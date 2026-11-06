# Test the model on one photo:  python classify_one.py leaf.jpg
import sys
from PIL import Image
from classifier import Classifier
import advice

if len(sys.argv) < 2:
    print("Usage: python classify_one.py path_to_leaf_photo.jpg")
    sys.exit(1)
clf = Classifier()
if not clf.ready:
    print("MODEL NOT READY:", clf.error)
    sys.exit(1)
img = Image.open(sys.argv[1]).convert("RGB")
print("Running on:", clf.device)
for t in clf.predict(img):
    print(f"{t['score']*100:5.1f}%  {advice.pretty(t['label'])}   [{advice.categorize(t['label'])}]")
