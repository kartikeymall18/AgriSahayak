"""Fasal Saathi - the helper behind the voice and the chat. It answers ONLY from the saved scan records, the sensors
and the fixed advice sentences. It never invents medicines or doses, and it never speaks GPS coordinates.
Languages: Hindi, English, Bhojpuri (draft), Maithili (draft). All sentences live in voice/locale/*.json."""
import re
import advice
import support
from voice import i18n

HI_RE = re.compile(r"[\u0900-\u097F]")
BO_DEVA = {"रउआ", "रउरा", "बानी", "हमनी", "कइसे", "कइलीं", "कइल", "भइल", "बा", "बाड़े", "बाड़न", "लागेला", "चाहीं", "कहवाँ"}
MAI_DEVA = {"अहाँ", "अहाँक", "हमर", "हमरा", "अछि", "छी", "छियै", "करैत", "कतए", "केहन", "कोना", "कतेक", "नहि", "नहिं"}
ROMAN_HI = {
    "aap", "ap", "tum", "hum", "mai", "main", "mera", "meri", "mujhe", "ham", "hain", "ho", "hai", "tha", "thi",
    "kya", "kyu", "kyun", "kaise", "kaisa", "kaisi", "kab", "kahan", "kitna", "kitni", "kitne", "ka", "ke", "ki",
    "ko", "se", "mein", "nahi", "nahin", "batao", "bataye", "batayiye", "karo", "karu", "karun", "kare", "kya",
    "fasal", "kheti", "mitti", "pani", "paanee", "rog", "bimari", "bimar", "aloo", "aaloo", "tamatar", "mirchi",
    "namaste", "pranam", "dhanyavaad", "kripya", "chahiye", "accha", "acha", "kitna", "rauwa", "ba", "bani"
}
ROMAN_BHO = {"rauwa", "raura", "baani", "hamni", "kaile", "bhail", "kaisan", "baate", "baade", "chaheen", "kahela", "kaileba"}
ROMAN_MAI = {"ahan", "ahank", "hamar", "hamra", "achhi", "chhi", "chhiyai", "karait", "katae", "katek", "kena", "kona"}


def requested_reply_language(text):
    """Return a language only when the user explicitly asks for the answer in it."""
    s = str(text or "")
    low = s.lower()
    requested = (
        ("bho", r"\bbhojpuri\b|भोजपुरी"),
        ("mai", r"\bmaithili\b|मैथिली|मैथिली"),
        ("hi", r"\bhindi\b|हिंदी|हिन्दी"),
        ("en", r"\benglish\b|अंग्रेजी|अंग्रेज़ी"),
    )
    command = bool(re.search(
        r"\b(reply|answer|respond|report|explain|translate|write|tell|give)\b|"
        r"जवाब|उत्तर|रिपोर्ट|लिखो|अनुवाद",
        low, re.I))
    # A bare mention such as "I speak Hindi" is not a reply-language instruction.
    # Accept "speak/say in Hindi" only when it clearly describes the requested output.
    command = command or bool(re.search(
        r"^\s*(?:please\s+)?(?:speak|say)\s+(?:(?:in|using)\s+)?(?:hindi|english|bhojpuri|maithili)\b|"
        r"\b(?:speak|say)\s+(?:in|using)\s+|"
        r"\b(?:in|using)\s+\w+\s+(?:please\s+)?(?:reply|answer|report|speak|say)\b",
        low, re.I))
    command = command or bool(re.search(
        r"(?:हिंदी|हिन्दी|भोजपुरी|मैथिली|अंग्रेज़ी|अंग्रेजी)\s*(?:में|मे)\s*"
        r"(?:जवाब|उत्तर|रिपोर्ट|लिख|बता|बोल|कह|दो|दीजिए|दें)|"
        r"(?:hindi|english|bhojpuri|maithili)\s+(?:me|mein)\s+"
        r"(?:reply|answer|report|batao|bataiye|bolo|likho|jawab|do)\b",
        low, re.I))
    if command:
        for code, pattern in requested:
            if re.search(pattern, low, re.I):
                return code
    return None


