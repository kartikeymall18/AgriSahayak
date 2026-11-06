# OPTIONAL neural voice (Indic Parler-TTS). Runs as its own small program inside its own Python environment (tts_env),
# so the packages it needs cannot break the main server. The main server calls it on port 5005.
# Set up once with setup_parler_tts.bat, start with start_tts.bat, and set TTS_ENGINE = "parler" in config.py.
import io
import json
import os
from http.server import BaseHTTPRequestHandler, HTTPServer

import soundfile as sf
import torch
from parler_tts import ParlerTTSForConditionalGeneration
from transformers import AutoTokenizer

ROOT = os.path.dirname(os.path.abspath(__file__))
MODEL = os.path.join(ROOT, "voice_models", "indic-parler-tts")
TEXT_TOKENIZER = os.path.join(ROOT, "voice_models", "flan-t5-large-tokenizer")
dev = "cuda:0" if torch.cuda.is_available() else "cpu"
print("Loading the voice on", dev, "...")
dtype = torch.float16 if dev.startswith("cuda") else torch.float32
model = ParlerTTSForConditionalGeneration.from_pretrained(MODEL, torch_dtype=dtype).to(dev)
tok = AutoTokenizer.from_pretrained(MODEL)
dtok = AutoTokenizer.from_pretrained(TEXT_TOKENIZER, local_files_only=True)
VOICE = {
    "hi": "Divya's voice is clear and calm, speaking at a moderate speed, with a very close recording and very clear audio.",
    "en": "Mary's voice is a warm, natural American English female voice, with clear consonants and vowels, conversational intonation, a calm confident tone, and a moderate pace in a close, clean recording.",
}
VOICE["mai"] = "A female speaker delivers clear and calm speech at a moderate speed, with a very close recording and very clear audio."
VOICE["bho"] = VOICE["hi"]          # no Bhojpuri voice exists: the Hindi voice reads the Devanagari text (approximate)


def synth(text, lang):
    d = dtok(VOICE.get(lang, VOICE["hi"]), return_tensors="pt").to(dev)
    p = tok(text, return_tensors="pt").to(dev)
    with torch.no_grad():
        out = model.generate(input_ids=d.input_ids, attention_mask=d.attention_mask, prompt_input_ids=p.input_ids,
                             prompt_attention_mask=p.attention_mask, max_new_tokens=1024)
    buf = io.BytesIO()
    sf.write(buf, out.float().cpu().numpy().squeeze(), model.config.sampling_rate, format="WAV")
    return buf.getvalue()


class H(BaseHTTPRequestHandler):
    def log_message(self, *a):
        pass

    def do_GET(self):
        if self.path != "/health":
            self.send_response(404); self.end_headers(); return
        data = json.dumps({"ready": True, "engine": "Indic Parler-TTS", "device": dev}).encode("utf-8")
        self.send_response(200); self.send_header("Content-Type", "application/json"); self.end_headers(); self.wfile.write(data)

    def do_POST(self):
        try:
            body = json.loads(self.rfile.read(int(self.headers.get("Content-Length", 0))))
            data = synth(str(body.get("text", ""))[:600], body.get("lang", "hi"))
            self.send_response(200); self.send_header("Content-Type", "audio/wav"); self.end_headers(); self.wfile.write(data)
        except Exception as e:
            self.send_response(500); self.end_headers(); self.wfile.write(str(e).encode("utf-8", "replace"))


print("Neural voice ready on http://127.0.0.1:5005/tts")
HTTPServer(("127.0.0.1", 5005), H).serve_forever()
