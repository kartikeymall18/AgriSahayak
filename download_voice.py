# Downloads the speech model(s) ONCE (internet needed). Afterwards everything runs offline.
#   python download_voice.py            -> SraVaani-1.0 speech recognition (about 1 GB)
#   python download_voice.py --parler   -> also Indic Parler-TTS neural voice (optional, for the separate voice program)
# Both models are "gated": log in at huggingface.co, open the model page, press the button that accepts the conditions,
# then make a READ token at huggingface.co/settings/tokens and paste it here when asked.
import getpass
import os
import sys

os.environ.pop("HF_HUB_OFFLINE", None)
os.environ.pop("TRANSFORMERS_OFFLINE", None)
from huggingface_hub import snapshot_download, hf_hub_download

ROOT = os.path.dirname(os.path.abspath(__file__))
MODELS = [("ARTPARK-IISc/SraVaani-1.0", os.path.join(ROOT, "voice_models", "sravaani"), "https://huggingface.co/ARTPARK-IISc/SraVaani-1.0")]
if "--parler" in sys.argv:
    MODELS.append(("ai4bharat/indic-parler-tts", os.path.join(ROOT, "voice_models", "indic-parler-tts"), "https://huggingface.co/ai4bharat/indic-parler-tts"))

token = os.environ.get("HF_TOKEN") or getpass.getpass("Paste your Hugging Face READ token (it stays hidden, nothing is saved): ").strip()
for repo, dest, page in MODELS:
    print("\nDownloading %s -> %s" % (repo, dest))
    try:
        snapshot_download(repo_id=repo, local_dir=dest, token=token or None)
        print("OK:", repo)
    except Exception as e:
        msg = str(e)
        print("FAILED:", msg[:300])
        if "401" in msg or "403" in msg or "gated" in msg.lower() or "restricted" in msg.lower():
            print("This model needs access. Open %s while logged in, accept the conditions, and run this again." % page)
        sys.exit(1)
if "--parler" in sys.argv:
    # The Parler speaker-description encoder uses Flan-T5's tokenizer as well.
    # Keep it beside the voice model so normal startup can remain fully offline.
    tokenizer_dir = os.path.join(ROOT, "voice_models", "flan-t5-large-tokenizer")
    os.makedirs(tokenizer_dir, exist_ok=True)
    print("\nDownloading the local Parler description tokenizer")
    for filename in ("special_tokens_map.json", "spiece.model", "tokenizer_config.json", "tokenizer.json"):
        try:
            hf_hub_download(repo_id="google/flan-t5-large", filename=filename, token=token or None, local_dir=tokenizer_dir)
        except Exception as e:
            print("FAILED to download tokenizer file %s: %s" % (filename, str(e)[:200]))
            sys.exit(1)
print("\nAll done. Next: python voice_check.py")
