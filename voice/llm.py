"""Optional helper for free-form questions: local Qwen first, then a configured online provider.
It is only asked when fixed answers cannot handle the question. It sees a small FACTS list, and its answer is
discarded if it contains unsafe treatment advice. Then the fixed answer is used instead."""
import json
import os
import re
import time
import threading
import urllib.request

NAMES = {"hi": "Hindi", "bho": "Bhojpuri", "mai": "Maithili", "en": "English"}
SCRIPTS = {"hi": "Devanagari", "bho": "Devanagari", "mai": "Devanagari", "en": "Latin"}
LANGUAGE_RULES = {
    "hi": "Write simple standard Hindi only in Devanagari, never Romanized Hindi. Example: 'potato kya hai?' -> 'आलू खाने योग्य भूमिगत तना-कंद है।'",
    "bho": "Write natural Bhojpuri in Devanagari, not standard Hindi and not Roman letters. Example: 'potato ka ha?' -> 'आलू खाए के लायक जमीन के नीचे उगे वाला कंद ह।'",
    "mai": "Write natural Maithili in Devanagari, not standard Hindi and not Roman letters. Example: 'potato ki achhi?' -> 'आलू खेबा योग्य जमीनक नीचाँ उगएबला कन्द अछि।'",
    "en": "Write natural English using Latin script.",
}
SYSTEM = ("You are Fasal Saathi, a concise and practical farm assistant. "
          "Answer the user's actual question directly in {lang}, using {script} script. "
          "Language rule: {language_rule} "
          "Use at most two short sentences and 45 words. Output only the final answer: no greeting unless the user greeted you, "
          "no reasoning, no analysis, no JSON, no markdown, and no repetition of the question. "
          "Use FACTS only for claims about this user's scans, sensors, or field; never invent those measurements or diagnoses. "
          "When FACTS contains a matching crop_reference and the user asks what that crop is, use that definition and answer only that question. "
          "The produce detector estimates counts of supported objects, which may be wrong. For tomatoes only, a separate visual color cue may estimate mostly-green, turning, mostly-red, or unclear surface color; do not treat this as confirmed maturity, freshness, quality, health, or disease. It does not diagnose disease on fruit. "
          "The supported produce classes are apple, cherry, fig, olive, pomegranate, orange, rockmelon, strawberry, potato, tomato, watermelon, and bell pepper; green chilli is not a supported detector class. "
          "For general crop questions, you may give brief general information and label it as general guidance when needed. "
          "Do not invent current government scheme eligibility, benefit amounts, or official contacts. "
          "Do not recommend medicines, pesticides, fertilizers, sprays, or application amounts; for treatment decisions, refer the farmer to a local agriculture officer. "
          "If you are unsure, say so briefly and suggest the next safe step.")
BANNED = ["mancozeb", "carbendazim", "imidacloprid", "chlorpyrifos", "cypermethrin", "glyphosate", "streptocycline", "streptomycin", "metalaxyl",
          "hexaconazole", "propiconazole", "thiamethoxam", "monocrotophos", "profenofos", "dimethoate", "malathion", "endosulfan", "copper oxychloride",
          "bordeaux", "sulphur", "sulfur", "urea", "dap ", "npk", "fungicide", "pesticide", "insecticide", "antibiotic", "neem oil",
          "मैन्कोजेब", "कार्बेन्डाजिम", "इमिडाक्लोप्रिड", "क्लोरपायरीफॉस", "ग्लाइफोसेट", "स्ट्रेप्टोसाइक्लिन", "यूरिया", "डीएपी", "कीटनाशक", "फफूंदनाशक", "फफूंद नाशक", "नीम का तेल", "नीम तेल"]
AMOUNT = re.compile(r"\d+(\.\d+)?\s*(ml|mg|g|gm|gram|grams|kg|l|ltr|litre|liter|liters|litres|tbsp|tsp|cc|ppm|मिली|मि\.ली|ग्राम|किलो|लीटर|चम्मच|%)\b|per\s+(acre|hectare|litre|liter)|प्रति\s*(एकड़|हेक्टेयर|लीटर|बीघा)", re.I)
CROP_ALIASES = {"potato": ("potato", "potatoes", "aloo", "aaloo", "आलू"), "tomato": ("tomato", "tomatoes", "tamatar", "टमाटर"), "chilli": ("chilli", "chili", "mirchi", "मिर्च"), "bell pepper": ("bell pepper", "capsicum", "shimla mirch", "शिमला मिर्च")}
BHO_OUTPUT = {"ह", "हई", "हईं", "बा", "बानी", "रउआ", "भइल", "कइल", "चाहीं", "लागेला"}
MAI_OUTPUT = {"अछि", "छी", "छियै", "अहाँ", "हमर", "करैत", "कतए", "कतेक", "नहि"}