def detect_language(text):
    """Choose a requested language first, otherwise infer from script and vocabulary."""
    s = str(text or "")
    low = s.lower()
    explicit = requested_reply_language(s)
    if explicit:
        return explicit
    words = set(re.findall(r"[a-z]+", s.lower()))
    deva_words = set(re.findall(r"[\u0900-\u0963\u0965-\u097F]+", s))
    bho_phrase = re.search(r"\b(?:ka|ke)\s+ha\b|\bka\s+ba\b", s.lower())
    if words & ROMAN_BHO or deva_words & BO_DEVA or bho_phrase:
        return "bho"
    if words & ROMAN_MAI or deva_words & MAI_DEVA:
        return "mai"
    if HI_RE.search(s):
        return "hi"
    return "hi" if words & ROMAN_HI else "en"

# words that trigger each intent: English, Hindi, Bhojpuri / Maithili, and Hindi typed in English letters
K = {
    "photo": ["take a photo", "take photo", "take a picture", "click photo", "capture", "photo lo", "फोटो ले", "फोटो खींच", "फ़ोटो ले", "फोटो लीं", "फोटो लिय", "फोटो ल ", "tasveer", "photo kheench"],
    "cam_on": ["start camera", "camera on", "turn on camera", "कैमरा चालू", "कैमरा खोल", "camera chalu"],
    "cam_off": ["stop camera", "camera off", "turn off camera", "कैमरा बंद", "कैमरा बन्द", "camera band"],
    "pump": ["pump on", "start pump", "start the pump", "turn on the pump", "run the pump", "पंप चालू", "पम्प चालू", "पंप चला", "पम्प चला", "पंप शुरू", "pump chalu", "pump chala"],
    "advice": ["what should i do", "what to do", "treat", "cure", "medicine", "spray", "remedy", "इलाज", "दवा", "क्या करूं", "क्या करूँ", "क्या करें", "उपाय", "का करीं", "का करे", "की करी", "करबाक", "ilaj", "dawai", "dawa", "upay", "kya karu", "kya karun", "kya karen"],
    "problem": ["disease", "problem", "sick", "infect", "unhealthy", "diseased", "बीमार", "रोग", "दिक्कत", "खराब", "समस्या", "बेमारी", "बेमार", "बिमारी", "bimari", "bimar", "rog", "dikkat", "samasya"],
    "weather": ["temperature", "humidity", "weather", "तापमान", "आर्द्रता", "मौसम", "हवा की नमी", "हवा के नमी", "tapman", "temp "],
    "soil": ["soil", "moisture", "water", "irrigat", "wet", "dry", "मिट्टी", "माटी", "माटि", "नमी", "पानी", "पानि", "सिंचाई", "mitti", "nami", "pani", "sinchai"],
    "count": ["how many", "count", "total", "number of", "कितने", "कितनी", "कितना", "केतना", "केतने", "कतेक", "कतना", "गिन", "kitne", "kitni"],
    "where": ["where", "location", "place", "map", "कहाँ", "कहां", "कहवाँ", "कतए", "जगह", "नक्शा", "लोकेशन", "kahan", "kaha", "jagah", "naksha"],
    "latest": ["latest", "last", "recent", "newest", "current", "आखिरी", "आख़िरी", "अंतिम", "अन्तिम", "पिछला", "ताज़ा", "ताजा", "अभी", "अबहीं", "akhiri", "pichla", "taza", "abhi"],
    "summary": ["summary", "report", "overall", "status", "everything", "सारांश", "रिपोर्ट", "हाल", "सब कुछ", "सब कछु", "halchal", "haal", "sab kuch"],
    "greet": ["hello", "hi", "hey", "help", "namaste", "pranam", "नमस्ते", "नमस्कार", "प्रणाम", "मदद", "madad", "who are you", "आप कौन", "तुम कौन", "रउआ के"],
}
ORDER = ["photo", "cam_on", "cam_off", "pump", "advice", "problem", "weather", "soil", "count", "where", "latest", "summary", "greet"]
PRODUCE_TERMS = ("potato", "potatoes", "aloo", "aaloo", "आलू", "tomato", "tomatoes", "tamatar", "टमाटर",
                 "chilli", "chili", "mirchi", "मिर्च", "bell pepper", "capsicum", "शिमला मिर्च", "apple", "apples", "सेब",
                 "cherry", "cherries", "चेरी", "fig", "figs", "अंजीर", "olive", "olives", "जैतून", "pomegranate", "अनार",
                 "orange", "oranges", "संतरा", "rockmelon", "cantaloupe", "खरबूजा", "strawberry", "strawberries", "स्ट्रॉबेरी",
                 "watermelon", "तरबूज")
