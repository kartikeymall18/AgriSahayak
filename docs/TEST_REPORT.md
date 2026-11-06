# Test report

**Scope:** sanitized GitHub-ready source package. This report separates deterministic code checks from local model smoke tests and physical hardware checks.

## Environment used for source/model checks

- Windows, Python 3.11.9
- PyTorch 2.14.1+cu130; CUDA available on the NVIDIA GPU
- Transformers 5.21.1; Flask 3.1.3
- Report date: 2026-11-06

## Results

| Check | Result | What it proves / does not prove |
|---|---|---|
| Python source syntax | PASS — 27 Python files parsed | Parser-level syntax only |
| Deterministic unit checks | PASS — 7 tests | Farm-support shortlist, package privacy defaults, safe host setting and tablet asset presence |
| Leaf model loading/inference smoke | PASS — loaded on CUDA; synthetic-image inference 0.53 s | Structurally valid output only; synthetic label is not accuracy evidence |
| CLIP gate loading/inference smoke | PASS — loaded; synthetic-image inference 0.26 s | Valid scores only; synthetic scene result is not accuracy evidence |
| Produce detector loading/inference smoke | PASS — loaded on CUDA; synthetic-image inference 0.56 s | Returned boxes/count schema; synthetic detections are not accuracy evidence |
| Tomato-fruit screen smoke | PASS — loaded on CUDA; synthetic-image inference 0.14 s | Returned a supported status; synthetic status is not fruit-health evidence |
| Tomato-fruit held-out evaluation | PASS — 79 images, CUDA, 3.23 s | Reproduced the saved metrics: accuracy 89.87%, macro-F1 89.10%, balanced accuracy 88.24% |
| Dashboard route and visual review | PASS — overview, live monitor, rover, support desk, Fasal Saathi, and records rendered in Edge at 1920×1200; local routes returned HTTP 200 | Screenshots use the sanitized copy's empty record store; no connected tablet, rover, or model weights |
| Staged-file privacy scanner | PASS — 78 staged files scanned; the six exact preview screenshots are SHA-256 allow-listed after visual review | No common API keys, personal paths/emails, or unapproved private artifact types found |
| Actual tablet camera, Wi-Fi/OTG and Arduino motor control | Not run here | Requires the physical tablet, rover, wiring and safe bench setup |

## Run source checks

```powershell
python -m unittest discover -s tests -v
```

## Accuracy numbers

The tomato evaluation was run using the project's existing `train_tomato_fruit.split_data()` split and saved local checkpoint; the 372/79/79 split and reported metrics match `screening_metrics.json`. It does not independently validate field performance, and it is not a new data collection. Model-card values and this evaluation are documented in [Model report](MODEL_REPORT.md). No 39-model benchmark table from another repository is attributed to AgriSahayak.

