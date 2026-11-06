# Test the leaf check on one or more photos:   python check_leaf.py photo1.jpg photo2.jpg ...
import sys
from PIL import Image
from gate import LeafGate, PROMPTS

if len(sys.argv) < 2:
    print("Usage: python check_leaf.py photo1.jpg [photo2.jpg ...]"); sys.exit(1)
g = LeafGate()
if not g.ready:
    print(g.error); sys.exit(1)
print("Limit (LEAF_MIN): %.2f   plant score at or above the limit = leaf\n" % g.min)
for path in sys.argv[1:]:
    img = Image.open(path).convert("RGB")
    p = g.scores(img)
    r = g.check(img)
    top = sorted(range(len(PROMPTS)), key=lambda i: -p[i])[:2]
    print("%-40s plant score %.2f  ->  %s   (looks most like: %s)" %
          (path[-40:], r["plant_score"], "LEAF" if r["is_plant"] else "NOT A LEAF", PROMPTS[top[0]]))