VISION_TERMS = ("count", "identify", "recognize", "recognise", "detect", "see", "model", "camera", "photo", "scan",
                "can it", "can the", "does it", "support", "गिन", "पहचान", "देख", "मॉडल", "कैमरा", "फोटो")
SUPPORT_TERMS = ("scheme", "government", "govt", "loan", "credit", "subsidy", "benefit", "financial help", "farmer support",
                 "agriculture officer", "field officer", "kisan call", "crop insurance", "crop loss", "सरकारी योजना", "योजना",
                 "कर्ज", "कर्जा", "ऋण", "सब्सिडी", "सरकारी मदद", "कृषि अधिकारी", "किसान सहायता", "बीमा", "मुआवजा")
PRODUCE_CONDITION_TERMS = ("healthy", "unhealthy", "rotten", "spoiled", "fresh", "diseased", "disease", "health", "सड़ा", "सड़ी", "सड़ी", "ताजा", "ताज़ा", "स्वस्थ", "खराब", "बीमारी", "रोग")
PRODUCE_CONDITION_REPLIES = {
    "en": "I can screen tomato fruit images for a broad healthy-looking versus possible-issue result. It cannot name a tomato fruit disease, confirm freshness, or replace the separate leaf-disease model. Other supported produce is detected and counted only.",
    "hi": "मैं टमाटर के फल की तस्वीर में स्वस्थ-जैसा या संभावित समस्या का सामान्य स्क्रीन कर सकता हूँ। यह किसी खास फल-रोग की पुष्टि नहीं करता और पत्ती के अलग रोग-मॉडल की जगह नहीं लेता। अन्य समर्थित फल-सब्ज़ियों की केवल पहचान और गिनती होती है।",
    "bho": "हम टमाटर के फल के फोटो में स्वस्थ-जइसन भा संभावित दिक्कत के सामान्य जाँच कर सकेनी। ई कवनो खास फल-रोग के पक्का नाम ना बतावेला आ पत्ता वाला अलग मॉडल के जगह ना लेला। बाकी समर्थित फल-सब्जी के खाली पहचान आ गिनती होला।",
    "mai": "हम टमाटर फलके तस्वीरमे स्वस्थ-जेकाँ वा संभावित समस्या देखबाक सामान्य स्क्रीनिंग कऽ सकैत छी। ई खास फल-रोगक पुष्टि नहि करैत अछि आ पातक अलग रोग-मॉडलके स्थान नहि लैत अछि। दोसर समर्थित फल-सब्जीक केवल पहचान आ गिनती होइत अछि।",
}
TOMATO_HEALTH_REPLIES = {
    "en": "Tomato photo screen: {summary}. This prototype screens the image as a whole, not each fruit separately, and does not name a disease. Inspect the fruit and ask an agriculture specialist if unsure.",
    "hi": "टमाटर फोटो स्क्रीन: {summary}। यह प्रोटोटाइप पूरी तस्वीर की जाँच करता है, हर फल की अलग-अलग नहीं, और किसी खास रोग का नाम नहीं बताता। संदेह हो तो कृषि विशेषज्ञ से पूछें।",
    "bho": "टमाटर फोटो के स्क्रीन: {summary}। ई प्रोटोटाइप पूरा फोटो के जाँचे ला, हर फल के अलग-अलग ना, आ खास रोग के नाम ना बतावेला। शंका होखे त कृषि विशेषज्ञ से पूछीं।",
    "mai": "टमाटर फल स्क्रीनिंग: {summary}। ई प्रोटोटाइप पूरा तस्वीरकेँ जाँचैत अछि, प्रत्येक फलकेँ अलग नहि, आ खास रोगक नाम नहि बतबैत अछि। शंका भए त कृषि विशेषज्ञसँ पूछू।",
}
TOMATO_HEALTH_WORDS = {
    "en": {"healthy": "likely healthy-looking", "possible_disease": "possible issue", "uncertain": "unclear"},
    "hi": {"healthy": "स्वस्थ-जैसा", "possible_disease": "संभावित समस्या", "uncertain": "स्पष्ट नहीं"},
    "bho": {"healthy": "स्वस्थ-जइसन", "possible_disease": "संभावित दिक्कत", "uncertain": "साफ नइखे"},
    "mai": {"healthy": "स्वस्थ-जेकाँ", "possible_disease": "संभावित समस्या", "uncertain": "स्पष्ट नहि"},
}
PRODUCE_MATURITY_TERMS = ("mature", "maturity", "ripe", "ripeness", "unripe", "ripen",
                          "पक", "पका", "पकी", "परिपक्व", "पकाव")