def _facts_for_question(facts, question):
    """Keep crop definitions focused so unrelated field telemetry doesn't crowd the answer."""
    if not isinstance(facts, dict):
        return {}
    q = (question or "").lower()
    refs = facts.get("crop_reference") or {}
    crop = next((name for name, aliases in CROP_ALIASES.items() if any(alias in q for alias in aliases)), None)
    definition = any(x in q for x in ("what is", "what are", "define", "meaning", "kya hai", "kya hota", "ka ha", "ki achhi", "काहे", "का ह", "का बा", "की अछि", "क्या है", "क्या होता", "का मतलब"))
    if crop and definition and crop in refs:
        return {"crop_reference": {crop: refs[crop]}}
    if crop and any(x in q for x in ("fruit", "count", "identify", "recognize", "recognise", "scan", "फल", "गिन", "पहचान")):
        result = {"crop_reference": {crop: refs[crop]}} if crop in refs else {}
        if facts.get("vision_capabilities"):
            result["vision_capabilities"] = facts["vision_capabilities"]
        return result or facts
    return facts


def safe(text):
    """True only if the text has no amounts, doses or chemical names."""
    t = " " + text.lower() + " "
    return not AMOUNT.search(text) and not any(b in t for b in BANNED)


def language_matches(text, lang):
    """Reject an LLM answer that ignored the requested script or regional language."""
    deva = set(re.findall(r"[\u0900-\u0963\u0965-\u097F]+", text or ""))
    if lang == "en":
        return not deva
    if not deva:
        return False
    if lang == "bho":
        return bool(deva & BHO_OUTPUT)
    if lang == "mai":
        return bool(deva & MAI_OUTPUT)
    return True


