import re
from voice import i18n
import config

CATS = {
    "healthy": {
        "en": "The leaf looks healthy. No treatment is needed. Keep regular watering and checking.",
        "hi": "पत्ता स्वस्थ दिख रहा है। किसी इलाज की ज़रूरत नहीं है। नियमित पानी और जाँच जारी रखें।"},
    "fungal": {
        "en": "This is probably a fungal disease. Remove badly affected leaves and dispose of them safely, avoid watering from above, improve air flow between plants, and ask your local agriculture officer which medicine and how much to use.",
        "hi": "यह संभवतः फफूंद से होने वाला रोग है। ज़्यादा प्रभावित पत्तों को हटाकर सुरक्षित तरीके से नष्ट करें, ऊपर से पानी देने से बचें, पौधों के बीच हवा आने-जाने दें, और कौन सी दवा कितनी डालनी है यह अपने स्थानीय कृषि अधिकारी से पूछें।"},
    "bacterial": {
        "en": "This is probably a bacterial disease. Remove affected leaves, do not touch healthy plants after touching sick ones, avoid watering from above, and ask your local agriculture officer for a suitable treatment.",
        "hi": "यह संभवतः जीवाणु से होने वाला रोग है। प्रभावित पत्ते हटाएँ, बीमार पौधे छूने के बाद स्वस्थ पौधों को न छुएँ, ऊपर से पानी देने से बचें, और सही इलाज के लिए स्थानीय कृषि अधिकारी से पूछें।"},
    "viral": {
        "en": "This is probably a virus disease. Virus diseases cannot be cured. Remove and destroy the infected plant if there are only a few, control insects like whiteflies and aphids that spread it, and ask your local agriculture officer.",
        "hi": "यह संभवतः विषाणु (वायरस) से होने वाला रोग है। इसका कोई इलाज नहीं है। अगर संक्रमित पौधे कम हों तो उन्हें हटाकर नष्ट करें, सफ़ेद मक्खी और माहू जैसे कीड़ों को रोकें, और अपने स्थानीय कृषि अधिकारी से पूछें।"},
    "pest": {
        "en": "This looks like mite damage. Check the underside of the leaves, spray the plant with a strong stream of water, and ask your local agriculture officer for a suitable treatment.",
        "hi": "यह माइट (कुटकी) कीट का नुकसान लगता है। पत्तों के नीचे की तरफ़ देखें, पौधे पर पानी की तेज़ धार डालें, और सही इलाज के लिए स्थानीय कृषि अधिकारी से पूछें।"},
}
SOIL = {
    "dry": {"en": "The soil is dry. Water the plant.", "hi": "मिट्टी सूखी है। पौधे को पानी दें।"},
    "ok": {"en": "Soil moisture is fine.", "hi": "मिट्टी में नमी ठीक है।"},
    "wet": {"en": "The soil is very wet. Do not water now and check that water can drain.",
            "hi": "मिट्टी बहुत गीली है। अभी पानी न दें और जाँचें कि पानी निकल पा रहा है।"},
}
REVIEW = {"en": "I am not sure about this result. Please check the plant by eye or take a clearer photo.",
          "hi": "मुझे इस नतीजे पर पक्का भरोसा नहीं है। कृपया पौधे को खुद देखें या साफ़ फोटो लें।"}
MISMATCH = {"en": "The crop name you entered does not match the photo.",
            "hi": "आपने जो फसल का नाम डाला है वह फोटो से मेल नहीं खाता।"}


def categorize(label):
    l = label.lower()
    if "healthy" in l:
        return "healthy"
    if "virus" in l or "mosaic" in l or "curl" in l:
        return "viral"
    if "mite" in l:
        return "pest"
    if "bacterial" in l or "huanglongbing" in l or "greening" in l:
        return "bacterial"
    return "fungal"


def pretty(label):
    s = label.replace("___", " - ").replace("__", " ").replace("_", " ")
    return re.sub(r"\s+", " ", s).strip()


def crop_of(label):
    """Crop name taken from the model's label, e.g. 'Tomato___Early_blight' -> 'Tomato'."""
    c = (label or "").split("___")[0].replace("_", " ")
    return re.sub(r"\s+", " ", c).strip() or "Unknown"


# Hindi names for the 14 crops and the common conditions, so the Hindi voice does not have to spell out English words.
# First version: please ask a native speaker or an agriculture officer to check these words.
CROP_HI = {"apple": "सेब", "blueberry": "ब्लूबेरी", "cherry": "चेरी", "corn": "मक्का", "grape": "अंगूर", "orange": "संतरा",
           "peach": "आड़ू", "pepper": "शिमला मिर्च", "potato": "आलू", "raspberry": "रसभरी", "soybean": "सोयाबीन",
           "squash": "कद्दू", "strawberry": "स्ट्रॉबेरी", "tomato": "टमाटर"}
