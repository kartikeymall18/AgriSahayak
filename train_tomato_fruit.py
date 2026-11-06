"""Fine-tune a separate two-class tomato-fruit screening model.

Input folders under data/tomato_fruit_train:
  Healthy_Tomato/  Disease_Tomato/

The label is binary and only supports screening; it is not a fruit-pathology diagnosis.
"""
import json
import os
import random
from pathlib import Path

import numpy as np
import torch
from PIL import Image, ImageEnhance, ImageOps
from torch import nn
from torch.utils.data import DataLoader, Dataset
from transformers import AutoModelForImageClassification

from classifier import MODEL_DIR as LEAF_MODEL_DIR, preprocess

ROOT = Path(__file__).resolve().parent
DATA_DIR = ROOT / "data" / "tomato_fruit_train"
OUT_DIR = ROOT / "model" / "tomato_fruit_disease"
SEED = 41
EPOCHS = 18
BATCH = 24
LABELS = {0: "Healthy tomato fruit", 1: "Possible diseased tomato fruit"}


def split_data():
    rng = random.Random(SEED)
    splits = {"train": [], "val": [], "test": []}
    for folder, label in (("Healthy_Tomato", 0), ("Disease_Tomato", 1)):
        files = [p for p in (DATA_DIR / folder).glob("*") if p.suffix.lower() in (".jpg", ".jpeg", ".png")]
        if len(files) < 25:
            raise RuntimeError("Not enough images in " + str(DATA_DIR / folder))
        rng.shuffle(files)
        n_test = max(1, round(len(files) * 0.15))
        n_val = max(1, round(len(files) * 0.15))
        splits["test"].extend((p, label) for p in files[:n_test])
        splits["val"].extend((p, label) for p in files[n_test:n_test + n_val])
        splits["train"].extend((p, label) for p in files[n_test + n_val:])
    for rows in splits.values():
        rng.shuffle(rows)
    return splits


def load_image(path, augment):
    with Image.open(path) as source:
        img = source.convert("RGB")
    if augment:
        if random.random() < 0.5:
            img = ImageOps.mirror(img)
        if random.random() < 0.35:
            img = img.rotate(random.uniform(-12, 12), resample=Image.Resampling.BILINEAR)
        if random.random() < 0.65:
            img = ImageEnhance.Brightness(img).enhance(random.uniform(0.85, 1.15))
            img = ImageEnhance.Contrast(img).enhance(random.uniform(0.85, 1.15))
            img = ImageEnhance.Color(img).enhance(random.uniform(0.82, 1.18))
    return torch.from_numpy(preprocess(img, _PREPROCESSOR).copy())


class FruitDataset(Dataset):
    def __init__(self, rows, augment=False):
        self.rows = rows
        self.augment = augment

    def __len__(self):
        return len(self.rows)

    def __getitem__(self, index):
        path, label = self.rows[index]
        return load_image(path, self.augment), label


def metrics(y_true, y_pred):
    result = {}
    f1s, recalls = [], []
    for label in (0, 1):
        tp = sum(a == label and b == label for a, b in zip(y_true, y_pred))
        fp = sum(a != label and b == label for a, b in zip(y_true, y_pred))
        fn = sum(a == label and b != label for a, b in zip(y_true, y_pred))
        precision = tp / max(1, tp + fp)
        recall = tp / max(1, tp + fn)
        f1 = 2 * precision * recall / max(1e-9, precision + recall)
        result["healthy" if label == 0 else "possible_disease"] = {
            "precision": round(precision, 4), "recall": round(recall, 4), "f1": round(f1, 4)}
        f1s.append(f1)
        recalls.append(recall)
    result["accuracy"] = round(sum(a == b for a, b in zip(y_true, y_pred)) / max(1, len(y_true)), 4)
    result["macro_f1"] = round(sum(f1s) / 2, 4)
    result["balanced_accuracy"] = round(sum(recalls) / 2, 4)
    return result


def evaluate(model, loader, device):
    model.eval()
    y_true, y_pred = [], []
    with torch.inference_mode():
        for x, y in loader:
            logits = model(pixel_values=x.to(device)).logits
            y_true.extend(y.tolist())
            y_pred.extend(logits.argmax(-1).cpu().tolist())
    return metrics(y_true, y_pred)