TOMATO_STAGE_NAMES = {
    "en": {"mostly_green": "mostly green", "turning": "turning color", "mostly_red": "mostly red", "uncertain": "unclear"},
    "hi": {"mostly_green": "मुख्यतः हरा", "turning": "रंग बदलता हुआ", "mostly_red": "मुख्यतः लाल", "uncertain": "स्पष्ट नहीं"},
    "bho": {"mostly_green": "अधिकतर हरियर", "turning": "रंग बदलत", "mostly_red": "अधिकतर लाल", "uncertain": "साफ नइखे"},
    "mai": {"mostly_green": "अधिकांश हरियर", "turning": "रंग बदलैत", "mostly_red": "अधिकांश लाल", "uncertain": "स्पष्ट नहि"},
}
TOMATO_MATURITY_REPLIES = {
    "en": "Latest tomato color-stage estimate: {stage}. This is only a rough surface-color cue; it cannot confirm maturity, freshness, or disease.",
    "hi": "पिछली तस्वीर में टमाटर के रंग-चरण का अनुमान: {stage}। यह केवल सतह के रंग का मोटा संकेत है; इससे परिपक्वता, ताज़गी या बीमारी की पुष्टि नहीं होती।",
    "bho": "पिछला तस्वीर में टमाटर के रंग-चरण के मोटा अनुमान बा: {stage}। ई खाली सतह के रंग के संकेत ह; एहसे पकाव, ताजगी भा बेमारी पक्का ना होखेला।",
    "mai": "पछिला तस्वीरमे टमाटरक रंग-चरणक मोट अनुमान: {stage}। ई केवल सतहक रंगक संकेत अछि; एहि सँ परिपक्वता, ताजगी वा रोग निश्चित नहि होइत अछि।",
}
TOMATO_MATURITY_NONE = {
    "en": "I do not have a tomato color-stage estimate yet. Centre one tomato in good light and take a photo. Color alone cannot confirm maturity or health.",
    "hi": "अभी टमाटर के रंग-चरण का अनुमान उपलब्ध नहीं है। अच्छी रोशनी में एक टमाटर को बीच में रखकर फोटो लें। केवल रंग से परिपक्वता या स्वास्थ्य की पुष्टि नहीं होती।",
    "bho": "अभी टमाटर के रंग-चरण के अनुमान नइखे। बढ़िया रोशनी में एगो टमाटर बीच में रख के फोटो लीं। खाली रंग से पकाव भा सेहत पक्का ना होखेला।",
    "mai": "एखन टमाटरक रंग-चरणक अनुमान नहि अछि। नीक रोशनीमे एकटा टमाटर बीचमे राखि फोटो लिअ। केवल रंग सँ परिपक्वता वा स्वास्थ्य निश्चित नहि होइत अछि।",
}


def detect(text):
    t = " " + re.sub(r"\s+", " ", (text or "").lower().strip()) + " "
    # A crop vision-capability question belongs to the LLM's model-capability facts,
    # not the saved-record count intent ("can it count potatoes?" is not "how many scans?").
    raw = (text or "").lower()
    asks_about_leaf = any(term in raw for term in ("leaf", "leaves", "plant", "पत्ता", "पत्ते", "पत्ती", "पौधा", "पौधे"))
    if any(term in raw for term in PRODUCE_TERMS) and (any(term in raw for term in PRODUCE_CONDITION_TERMS) or
            any(term in raw for term in PRODUCE_MATURITY_TERMS)) and not asks_about_leaf:
        return "produce_condition"
    if any(term in raw for term in SUPPORT_TERMS):
        return "support"
    if any(term in raw for term in PRODUCE_TERMS) and any(term in raw for term in VISION_TERMS):
        return "unknown"
    # A greeting is an intent only when the whole utterance is a greeting/help
    # prompt. Matching "hey" anywhere swallowed questions such as "hey potato kya hai?"
    # before they could reach the LLM.
    greeting_text = re.sub(r"[^\w\s]", " ", (text or "").lower(), flags=re.UNICODE)
    greeting_text = " ".join(greeting_text.split())
    greetings = {" ".join(re.sub(r"[^\w\s]", " ", w.lower(), flags=re.UNICODE).split()) for w in K["greet"]}
    for intent in ORDER:
        for w in K[intent]:
            if intent == "greet":
                if greeting_text in greetings:
                    return intent
                continue
            if re.fullmatch(r"[a-z]{1,4}", w):                  # short English words must match as whole words
                if re.search(r"\b" + re.escape(w) + r"\b", t):
                    return intent
            elif w in t:
                return intent
    return None