COND_HI = [("healthy", "स्वस्थ"), ("early blight", "अगेती झुलसा"), ("late blight", "पछेती झुलसा"), ("bacterial spot", "जीवाणु धब्बा रोग"),
           ("septoria", "सेप्टोरिया पत्ती धब्बा"), ("leaf mold", "पत्ती फफूंद"), ("target spot", "टारगेट स्पॉट रोग"),
           ("mosaic", "मोज़ेक वायरस"), ("yellow leaf curl", "पत्ती मरोड़ वायरस"), ("spider mite", "माइट कीट"),
           ("powdery mildew", "चूर्णिल आसिता रोग"), ("common rust", "सामान्य रतुआ रोग"), ("cedar apple rust", "रतुआ रोग"),
           ("northern leaf blight", "उत्तरी पर्ण झुलसा"), ("gray leaf spot", "धूसर पत्ती धब्बा"), ("cercospora", "धूसर पत्ती धब्बा"),
           ("black rot", "काला सड़न रोग"), ("esca", "एस्का रोग"), ("leaf blight", "पत्ती झुलसा"), ("apple scab", "पपड़ी रोग"), ("scab", "पपड़ी रोग"),
           ("leaf scorch", "पत्ती झुलसन"), ("haunglongbing", "सिट्रस ग्रीनिंग रोग"), ("citrus greening", "सिट्रस ग्रीनिंग रोग")]


def label_hi(label):
    """Hindi version of a model label, e.g. 'Tomato___Early_blight' -> 'टमाटर, अगेती झुलसा'."""
    crop = crop_of(label)
    cl = crop.lower()
    crop_hi = next((v for k, v in CROP_HI.items() if k in cl), crop)
    cond = pretty(label).split(" - ", 1)[1] if " - " in pretty(label) else ""
    low = cond.lower()
    cond_hi = next((v for k, v in COND_HI if k in low), cond)
    return crop_hi + (", " + cond_hi if cond_hi else "")


def plant_hi(plot, lang="hi"):
    return (plot or "").replace("Plant ", i18n.T(lang, "plant_word") + " ")


def norm(s):
    return re.sub(r"[^a-z0-9]", "", s.lower())


def crop_match(crop, label):
    words = [norm(w) for w in re.split(r"\s+", crop.strip()) if w]
    ln = norm(label)
    return all(w in ln for w in words) if words else True


def soil_state(v):
    if v is None:
        return None
    if v < config.SOIL_DRY_BELOW:
        return "dry"
    if v > config.SOIL_WET_ABOVE:
        return "wet"
    return "ok"


def cat_text(cat, lang):
    """Fixed advice sentence for a category in en / hi / bho / mai (Bhojpuri and Maithili are drafts)."""
    return i18n.get(lang, "adv_" + cat) or CATS[cat]["en" if lang == "en" else "hi"]


def soil_text(state, lang):
    return i18n.get(lang, "soil_" + state) or SOIL[state]["en" if lang == "en" else "hi"]


def review_text(lang):
    return i18n.get(lang, "review") or REVIEW["en" if lang == "en" else "hi"]


