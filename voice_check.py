# Tests every part of the voice system one by one and tells you which one is broken.   Run:  python voice_check.py
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
os.environ.setdefault("HF_HUB_OFFLINE", "1")
res = []


def say(status, name, detail=""):
    res.append(status)
    print("%-5s %-34s %s" % (status, name, detail))


print("AgriSahayak voice check\n" + "-" * 60)
# 1. GPU
try:
    import torch
    if torch.cuda.is_available():
        p = torch.cuda.get_device_properties(0)
        say("PASS", "PyTorch + GPU", "%s, %.1f GB video memory, torch %s" % (p.name, p.total_memory / 1e9, torch.__version__))
    else:
        say("WARN", "PyTorch + GPU", "torch %s sees NO GPU. Run: python install_cuda_torch.py (it works on CPU, but slowly)" % torch.__version__)
except Exception as e:
    say("FAIL", "PyTorch", str(e)[:120])
# 2. model files
from voice.asr import MODEL_DIR, ASR
say("PASS" if os.path.isdir(MODEL_DIR) and os.listdir(MODEL_DIR) else "FAIL", "SraVaani files", MODEL_DIR if os.path.isdir(MODEL_DIR) else "missing. Run: python download_voice.py")
# 3. speaker
from voice.tts import TTS
import tempfile
tts = TTS(os.path.join(tempfile.gettempdir(), "agri_voice_check"))
print("      speaker engine:", tts.engine)
wav = None
if tts.engine == "windows":
    v = tts.voices()
    hindi = [x for x in v if x[1].lower().startswith("hi")]
    say("PASS" if hindi else "FAIL", "Windows Hindi voice", ", ".join("%s (%s)" % x for x in hindi) if hindi else "none. Windows Settings, Time and language, Speech, Add voices, Hindi. Installed: " + ", ".join(x[0] for x in v))
name = tts.synth("नमस्ते, मैं फसल साथी हूँ। मिट्टी की नमी चालीस प्रतिशत है।", "hi")
if name:
    wav = os.path.join(tts.outdir, name)
    say("PASS", "Make a Hindi sentence", "%s (voice: %s)" % (name, tts.last_voice))
else:
    say("FAIL" if tts.engine != "none" else "SKIP", "Make a Hindi sentence", tts.note or "no audio made")
# 4. speech recognition on that sentence (round trip)
if wav and os.path.isdir(MODEL_DIR):
    a = ASR()
    t0 = time.time()
    a.load()
    if a.state == "ready":
        say("PASS", "Load SraVaani", "%s in %.0f s" % (a.device, time.time() - t0))
        t0 = time.time()
        try:
            text = a.transcribe(wav)
            say("PASS" if text else "FAIL", "Recognise the Hindi sentence", "%.1f s  ->  %s" % (time.time() - t0, text or "(empty)"))
            print("      It should be close to: नमस्ते मैं फसल साथी हूँ मिट्टी की नमी चालीस प्रतिशत है")
        except Exception as e:
            say("FAIL", "Recognise the Hindi sentence", str(e)[:200])
    else:
        say("FAIL", "Load SraVaani", (a.error or a.state)[:300])
        print("      If the message says 'No module named X': pip install X  (then run this again).")
        print("      If it mentions transformers or remote code: pip install \"transformers<5\"")
else:
    say("SKIP", "SraVaani test", "needs the model files and a working speaker")
# 5. optional parts
from voice.llm import LLM
l = LLM()
if l.enabled:
    say("PASS" if l.ready() else "WARN", "LLM (Ollama)", l.model if l.ready() else (l.error or "not ready"))
else:
    say("SKIP", "LLM (Ollama)", "switched off (USE_LLM in config.py)")
if tts.engine == "parler":
    import urllib.request
    try:
        urllib.request.urlopen(os.environ.get("AGRI_TTS_URL", "http://127.0.0.1:5005/"), timeout=2)
        say("PASS", "Neural voice program", "answers on port 5005")
    except Exception as e:
        say("WARN" if "HTTP Error 404" in str(e) or "405" in str(e) else "FAIL", "Neural voice program", "run start_tts.bat in another window (%s)" % str(e)[:60])
print("-" * 60)
print("Result: %d PASS, %d WARN, %d FAIL, %d SKIP" % tuple(res.count(k) for k in ("PASS", "WARN", "FAIL", "SKIP")))
