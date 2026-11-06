"""Speech to text with SraVaani-1.0 (IISc / ARTPARK, MIT licence). Covers Hindi, Bhojpuri, Maithili, Awadhi and many more.
The model is downloaded once by download_voice.py into voice_models/sravaani, then runs fully offline on the GPU."""
import os

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MODEL_DIR = os.path.join(ROOT, "voice_models", "sravaani")


def _setting(name, default):
    env = os.environ.get("AGRI_" + name)
    if env is not None:
        return env.strip().lower() not in ("0", "false", "no", "off", "")
    try:
        import config
        return bool(getattr(config, name, default))
    except Exception:
        return default


class ASR:
    def __init__(self):
        self.enabled = _setting("VOICE_ASR", True)
        self.state = "off" if not self.enabled else "idle"      # off, idle, missing, loading, ready, error
        self.error = None
        self.device = "cpu"
        self.model = None

    def prepare(self):
        """Called at start-up, instantly: shows 'missing' or 'loading' before the slow load begins."""
        if not self.enabled:
            self.state = "off"
        elif not os.path.isdir(MODEL_DIR) or not os.listdir(MODEL_DIR):
            self.state, self.error = "missing", "SraVaani is not downloaded yet. Run download_voice.py once."
        else:
            self.state = "loading"

    def load(self):
        """Runs once on the inference thread at start-up. Never raises."""
        if not self.enabled:
            self.state = "off"
            return
        if not os.path.isdir(MODEL_DIR) or not os.listdir(MODEL_DIR):
            self.state, self.error = "missing", "SraVaani is not downloaded yet. Run download_voice.py once."
            return
        self.state = "loading"
        try:
            import torch
            from transformers import AutoModel
            self.device = "cuda" if torch.cuda.is_available() else "cpu"
            m = AutoModel.from_pretrained(MODEL_DIR, trust_remote_code=True)
            m = m.to(self.device)
            if self.device == "cpu":
                m = m.float()
            self.model = m.eval()
            self.state, self.error = "ready", None
        except Exception as e:
            self.state, self.error = "error", (type(e).__name__ + ": " + str(e))[:500]

    def transcribe(self, wav_path):
        """WAV file (16 kHz mono is best) -> text. Must be called on the inference thread."""
        if self.state != "ready":
            raise RuntimeError("Speech recognition is not ready (%s). %s" % (self.state, self.error or ""))
        import torch
        with torch.no_grad():
            out = self.model.transcribe([wav_path], return_hypotheses=True)
        if isinstance(out, tuple):
            out = out[0]
        h = out[0] if isinstance(out, (list, tuple)) else out
        text = h if isinstance(h, str) else (getattr(h, "text", None) or str(h))
        return text.strip()

    def status(self):
        return {"state": self.state, "device": self.device, "error": self.error}