def speech_text(rec, lang):
    """What the voice says after a scan. The place (field, plant number, GPS) is NEVER spoken."""
    lang = lang if lang in i18n.LANGS else "hi"
    hi = lang != "en"
    if rec.get("kind") == "video":
        return i18n.T(lang, "video_saved")
    r = rec.get("result") or {}
    parts = []
    if r.get("status") == "no_model":
        parts.append(i18n.T(lang, "no_model"))
    elif r.get("status") == "not_plant":
        if r.get("scene") == "hand":
            parts.append("कैमरे में हाथ दिख रहा है; पत्ती या फल-सब्ज़ी को बीच में रखें।" if hi else "A hand is visible; centre a leaf or supported produce in the camera.")
        elif r.get("scene") == "person":
            parts.append("कैमरे में व्यक्ति दिख रहा है; पत्ती या फल-सब्ज़ी को बीच में रखें।" if hi else "A person is visible; centre a leaf or supported produce in the camera.")
        else:
            parts.append(i18n.T(lang, "not_plant"))
    elif r.get("status") == "produce":
        counts = r.get("produce_counts") or {}
        stage_counts = r.get("tomato_color_stages") or {}
        sample_screen = r.get("tomato_sample_screen") or {}
        if r.get("tomato_screen_available"):
            screen_words = {
                "en": {"healthy": "likely healthy-looking", "possible_disease": "possible issue"},
                "hi": {"healthy": "स्वस्थ-जैसा", "possible_disease": "संभावित समस्या"},
                "bho": {"healthy": "स्वस्थ-जइसन", "possible_disease": "संभावित दिक्कत"},
                "mai": {"healthy": "स्वस्थ-जेकाँ", "possible_disease": "संभावित समस्या"},
            }.get(lang, {})
            result_word = screen_words.get(sample_screen.get("status"), "unclear")
            if lang == "en": parts.append("Tomato photo screen: %s. This prototype screens the image as a whole, not each fruit separately, and does not name a disease." % result_word)
            elif lang == "bho": parts.append("टमाटर फोटो के स्क्रीन: %s। ई प्रोटोटाइप पूरा फोटो के जाँचे ला, हर फल के अलग-अलग ना, आ खास रोग के नाम ना बतावेला।" % result_word)
            elif lang == "mai": parts.append("टमाटर फल स्क्रीनिंग: %s। ई प्रोटोटाइप पूरा तस्वीरकेँ जाँचैत अछि, प्रत्येक फलकेँ अलग नहि, आ खास रोगक नाम नहि बतबैत अछि।" % result_word)
            else: parts.append("टमाटर फोटो स्क्रीन: %s। यह प्रोटोटाइप पूरी तस्वीर की जाँच करता है, हर फल की अलग-अलग नहीं, और किसी खास रोग का नाम नहीं बताता।" % result_word)
        elif any(str(k).lower() == "tomato" for k in counts):
            parts.append("टमाटर फल का स्वास्थ्य स्क्रीन उपलब्ध नहीं है।" if lang == "hi" else "Tomato fruit health screen is unavailable.")
        else:
            parts.append("Other produce is detected and counted only; no health screen is available for it." if lang == "en" else
                          "अन्य फल-सब्ज़ियों की केवल पहचान और गिनती होती है; उनका स्वास्थ्य स्क्रीन उपलब्ध नहीं है।")
        items = []
        for crop, count in counts.items():
            crop_name = pretty(crop)
            if lang != "en":
                normalized = crop_name.lower().replace("-", " ")
                crop_name = next((value for key, value in CROP_HI.items() if key in normalized), crop_name)
            items.append("%s: %s" % (crop_name, count))
        listing = ", ".join(items) or pretty(r.get("label", "produce"))
        stage_words = {
            "en": {"mostly_green": "mostly green", "turning": "turning color", "mostly_red": "mostly red", "uncertain": "unclear"},
            "hi": {"mostly_green": "मुख्यतः हरा", "turning": "रंग बदलता हुआ", "mostly_red": "मुख्यतः लाल", "uncertain": "स्पष्ट नहीं"},
            "bho": {"mostly_green": "अधिकतर हरियर", "turning": "रंग बदलत", "mostly_red": "अधिकतर लाल", "uncertain": "साफ नइखे"},
            "mai": {"mostly_green": "अधिकांश हरियर", "turning": "रंग बदलैत", "mostly_red": "अधिकांश लाल", "uncertain": "स्पष्ट नहि"},
        }.get(lang, {})
        stage_listing = ", ".join("%s: %s" % (stage_words.get(k, k), v) for k, v in stage_counts.items())
        if lang == "en":
            parts.append("Detected produce: %s. Object boxes and counts are estimates." % listing)
            if stage_listing:
                parts.append("Tomato surface-color stage estimate: %s; color alone cannot confirm maturity." % stage_listing)
        elif lang == "bho":
            parts.append("फोटो में पहचान आ अनुमानित गिनती बा: %s। बॉक्स आ गिनती अनुमान ह।" % listing)
            if stage_listing:
                parts.append("टमाटर के रंग-चरण के मोट अनुमान: %s; खाली रंग से पकाव पक्का ना होखेला।" % stage_listing)
        elif lang == "mai":
            parts.append("फोटोमे पहचान आ अनुमानित गिनती अछि: %s। बॉक्स आ गिनती अनुमान अछि।" % listing)
            if stage_listing:
                parts.append("टमाटरक रंग-चरणक मोट अनुमान: %s; केवल रंग सँ परिपक्वता निश्चित नहि होइत अछि।" % stage_listing)
        else:
            parts.append("पहचानी गई फल-सब्ज़ियाँ: %s। बॉक्स और गिनती अनुमान हैं।" % listing)
            if stage_listing:
                parts.append("टमाटर के रंग-चरण का मोटा अनुमान: %s; केवल रंग से परिपक्वता की पुष्टि नहीं होती।" % stage_listing)
    elif r.get("status") == "produce_hint":
        kind = r.get("candidate_kind", "")
        names = {"green chilli": "हरी मिर्च", "bell pepper": "शिमला मिर्च", "tomato": "टमाटर", "potato": "आलू"}
        candidate = names.get(kind, r.get("candidate", "फल या सब्ज़ी"))
        if lang == "en":
            parts.append("The image may show %s, but the box detector could not confirm it." % r.get("candidate", "produce"))
        elif lang == "bho":
            parts.append("तस्वीर में ई %s हो सकेला, बाकिर बॉक्स डिटेक्टर पक्का नइखे कइले।" % candidate)
        elif lang == "mai":
            parts.append("तस्वीरमे ई %s भऽ सकैत अछि, मुदा बॉक्स डिटेक्टर पक्का नहि कएलक।" % candidate)
        else:
            parts.append("तस्वीर में %s हो सकता है, लेकिन बॉक्स डिटेक्टर इसकी पुष्टि नहीं कर पाया।" % candidate)
    elif r.get("label"):
        name = label_hi(r["label"]) if hi else pretty(r["label"]).replace(" - ", ", ")
        parts.append(i18n.T(lang, "result_line", name=name, pct=round(r["confidence"] * 100)))
        parts.append(review_text(lang) if r.get("reasons") else cat_text(r["category"], lang))
    st = soil_state(rec.get("soil"))
    if st:
        parts.append(soil_text(st, lang))
    return " ".join(x.strip() for x in parts if x.strip())