def main():
    global _PREPROCESSOR
    torch.manual_seed(SEED)
    np.random.seed(SEED)
    random.seed(SEED)
    torch.set_num_threads(min(4, os.cpu_count() or 4))
    device = "cuda" if torch.cuda.is_available() else "cpu"
    cfg_path = Path(LEAF_MODEL_DIR) / "preprocessor_config.json"
    _PREPROCESSOR = json.loads(cfg_path.read_text(encoding="utf-8"))
    splits = split_data()
    print("Device:", device)
    print("Split sizes:", {k: len(v) for k, v in splits.items()})

    model = AutoModelForImageClassification.from_pretrained(LEAF_MODEL_DIR, local_files_only=True)
    model.classifier = nn.Linear(model.classifier.in_features, 2)
    model.config.num_labels = 2
    model.config.id2label = LABELS
    model.config.label2id = {v: k for k, v in LABELS.items()}
    model.to(device)

    train_loader = DataLoader(FruitDataset(splits["train"], augment=True), batch_size=BATCH,
                              shuffle=True, num_workers=0, pin_memory=device == "cuda")
    val_loader = DataLoader(FruitDataset(splits["val"]), batch_size=BATCH,
                            shuffle=False, num_workers=0, pin_memory=device == "cuda")
    test_loader = DataLoader(FruitDataset(splits["test"]), batch_size=BATCH,
                             shuffle=False, num_workers=0, pin_memory=device == "cuda")
    class_counts = [sum(y == c for _, y in splits["train"]) for c in (0, 1)]
    weights = torch.tensor([len(splits["train"]) / (2 * max(1, n)) for n in class_counts],
                           dtype=torch.float32, device=device)
    criterion = nn.CrossEntropyLoss(weight=weights)
    feature_params = [p for n, p in model.named_parameters() if "classifier" not in n]
    head_params = list(model.classifier.parameters())
    optimizer = torch.optim.AdamW([
        {"params": feature_params, "lr": 1.5e-5},
        {"params": head_params, "lr": 4e-4},
    ], weight_decay=0.01)

    best_f1, best_state, patience = -1.0, None, 0
    for epoch in range(1, EPOCHS + 1):
        model.train()
        running, seen = 0.0, 0
        for x, y in train_loader:
            x, y = x.to(device), y.to(device)
            optimizer.zero_grad(set_to_none=True)
            loss = criterion(model(pixel_values=x).logits, y)
            loss.backward()
            torch.nn.utils.clip_grad_norm_(model.parameters(), 1.0)
            optimizer.step()
            running += float(loss.item()) * len(y)
            seen += len(y)
        val = evaluate(model, val_loader, device)
        print("Epoch %02d  loss %.4f  val acc %.3f  val macro-F1 %.3f" %
              (epoch, running / max(1, seen), val["accuracy"], val["macro_f1"]))
        if val["macro_f1"] > best_f1:
            best_f1 = val["macro_f1"]
            best_state = {k: v.detach().cpu().clone() for k, v in model.state_dict().items()}
            patience = 0
        else:
            patience += 1
            if patience >= 5:
                break

    if best_state is None:
        raise RuntimeError("Training did not produce a checkpoint")
    model.load_state_dict(best_state)
    test = evaluate(model, test_loader, device)
    print("Held-out test metrics:", json.dumps(test, indent=2))
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    model.save_pretrained(str(OUT_DIR), safe_serialization=True)
    (OUT_DIR / "preprocessor_config.json").write_text(json.dumps(_PREPROCESSOR, indent=2), encoding="utf-8")
    result = {
        "source_dataset": "TCP (Tomato-Chilli-Papaya Fruit & Leaf) Disease Dataset, Mendeley Data, v4",
        "source_url": "https://data.mendeley.com/datasets/m4m6j2tjfj/4",
        "dataset_authors": ["Anand Kumar Jain", "Neeta Nain", "Anadi Jain"],
        "related_paper": "https://doi.org/10.21203/rs.3.rs-8819059/v1",
        "license": "CC BY 4.0; attribution required",
        "base_model": "Existing AgriSahayak classifier weights from linkanjarad/mobilenet_v2_1.0_224-plant-disease-identification",
        "classes": LABELS,
        "binary_scope": "healthy tomato fruit vs possible diseased tomato fruit; no specific disease name",
        "split_sizes": {k: len(v) for k, v in splits.items()},
        "held_out_test": test,
        "confidence_threshold": 0.68,
        "caveat": "Small source dataset and prototype validation. Field images may differ; low-confidence outputs must be marked uncertain and confirmed by a plant-health professional.",
    }
    (OUT_DIR / "screening_metrics.json").write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print("Saved model:", OUT_DIR)


if __name__ == "__main__":
    main()
