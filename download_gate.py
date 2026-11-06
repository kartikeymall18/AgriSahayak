# Run ONCE with internet (about 600 MB). Saves the leaf-check model into the folder "gate_model".
import os
from transformers import CLIPModel, AutoTokenizer

MODEL_ID = "openai/clip-vit-base-patch32"
OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "gate_model")
os.makedirs(OUT, exist_ok=True)
AutoTokenizer.from_pretrained(MODEL_ID).save_pretrained(OUT)
print("Saved tokenizer")
CLIPModel.from_pretrained(MODEL_ID).save_pretrained(OUT)
print("Done. Leaf-check model saved in:", OUT)
