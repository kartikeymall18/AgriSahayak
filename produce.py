"""Local produce detector and a separate limited tomato-fruit screening model."""
import os
import json
import threading

import torch
import numpy as np
from transformers import AutoImageProcessor, AutoModelForObjectDetection

from classifier import preprocess


TOMATO_STAGE_LABELS = {
    "mostly_green": "Mostly green",
    "turning": "Turning color",
    "mostly_red": "Mostly red",
    "uncertain": "Color unclear",
}


def estimate_tomato_color_stage(image, box):
    """Rough surface-color cue for a tomato box, not a maturity or quality diagnosis."""
    try:
        x1, y1, x2, y2 = [int(round(float(v))) for v in box]
        x1, x2 = max(0, x1), min(image.width, x2)
        y1, y2 = max(0, y1), min(image.height, y2)
        if x2 - x1 < 4 or y2 - y1 < 4:
            return "uncertain"
        rgb = np.asarray(image.crop((x1, y1, x2, y2)).convert("RGB"), dtype=np.float32) / 255.0
        r, g, b = rgb[..., 0], rgb[..., 1], rgb[..., 2]
        mx, mn = rgb.max(axis=2), rgb.min(axis=2)
        delta = mx - mn
        hue = np.zeros_like(mx)
        nz = delta > 1e-6
        mr, mg, mb = (mx == r) & nz, (mx == g) & nz, (mx == b) & nz
        hue[mr] = ((g[mr] - b[mr]) / delta[mr]) % 6
        hue[mg] = ((b[mg] - r[mg]) / delta[mg]) + 2
        hue[mb] = ((r[mb] - g[mb]) / delta[mb]) + 4
        hue *= 60
        saturation = np.divide(delta, mx, out=np.zeros_like(delta), where=mx > 1e-6)
        valid = (saturation >= 0.22) & (mx >= 0.16) & (mx <= 0.995)
        n = int(valid.sum())
        if n < 20:
            return "uncertain"
        red = float((valid & ((hue < 22) | (hue >= 340))).sum()) / n
        orange = float((valid & (hue >= 22) & (hue < 52)).sum()) / n
        green = float((valid & (hue >= 52) & (hue <= 165)).sum()) / n
        if red >= 0.50 and red >= green * 1.25:
            return "mostly_red"
        if green >= 0.58 and green >= red * 1.25:
            return "mostly_green"
        if (red + orange) >= 0.24 and green >= 0.12:
            return "turning"
        if orange >= 0.28 or (red >= 0.18 and green >= 0.18):
            return "turning"
        return "uncertain"
    except Exception:
        return "uncertain"


