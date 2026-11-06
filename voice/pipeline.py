"""The voice turn: audio in -> text (ASR) -> answer (fixed answers, optional LLM) -> audio out (TTS).
Every turn is logged to data/voice_log.jsonl with the four language decisions kept apart:
what the user spoke, what the recognizer wrote, the language of the answer, and the voice used."""
import io
import json
import os
import time
import wave

from .asr import ASR
from .llm import LLM
from .tts import TTS
from . import i18n


def script_of(text):
    deva = sum(1 for c in text if "\u0900" <= c <= "\u097F")
    latin = sum(1 for c in text if c.isascii() and c.isalpha())
    return "devanagari" if deva > latin else ("latin" if latin else "none")


class Voice:
    def __init__(self, data_dir, run_infer):
        self.dir = os.path.join(data_dir, "voice")
        os.makedirs(self.dir, exist_ok=True)
        self.asr, self.tts, self.llm = ASR(), TTS(self.dir), LLM()
        self.run_infer = run_infer                      # runs a function on the single inference thread and waits
        self.log_path = os.path.join(data_dir, "voice_log.jsonl")

    def start(self, submit):
        """Warm the speech recognition and voice helpers without blocking dashboard startup."""
        self.asr.prepare()
        if self.asr.state == "loading":
            submit(self.asr.load)
        self.tts.prepare()
        self.llm.prepare()

    def status(self):
        return {"asr": self.asr.status(), "tts": self.tts.status(), "llm": self.llm.status(), "languages": i18n.names()}

    # ---------- helpers ----------
    def _cleanup(self, keep=40):
        files = sorted((os.path.join(self.dir, f) for f in os.listdir(self.dir)), key=os.path.getmtime)
        for f in files[:-keep]:
            try:
                os.remove(f)
            except OSError:
                pass

    @staticmethod
    def wav_info(data):
        """(duration seconds, error text or None)"""
        try:
            with wave.open(io.BytesIO(data)) as w:
                return w.getnframes() / float(w.getframerate() or 1), None
        except Exception:
            return 0.0, "The audio is not a WAV file."

    def synth_url(self, text, lang):
        name = self.tts.synth(text, lang)
        return "/api/audio/" + name if name else None

    def _log(self, rec):
        try:
            with open(self.log_path, "a", encoding="utf-8") as f:
                f.write(json.dumps(rec, ensure_ascii=False) + "\n")
        except OSError:
            pass

    # ---------- one turn ----------
    def turn(self, wav_bytes, in_lang, out_lang, answer_fn, facts_fn, synthesize=True):
        t0 = time.time()
        in_lang = in_lang if in_lang in i18n.LANGS or in_lang == "auto" else "hi"
        out_lang = out_lang if out_lang in i18n.LANGS or out_lang == "auto" else "auto"
        res = {"ok": False, "in_lang": in_lang, "out_lang": out_lang, "timings": {}}
        dur, err = self.wav_info(wav_bytes)
        if err or dur < 0.4 or dur > 30:
            res["error"] = err or ("The recording is too short." if dur < 0.4 else "The recording is longer than 30 seconds.")
            res["code"] = "bad_audio"
            return res
        qname = "q_%d.wav" % int(t0 * 1000)
        qpath = os.path.join(self.dir, qname)
        with open(qpath, "wb") as f:
            f.write(wav_bytes)
        try:
            t = time.time()
            text = self.run_infer(self.asr.transcribe, qpath)
            res["timings"]["asr_ms"] = int((time.time() - t) * 1000)
        except Exception as e:
            res["error"], res["code"] = str(e)[:300], "asr_failed"
            return res
        if not text:
            res["error"], res["code"] = "I could not hear any words. Please speak closer to the microphone.", "no_speech"
            return res
        t = time.time()
        ans = answer_fn(text, out_lang)
        # The recognizer returns a transcript; the answer language follows it automatically.
        out_lang = ans.get("lang") if ans.get("lang") in i18n.LANGS else (out_lang if out_lang in i18n.LANGS else None)
        if out_lang not in i18n.LANGS:
            out_lang = "hi" if script_of(text) == "devanagari" else "en"
        res["timings"]["nlu_ms"] = int((time.time() - t) * 1000)
        llm_ms = None
        if ans.get("intent") == "unknown" and self.llm.enabled:
            t = time.time()
            llm_text = self.llm.answer(text, facts_fn(), out_lang)
            res["timings"]["llm_ms"] = int((time.time() - t) * 1000)
            llm_ms = res["timings"]["llm_ms"]
            if llm_text:
                ans["reply"], ans["intent"] = llm_text, "llm"
        t = time.time()
        res["audio_url"] = self.synth_url(ans["reply"], out_lang) if synthesize else None
        res["timings"]["tts_ms"] = int((time.time() - t) * 1000)
        res.update(ok=True, text_in=text, reply=ans["reply"], lang=out_lang, out_lang=out_lang, intent=ans["intent"], action=ans.get("action"),
                   llm_provider=self.llm.last_provider if ans["intent"] == "llm" else None, llm_ms=llm_ms)
        res["timings"]["total_ms"] = int((time.time() - t0) * 1000)
        self._log({"ts": time.strftime("%Y-%m-%dT%H:%M:%S"), "input_audio_language": in_lang, "asr_text": text, "asr_text_script": script_of(text),
                   "intent": ans["intent"], "response_language": out_lang, "reply": ans["reply"], "tts_engine": self.tts.engine,
                   "tts_voice": self.tts.last_voice, "audio_in": qname, "audio_out": res["audio_url"], "timings": res["timings"]})
        self._cleanup()
        return res
