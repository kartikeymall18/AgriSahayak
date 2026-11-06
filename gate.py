"""Leaf gate: decides whether a photo shows a plant leaf BEFORE the disease model looks at it.
Uses CLIP (zero-shot) so no leaf/not-leaf training data is needed. Runs on the laptop only.
Settings (optional, in config.py):  LEAF_GATE = True/False,  LEAF_MIN = 0.50"""
import os
import config

GATE_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "gate_model")
PLANT = [
    "a close-up photo of a plant leaf",
    "a photo of a green leaf",
    "a photo of a diseased leaf with brown spots",
    "a photo of a crop plant in a farm",
    "a photo of leaves of a tomato, potato or pepper plant",
]
OTHER = [
    "a photo of a person", "a photo of a human face", "a photo of a hand", "a photo of a room",
    "a photo of a wall", "a photo of a table or floor", "a photo of a laptop or computer",
    "a photo of a phone or screen", "a photo of a pet or animal", "a photo of food",
    "a photo of a potato tuber", "a photo of tomatoes", "a photo of bell peppers",
    "a photo of green chilli peppers", "a close-up photo of a single green chilli pepper",
    "a photo of vegetables or produce on a table",
    "a photo of a building or street", "a photo of a paper or document", "a dark blurry photo",
]
PROMPTS = PLANT + OTHER
CANDIDATE_PROMPTS = {
    "green chilli": ("a photo of green chilli peppers", "a close-up photo of a single green chilli pepper"),
    "bell pepper": ("a photo of bell peppers",),
    "tomato": ("a photo of tomatoes",),
    "potato": ("a photo of a potato tuber",),
}
MEAN = (0.48145466, 0.4578275, 0.40821073)
STD = (0.26862954, 0.26130258, 0.27577711)


def preprocess(img):
    """CLIP image preparation (resize short side to 224, centre crop, normalise). Returns (3,224,224) float32."""
    import numpy as np
    from PIL import Image
    img = img.convert("RGB")
    w, h = img.size
    s = 224
    if w <= h:
        nw, nh = s, max(s, int(s * h / w))
    else:
        nh, nw = s, max(s, int(s * w / h))
    img = img.resize((nw, nh), Image.BICUBIC)
    left, top = (nw - s) // 2, (nh - s) // 2
    img = img.crop((left, top, left + s, top + s))
    arr = np.asarray(img, dtype=np.float32) / 255.0
    arr = (arr - np.array(MEAN, dtype=np.float32)) / np.array(STD, dtype=np.float32)
    return arr.transpose(2, 0, 1)


class LeafGate:
    def __init__(self):
        self.ready = False
        self.error = None
        self.min = float(getattr(config, "LEAF_MIN", 0.50))
        if not getattr(config, "LEAF_GATE", True):
            self.error = "Leaf check is switched off in config.py"
            return
        if not os.path.isdir(GATE_DIR):
            self.error = "Leaf-check model not installed. Run download_gate.py once (internet needed)."
            return
        try:
            import torch
            from transformers import CLIPModel, AutoTokenizer
            self.torch = torch
            tok = AutoTokenizer.from_pretrained(GATE_DIR)
            enc = tok(PROMPTS, padding=True, return_tensors="pt")
            self.ids, self.mask = enc["input_ids"], enc["attention_mask"]
            self.model = CLIPModel.from_pretrained(GATE_DIR).eval()
            self.ready = True
        except Exception as e:
            self.error = "Could not load leaf-check model: " + str(e)

    def scores(self, img):
        """Probability for every prompt (list of floats, same order as PROMPTS)."""
        x = self.torch.from_numpy(preprocess(img)).unsqueeze(0)
        with self.torch.no_grad():
            out = self.model(input_ids=self.ids, attention_mask=self.mask, pixel_values=x)
        return out.logits_per_image[0].softmax(-1).tolist()

    def check(self, img):
        p = self.scores(img)
        plant = float(sum(p[:len(PLANT)]))
        best = max(range(len(PROMPTS)), key=lambda i: p[i])
        produce_scores = {name: round(max(float(p[PROMPTS.index(prompt)]) for prompt in prompts), 4)
                          for name, prompts in CANDIDATE_PROMPTS.items()}
        return {"is_plant": plant >= self.min, "plant_score": round(plant, 4),
                "best": PROMPTS[best].replace("a photo of ", "").replace("a close-up photo of ", ""),
                "best_score": round(float(p[best]), 4), "produce_scores": produce_scores}