def facts_from(views):
    """views = record views, newest first. These are the facts every answer is built from."""
    ph = [v for v in views if v.get("kind") == "photo"]
    scored = [v for v in ph if (v.get("result") or {}).get("label") and
              (v.get("result") or {}).get("status") != "produce"]
    seen, per_plant = set(), []
    for v in scored:                                           # newest scan of each plant
        key = (v.get("field"), v.get("plot"))
        if key not in seen:
            seen.add(key)
            per_plant.append(v)
    healthy = [v for v in scored if not v["result"].get("reasons") and v["result"]["category"] == "healthy"]
    sick = [v for v in per_plant if not v["result"].get("reasons") and v["result"]["category"] != "healthy"]
    review = [v for v in scored if v["result"].get("reasons")]
    return {"photos": ph, "scored": scored, "per_plant": per_plant, "healthy": healthy, "sick": sick, "review": review}


def _name(v, lang):
    return advice.label_hi(v["result"]["label"]) if lang != "en" else advice.pretty(v["result"]["label"]).replace(" - ", ", ")


def answer(text, lang, views, soil, summary_fn, sens=None, farm_profile=None):
    """Returns {"reply", "lang", "intent", "action"}. action is one of photo, camera_on, camera_off, pump."""
    explicit_lang = requested_reply_language(text)
    if explicit_lang:
        lang = explicit_lang
    elif lang not in i18n.LANGS:
        lang = detect_language(text)
    T = lambda key, **kw: i18n.T(lang, key, **kw)
    intent = detect(text or "")
    f = facts_from(views)
    sens = sens or {}
    out = {"lang": lang, "intent": intent or "unknown", "action": None}

    if intent == "produce_condition":
        raw_text = str(text or "").lower()
        asks_tomato = any(term in raw_text for term in ("tomato", "tomatoes", "टमाटर", "टोमेटो"))
        latest_tomato = next((v for v in f["photos"] if
                              (v.get("result") or {}).get("status") == "produce" and
                              any("tomato" in str(name).lower() for name in
                                  (v.get("result") or {}).get("produce_counts", {}))), None)
        latest_result = (latest_tomato or {}).get("result") or {}
        if any(term in raw_text for term in PRODUCE_CONDITION_TERMS) and not any(
                term in raw_text for term in PRODUCE_MATURITY_TERMS):
            if not asks_tomato:
                out["reply"] = PRODUCE_CONDITION_REPLIES.get(lang, PRODUCE_CONDITION_REPLIES["en"])
            else:
                screen = latest_result.get("tomato_sample_screen") or {}
                words = TOMATO_HEALTH_WORDS.get(lang, TOMATO_HEALTH_WORDS["en"])
                summary = words.get(screen.get("status"), "unclear")
                if latest_result.get("tomato_screen_available"):
                    out["reply"] = TOMATO_HEALTH_REPLIES.get(lang, TOMATO_HEALTH_REPLIES["en"]).format(
                        summary=summary)
                elif latest_tomato and screen.get("status") == "uncertain":
                    out["reply"] = TOMATO_HEALTH_REPLIES.get(lang, TOMATO_HEALTH_REPLIES["en"]).format(
                        summary=words.get("uncertain", "unclear"))
                elif latest_tomato:
                    out["reply"] = PRODUCE_CONDITION_REPLIES.get(lang, PRODUCE_CONDITION_REPLIES["en"])
                else:
                    out["reply"] = TOMATO_HEALTH_REPLIES.get(lang, TOMATO_HEALTH_REPLIES["en"]).format(
                        summary={"en": "no tomato-fruit scan is available yet", "hi": "अभी टमाटर फल का स्कैन उपलब्ध नहीं है",
                                 "bho": "अभी टमाटर फल के स्कैन नइखे", "mai": "एखन टमाटर फल स्कैन उपलब्ध नहि अछि"}.get(lang, "no scan available"))
        elif any(term in raw_text for term in PRODUCE_MATURITY_TERMS):
            stage_counts = (latest_tomato.get("result") or {}).get("tomato_color_stages", {}) if latest_tomato else {}
            stage_names = TOMATO_STAGE_NAMES.get(lang, TOMATO_STAGE_NAMES["en"])
            stage_text = ", ".join("%s: %s" % (stage_names.get(k, k), count)
                                   for k, count in stage_counts.items())
            if stage_text:
                out["reply"] = TOMATO_MATURITY_REPLIES.get(lang, TOMATO_MATURITY_REPLIES["en"]).format(stage=stage_text)
            else:
                out["reply"] = TOMATO_MATURITY_NONE.get(lang, TOMATO_MATURITY_NONE["en"])
        else:
            out["reply"] = PRODUCE_CONDITION_REPLIES.get(lang, PRODUCE_CONDITION_REPLIES["en"])
        return out

    if intent == "support":
        latest = f["scored"][0] if f["scored"] else None
        latest_name = latest.get("name", "") if latest else ""
        profile = farm_profile if isinstance(farm_profile, dict) else {}
        crop = support.detect_crop(text) or str(profile.get("crop", "")).strip() or support.detect_crop(latest_name)
        result = support.recommend(crop=crop, district=profile.get("district", ""),
                                  cultivator=profile.get("cultivator", ""),
                                  field_details=profile.get("field_details", ""),
                                  issue=text, latest_result=latest_name)
        out["reply"] = support.reply(result, lang)
        out["support_recommendations"] = [
            {"id": x["id"], "name": x["name"], "url": x["url"], "reason": x["reason"]}
            for x in result["recommendations"]
        ]
        return out

    if intent in ("photo", "cam_on", "cam_off", "pump"):
        out["action"] = {"photo": "photo", "cam_on": "camera_on", "cam_off": "camera_off", "pump": "pump"}[intent]
        out["reply"] = T({"photo": "photo", "cam_on": "cam_on", "cam_off": "cam_off", "pump": "pump_on"}[intent])
        return out

    if intent == "greet":
        out["reply"] = T("greet")
        return out

    if intent == "weather":
        t, h = sens.get("temp"), sens.get("hum")
        out["reply"] = T("weather_value", t=round(t), h=round(h)) if t is not None and h is not None else T("weather_none")
        return out

    if intent == "soil":
        if soil is None:
            out["reply"] = T("soil_none")
        else:
            out["reply"] = T("soil_value", v=round(soil)) + advice.soil_text(advice.soil_state(soil), lang)
        return out

    if intent == "where":
        out["reply"] = T("where")
        return out

    if not f["scored"] and intent in ("latest", "problem", "count", "advice", "summary", None):
        out["reply"] = T("no_scans_count") if intent == "count" else T("no_scans")
        if intent is None:
            out["reply"] = T("sorry") + T("unknown")
        return out

    if intent == "latest":
        v = f["scored"][0]
        r = v["result"]
        s = T("latest", name=_name(v, lang), pct=round(r["confidence"] * 100))
        if r.get("reasons"):
            s += " " + advice.review_text(lang)
        st = advice.soil_state(v.get("soil"))
        if st:
            s += " " + advice.soil_text(st, lang)
        out["reply"] = s
        return out

    if intent == "problem":
        sick = f["sick"]
        if not sick:
            out["reply"] = T("disease_none") + (T("review_count", n=len(f["review"])) if f["review"] else "")
        else:
            items = "; ".join("%s: %s" % (advice.plant_hi(v.get("plot", ""), lang) if lang != "en" else v.get("plot", ""), _name(v, lang)) for v in sick[:3])
            out["reply"] = T("disease_found", n=len(sick), items=items)
        return out

    if intent == "count":
        out["reply"] = T("count", n=len(f["scored"]), h=len(f["healthy"]), d=len(f["sick"]), r=len(f["review"]))
        return out

    if intent == "advice":
        v = (f["sick"] or f["scored"])[0]
        r = v["result"]
        out["reply"] = advice.review_text(lang) if r.get("reasons") else T("advice_for", name=_name(v, lang)) + advice.cat_text(r["category"], lang)
        return out

    if intent == "summary":
        out["reply"] = summary_fn(lang)
        return out

    out["reply"] = T("sorry") + T("unknown")
    return out
