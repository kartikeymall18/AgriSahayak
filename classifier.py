import os
import json

MODEL_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "model")


def _size_pair(v, default):
    """Turn an int or a dict from preprocessor_config.json into (height, width)."""
    if isinstance(v, dict):
        if "height" in v and "width" in v:
            return int(v["height"]), int(v["width"])
        if "shortest_edge" in v:
            return int(v["shortest_edge"]), int(v["shortest_edge"])
    if isinstance(v, int):
        return v, v
    return default, default


def preprocess(img, cfg):
    """Same steps as the Hugging Face MobileNetV2 image processor, written by hand
    so it does not depend on the transformers version. Returns a float32 array (3, H, W)."""
    import numpy as np
    from PIL import Image

    img = img.convert("RGB")
    resample = cfg.get("resample", 2)
    if not isinstance(resample, int) or resample < 0 or resample > 5:
        resample = 2  # bilinear

    if cfg.get("do_resize", True):
        size = cfg.get("size", {"shortest_edge": 256})
        w, h = img.size
        if isinstance(size, dict) and "shortest_edge" in size:
            s = int(size["shortest_edge"])
            if w <= h:
                nw, nh = s, int(s * h / w)
            else:
                nh, nw = s, int(s * w / h)
        else:
            nh, nw = _size_pair(size, 224)
        img = img.resize((nw, nh), resample)

    if cfg.get("do_center_crop", True):
        ch, cw = _size_pair(cfg.get("crop_size", 224), 224)
        w, h = img.size
        top = max((h - ch) // 2, 0)
        left = max((w - cw) // 2, 0)
        img = img.crop((left, top, left + cw, top + ch))

    arr = np.asarray(img, dtype=np.float32)
    if cfg.get("do_rescale", True):
        arr = arr * float(cfg.get("rescale_factor", 1 / 255))
    if cfg.get("do_normalize", True):
        mean = np.array(cfg.get("image_mean", [0.5, 0.5, 0.5]), dtype=np.float32)
        std = np.array(cfg.get("image_std", [0.5, 0.5, 0.5]), dtype=np.float32)
        arr = (arr - mean) / std
    return arr.transpose(2, 0, 1)


class Classifier:
    def __init__(self):
        self.ready = False
        self.error = None
        self.device = "cpu"
        self.cfg = {}
        self._load()

    def _load(self):
        if not os.path.isdir(MODEL_DIR):
            self.error = "Model folder not found. Run download_model.py once (internet needed)."
            return
        try:
            import torch
            from transformers import AutoModelForImageClassification
            self.torch = torch
            torch.set_num_threads(min(4, os.cpu_count() or 4))
            self.device = "cuda" if torch.cuda.is_available() else "cpu"
            cfg_path = os.path.join(MODEL_DIR, "preprocessor_config.json")
            if os.path.isfile(cfg_path):
                with open(cfg_path, encoding="utf-8") as f:
                    self.cfg = json.load(f)
            self.model = AutoModelForImageClassification.from_pretrained(MODEL_DIR).to(self.device).eval()
            self.ready = True
        except Exception as e:
            self.error = "Could not load model: " + str(e)

    def predict(self, img, k=3):
        arr = preprocess(img, self.cfg)
        x = self.torch.from_numpy(arr).unsqueeze(0).to(self.device)
        with self.torch.no_grad():
            logits = self.model(pixel_values=x).logits
        probs = logits.softmax(-1)[0]
        top = probs.topk(min(k, probs.shape[0]))
        id2label = self.model.config.id2label
        return [{"label": id2label[int(i)], "score": float(s)} for s, i in zip(top.values, top.indices)]