class LLM:
    def __init__(self):
        v = os.environ.get("AGRI_USE_LLM")
        try:
            import config
            cfg = bool(getattr(config, "USE_LLM", False))
            self.model = getattr(config, "LLM_MODEL", "qwen3:4b")
            self.url = getattr(config, "LLM_URL", "http://127.0.0.1:11434")
            self.local_timeout = float(getattr(config, "LOCAL_LLM_TIMEOUT_SEC", 2.8))
            self.xai_model = getattr(config, "XAI_MODEL", "grok-4.7")
            self.xai_timeout = float(getattr(config, "XAI_API_TIMEOUT_SEC", 8))
            self.xai_key = os.environ.get("XAI_API_KEY") or getattr(config, "XAI_API_KEY", "")
            self.groq_model = getattr(config, "GROQ_MODEL", "openai/gpt-oss-20b")
            self.groq_timeout = float(getattr(config, "GROQ_API_TIMEOUT_SEC", 8))
            self.groq_key = os.environ.get("GROQ_API_KEY") or getattr(config, "GROQ_API_KEY", "")
        except Exception:
            cfg, self.model, self.url = False, "qwen3:4b", "http://127.0.0.1:11434"
            self.local_timeout, self.xai_model, self.xai_timeout, self.xai_key = 2.8, "grok-4.7", 8, ""
            self.groq_model, self.groq_timeout, self.groq_key = "openai/gpt-oss-20b", 8, ""
        self.enabled = (v.strip().lower() in ("1", "true", "yes", "on")) if v is not None else cfg
        self.error = None
        self.last_provider = "none"
        self.last_latency_ms = None
        self.local_error = None
        self.xai_key = str(self.xai_key or "").strip()
        self.xai_configured = bool(self.xai_key)
        self.groq_key = str(self.groq_key or "").strip()
        self.groq_configured = bool(self.groq_key)
        self._warm_thread = None
        self._warm_lock = threading.Lock()
        self._warming = False
        self._warm_started = False

    def prepare(self):
        """Warm Ollama in the background so the first farmer question avoids model-load delay."""
        if not self.enabled:
            return False
        with self._warm_lock:
            if self._warm_started:
                return True
            if not self.ready():
                return False
            self._warm_started = True
            self._warming = True
            self._warm_thread = threading.Thread(target=self._warm_local, name="ollama-warmup", daemon=True)
            self._warm_thread.start()
        return True

    def _warm_local(self):
        body = {"model": self.model, "stream": False, "think": False, "keep_alive": "30m",
                "options": {"temperature": 0, "num_predict": 1, "num_ctx": 512},
                "messages": [{"role": "system", "content": "Reply with OK."}, {"role": "user", "content": "OK"}]}
        try:
            req = urllib.request.Request(self.url + "/api/chat", data=json.dumps(body).encode("utf-8"),
                                         headers={"Content-Type": "application/json"})
            with urllib.request.urlopen(req, timeout=60) as r:
                r.read()
        except Exception:
            pass
        finally:
            self._warming = False

    def ready(self):
        if not self.enabled:
            return False
        try:
            with urllib.request.urlopen(self.url + "/api/tags", timeout=1.0) as r:
                names = [m.get("name", "") for m in json.loads(r.read()).get("models", [])]
            ok = any(n == self.model or n.startswith(self.model.split(":")[0] + ":") and self.model in n for n in names) or self.model in names
            self.local_error = None if ok else "Model '%s' is not pulled. Run: ollama pull %s" % (self.model, self.model)
            return ok
        except Exception as e:
            self.local_error = "Ollama is not running (%s)" % str(e)[:60]
            return False

    def _messages(self, question, facts, lang):
        system = SYSTEM.format(lang=NAMES.get(lang, "Hindi"), script=SCRIPTS.get(lang, "Devanagari"),
                               language_rule=LANGUAGE_RULES.get(lang, LANGUAGE_RULES["hi"]))
        user = "FACTS (JSON):\n" + json.dumps(_facts_for_question(facts, question), ensure_ascii=False) + "\n\nQUESTION:\n" + question
        return system, user

    @staticmethod
    def _clean_candidate(text):
        text = re.sub(r"<think>.*?</think>", "", str(text or ""), flags=re.S).strip()
        return text if text and safe(text) else None

    def _answer_xai(self, system, user):
        """Use xAI's documented Responses endpoint only after local timeout/failure."""
        body = {
            "model": self.xai_model,
            "instructions": system,
            "input": user,
            "max_output_tokens": 140,
            "reasoning_effort": "low",
            "store": False,
        }
        req = urllib.request.Request(
            "https://api.x.ai/v1/responses",
            data=json.dumps(body, ensure_ascii=False).encode("utf-8"),
            headers={"Content-Type": "application/json", "Authorization": "Bearer " + self.xai_key},
        )
        with urllib.request.urlopen(req, timeout=self.xai_timeout) as r:
            payload = json.loads(r.read())
        parts = []
        for item in payload.get("output", []):
            if item.get("type") == "message" or item.get("role") == "assistant":
                for content in item.get("content", []):
                    if content.get("type") == "output_text" and content.get("text"):
                        parts.append(content["text"])
        # Some compatible servers include an output_text convenience field.
        text = "\n".join(parts).strip() or str(payload.get("output_text", "")).strip()
        return self._clean_candidate(text)

    def _answer_groq(self, system, user):
        """Use Groq's OpenAI-compatible chat-completions endpoint."""
        body = {
            "model": self.groq_model,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            "temperature": 0.2,
            # GPT-OSS uses reasoning tokens from the same completion budget.
            # Low effort plus hidden reasoning preserves room for a short user-facing answer.
            "reasoning_effort": "low",
            "include_reasoning": False,
            "max_completion_tokens": 240,
            "stream": False,
        }
        req = urllib.request.Request(
            "https://api.groq.com/openai/v1/chat/completions",
            data=json.dumps(body, ensure_ascii=False).encode("utf-8"),
            headers={"Content-Type": "application/json", "Authorization": "Bearer " + self.groq_key,
                     "User-Agent": "AgriSahayak/1.0"},
        )
        with urllib.request.urlopen(req, timeout=self.groq_timeout) as r:
            payload = json.loads(r.read())
        choices = payload.get("choices") or []
        message = choices[0].get("message", {}) if choices else {}
        return self._clean_candidate(message.get("content", ""))

    def _translate(self, text, lang):
        """One short script/language correction pass when a model ignores the language request."""
        if lang not in NAMES:
            return None
        target = NAMES[lang]
        rule = LANGUAGE_RULES.get(lang, LANGUAGE_RULES["hi"])
        system = ("Translate the supplied answer into natural {target}, using {script} script. {rule} "
                  "Preserve its meaning without adding facts. Output only the translation in at most two short sentences. "
                  "Never add medicines, pesticide names, fertilizer names, doses, or quantities.").format(
                      target=target, script=SCRIPTS.get(lang, "Devanagari"), rule=rule)
        user = "ANSWER TO TRANSLATE:\n" + text
        translated = None
        if self.ready():
            body = {"model": self.model, "stream": False, "think": False, "keep_alive": "30m",
                    "options": {"temperature": 0.1, "num_predict": 120},
                    "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}]}
            try:
                req = urllib.request.Request(self.url + "/api/chat", data=json.dumps(body, ensure_ascii=False).encode("utf-8"),
                                             headers={"Content-Type": "application/json"})
                with urllib.request.urlopen(req, timeout=self.local_timeout) as r:
                    translated = self._clean_candidate(json.loads(r.read())["message"]["content"])
            except Exception:
                translated = None
        if translated and language_matches(translated, lang):
            return translated
        if self.groq_configured:
            try:
                translated = self._answer_groq(system, user)
                if translated and language_matches(translated, lang):
                    return translated
            except Exception:
                pass
        if self.xai_configured:
            try:
                translated = self._answer_xai(system, user)
                if translated and language_matches(translated, lang):
                    return translated
            except Exception:
                pass
        return None

    def _localized(self, text, lang):
        if not text or not safe(text):
            return None
        if language_matches(text, lang):
            return text
        return self._translate(text, lang)

    def answer(self, question, facts, lang):
        """Returns a safe answer text, or None (then the caller keeps the fixed answer)."""
        if not self.enabled:
            self.last_provider = "none"
            return None
        started = time.perf_counter()
        self.last_provider, self.last_latency_ms, self.error = "none", None, None
        system, user = self._messages(question, facts, lang)
        local_ready = self.ready()
        local_problem = self.local_error
        if local_ready:
            body = {"model": self.model, "stream": False, "think": False, "keep_alive": "30m",
                    "options": {"temperature": 0.2, "num_predict": 96, "num_ctx": 1024},
                    "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}]}
            try:
                req = urllib.request.Request(self.url + "/api/chat", data=json.dumps(body, ensure_ascii=False).encode("utf-8"),
                                             headers={"Content-Type": "application/json"})
                with urllib.request.urlopen(req, timeout=self.local_timeout) as r:
                    candidate = self._localized(json.loads(r.read())["message"]["content"], lang)
                if candidate:
                    self.last_provider = "local"
                    self.last_latency_ms = round((time.perf_counter() - started) * 1000)
                    return candidate
                local_problem = "Local answer was empty, unsafe, or did not match the requested language"
            except Exception as e:
                local_problem = "Local answer exceeded %.1f seconds or failed: %s" % (self.local_timeout, str(e)[:80])
        if self.groq_configured:
            try:
                candidate = self._localized(self._answer_groq(system, user), lang)
                if candidate:
                    self.last_provider = "groq"
                    self.last_latency_ms = round((time.perf_counter() - started) * 1000)
                    return candidate
                self.error = "Groq answer was empty or rejected by the safety/language filter"
            except Exception as e:
                code = getattr(e, "code", None)
                self.error = "Groq API request failed%s" % (" (HTTP %s)" % code if code else " or timed out")
        if self.xai_configured:
            try:
                candidate = self._localized(self._answer_xai(system, user), lang)
                if candidate:
                    self.last_provider = "xai"
                    self.last_latency_ms = round((time.perf_counter() - started) * 1000)
                    return candidate
                self.error = "xAI answer was empty or rejected by the safety/language filter"
            except Exception as e:
                code = getattr(e, "code", None)
                self.error = "xAI API request failed%s" % (" (HTTP %s)" % code if code else " or timed out")
        if not self.groq_configured and not self.xai_configured:
            self.error = local_problem or "Add a Groq or xAI API key to config.py to enable the online fallback"
        elif not self.error:
            self.error = local_problem or "The configured online model did not return a usable answer"
        self.last_latency_ms = round((time.perf_counter() - started) * 1000)
        return None

    def status(self):
        local_ready = self.ready() if self.enabled else False
        if local_ready and not self._warm_started:
            self.prepare()
        return {"enabled": self.enabled, "model": self.model,
                "ready": bool(local_ready or self.groq_configured or self.xai_configured),
                "local_ready": local_ready,
                "groq_configured": self.groq_configured, "groq_model": self.groq_model,
                "xai_configured": self.xai_configured, "xai_model": self.xai_model,
                "last_provider": self.last_provider, "last_latency_ms": self.last_latency_ms,
                "warming": self._warming,
                "error": self.error or (self.local_error if not local_ready and not self.groq_configured and not self.xai_configured else None)}
