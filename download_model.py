# Run ONCE with internet. It saves the model into the folder "model" so it works offline later.
import os
import shutil
from huggingface_hub import hf_hub_download
from transformers import AutoModelForImageClassification

MODEL_ID = "linkanjarad/mobilenet_v2_1.0_224-plant-disease-identification"
OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "model")
os.makedirs(OUT, exist_ok=True)

# 1) Image settings file: plain download, works with every transformers version.
p = hf_hub_download(MODEL_ID, "preprocessor_config.json")
shutil.copyfile(p, os.path.join(OUT, "preprocessor_config.json"))
print("Saved preprocessor_config.json")

# 2) The model itself.
AutoModelForImageClassification.from_pretrained(MODEL_ID).save_pretrained(OUT)
print("Done. Model saved in:", OUT)