class ProduceDetector:
    def __init__(self, model_dir):
        self.model_dir = model_dir
        self.processor = None
        self.model = None
        self.device = "cpu"
        self.error = None
        self._lock = threading.Lock()
        self.fruit_health = TomatoFruitScreen(os.path.join(os.path.dirname(model_dir), "tomato_fruit_disease"))

    @property
    def ready(self):
        return self.model is not None

    def load(self):
        if self.ready:
            return True
        with self._lock:
            if self.ready:
                return True
            if not os.path.isfile(os.path.join(self.model_dir, "model.safetensors")):
                self.error = "Produce detector weights are missing."
                return False
            try:
                processor = AutoImageProcessor.from_pretrained(self.model_dir, local_files_only=True)
                model = AutoModelForObjectDetection.from_pretrained(
                    self.model_dir, local_files_only=True, use_safetensors=True)
                self.device = "cuda:0" if torch.cuda.is_available() else "cpu"
                model.to(self.device).eval()
                self.processor, self.model, self.error = processor, model, None
                return True
            except Exception as exc:
                self.error = "Could not load the produce detector: %s" % str(exc)[:180]
                self.processor, self.model = None, None
                return False

    def predict(self, image, threshold=0.45):
        """Return produce boxes/counts and a limited binary screen for each tomato fruit box."""
        if not self.load():
            return {"detections": [], "counts": {}, "error": self.error}
        try:
            inputs = self.processor(images=image, return_tensors="pt").to(self.device)
            with torch.inference_mode():
                outputs = self.model(**inputs)
            sizes = torch.tensor([[image.height, image.width]], device="cpu")
            result = self.processor.post_process_object_detection(
                outputs, threshold=threshold, target_sizes=sizes)[0]
            detections = []
            counts = {}
            for score, label, box in zip(result["scores"], result["labels"], result["boxes"]):
                name = self.model.config.id2label[int(label.item())]
                confidence = float(score.item())
                x1, y1, x2, y2 = [round(float(v), 1) for v in box.tolist()]
                detection = {"label": name, "score": round(confidence, 4),
                             "box": [x1, y1, x2, y2]}
                if name.strip().lower() == "tomato":
                    stage = estimate_tomato_color_stage(image, (x1, y1, x2, y2))
                    detection["color_stage"] = stage
                    detection["color_stage_label"] = TOMATO_STAGE_LABELS[stage]
                detections.append(detection)
                counts[name] = counts.get(name, 0) + 1
            detections.sort(key=lambda item: item["score"], reverse=True)
            tomato_boxes = [d["box"] for d in detections
                            if str(d.get("label", "")).strip().lower() == "tomato"]
            tomato_sample_screen = None
            if tomato_boxes:
                x1 = min(box[0] for box in tomato_boxes); y1 = min(box[1] for box in tomato_boxes)
                x2 = max(box[2] for box in tomato_boxes); y2 = max(box[3] for box in tomato_boxes)
                pad_x, pad_y = (x2 - x1) * 0.12, (y2 - y1) * 0.12
                roi = image.crop((max(0, int(x1 - pad_x)), max(0, int(y1 - pad_y)),
                                  min(image.width, int(x2 + pad_x)), min(image.height, int(y2 + pad_y))))
                tomato_sample_screen = self.fruit_health.predict(roi)
            self.error = None
            return {"detections": detections, "counts": counts,
                    "tomato_sample_screen": tomato_sample_screen, "error": None}
        except Exception as exc:
            self.error = "Produce detection failed: %s" % str(exc)[:180]
            return {"detections": [], "counts": {}, "error": self.error}


class TomatoFruitScreen:
    """Small, separate binary fruit screen; does not replace the leaf disease model."""
    def __init__(self, model_dir):
        self.model_dir = model_dir
        self.model = None
        self.device = "cpu"
        self.error = None
        self.cfg = {}
        self.threshold = 0.68
        self._lock = threading.Lock()

    @property
    def installed(self):
        return os.path.isfile(os.path.join(self.model_dir, "model.safetensors"))

    @property
    def ready(self):
        return self.model is not None

    def load(self):
        if self.ready:
            return True
        with self._lock:
            if self.ready:
                return True
            try:
                from transformers import AutoModelForImageClassification
                with open(os.path.join(self.model_dir, "preprocessor_config.json"), encoding="utf-8") as f:
                    self.cfg = json.load(f)
                try:
                    with open(os.path.join(self.model_dir, "screening_metrics.json"), encoding="utf-8") as f:
                        self.threshold = float(json.load(f).get("confidence_threshold", self.threshold))
                except (OSError, ValueError, TypeError):
                    pass
                torch.set_num_threads(min(4, os.cpu_count() or 4))
                self.device = "cuda" if torch.cuda.is_available() else "cpu"
                model = AutoModelForImageClassification.from_pretrained(
                    self.model_dir, local_files_only=True, use_safetensors=True)
                self.model = model.to(self.device).eval()
                self.error = None
                return True
            except Exception as exc:
                self.error = "Tomato fruit screen could not load: %s" % str(exc)[:180]
                self.model = None
                return False

    def predict(self, image):
        if not self.load():
            return {"status": "unavailable", "error": self.error}
        try:
            arr = preprocess(image, self.cfg)
            x = torch.from_numpy(arr).unsqueeze(0).to(self.device)
            with torch.inference_mode():
                probs = self.model(pixel_values=x).logits.softmax(-1)[0]
            class_id = int(probs.argmax().item())
            confidence = float(probs[class_id].item())
            if confidence < self.threshold:
                return {"status": "uncertain", "confidence": round(confidence, 4),
                        "threshold": self.threshold}
            return {"status": "healthy" if class_id == 0 else "possible_disease",
                    "confidence": round(confidence, 4), "threshold": self.threshold}
        except Exception as exc:
            self.error = "Tomato fruit screening failed: %s" % str(exc)[:180]
            return {"status": "unavailable", "error": self.error}
