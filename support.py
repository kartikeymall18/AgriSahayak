"""Small, offline-first shortlist of official farmer-support routes.

The matcher ranks public programmes by the farmer's stated need. It is a referral
aid, not an eligibility checker or application service; state rules and deadlines
must be confirmed with the official department or bank.
"""
import re


PROGRAMMES = {
    "pmfby": {
        "name": "Pradhan Mantri Fasal Bima Yojana (PMFBY)",
        "url": "https://pmfby.gov.in/",
        "description": "Check crop-insurance enrollment, reporting a crop loss, claim status and local deadlines.",
    },
    "kcc": {
        "name": "Kisan Credit Card (KCC)",
        "url": "https://financialservices.gov.in/agriculture-credit",
        "description": "Ask a participating bank about crop-cost and working-capital credit and the documents for your cultivator status.",
    },
    "pmkisan": {
        "name": "PM-KISAN",
        "url": "https://pmkisan.gov.in/",
        "description": "Check the official eligibility/status service for this farmer family; eligibility rules and exclusions apply.",
    },
    "soil": {
        "name": "Soil Health Card",
        "url": "https://soilhealth.dac.gov.in/",
        "description": "Ask the local agriculture office about soil testing and crop-specific soil recommendations.",
    },
    "midh": {
        "name": "Mission for Integrated Development of Horticulture (MIDH)",
        "url": "https://nhb.gov.in/writereaddata/082825102800MIDH%20Guideline%202025.pdf",
        "description": "The 2025 guidance covers horticulture including vegetables and root/tuber crops. Ask your State Horticulture Mission which component is open for this crop and district.",
    },
    "expert": {
        "name": "Kisan Call Centre / local agriculture specialist",
        "url": "tel:18001801551",
        "description": "Request a crop-specific field assessment or referral to the district agriculture specialist.",
    },
    "state": {
        "name": "District agriculture office / Krishi Vigyan Kendra",
        "url": "https://kvk.icar.gov.in/",
        "description": "Ask about state and district schemes, local input support, and an in-person field visit.",
    },
}

ALIASES = {
    "potato": ("potato", "potatoes", "aloo", "aaloo", "आलू"),
    "tomato": ("tomato", "tomatoes", "tamatar", "टमाटर"),
    "bell pepper": ("bell pepper", "capsicum", "shimla mirch", "शिमला मिर्च"),
    "chilli": ("chilli", "chili", "mirchi", "मिर्च"),
    "wheat": ("wheat", "गेहूँ", "गेहूं"),
    "rice": ("rice", "paddy", "धान", "चावल"),
}

WORDS = {
    "loss": ("crop loss", "failed crop", "crop damage", "insurance", "claim", "drought", "flood", "hail", "नुकसान", "फसल बर्बाद", "फसल खराब", "बीमा", "मुआवजा", "सूखा", "बाढ़", "ओला", "क्षति"),
    "credit": ("loan", "credit", "debt", "kcc", "working capital", "crop cost", "कर्ज", "कर्जा", "ऋण", "लोन", "उधार", "बीज का पैसा", "खेती खर्च"),
    "income": ("income support", "cash support", "pm-kisan", "pm kisan", "financial help", "scheme", "subsidy", "सरकारी योजना", "योजना", "आर्थिक मदद", "किसान सम्मान", "पीएम किसान", "सब्सिडी"),
    "soil": ("soil test", "soil health", "soil nutrients", "fertility", "मिट्टी जाँच", "मिट्टी जांच", "माटी जाँच", "माटी जांच", "उर्वरता", "पोषक तत्व"),
    "expert": ("disease", "diagnosis", "not sure", "uncertain", "field visit", "officer", "expert", "किसान अधिकारी", "कृषि अधिकारी", "कृषि विशेषज्ञ", "खेत पर आएं", "खेत पर आएँ", "पक्का नहीं", "बीमारी", "रोग", "बेमारी"),
    "inputs": ("fertilizer", "fertiliser", "seed", "input support", "free fertilizer", "free fertiliser", "खाद", "बीज", "मुफ्त खाद", "मुफ्त बीज", "सरकारी मदद"),
}

REPLIES = {
    "en": "Based on the need you described, start by checking {name}. This is a relevant route to verify, not a promise of eligibility. Share your district/state and cultivator status so the support desk can narrow the shortlist.",
    "hi": "आपकी बताई जरूरत के आधार पर पहले {name} की जानकारी जाँचें। यह जाँचने योग्य विकल्प है, पात्रता की गारंटी नहीं। जिला/राज्य और खेती की स्थिति बताएँ, ताकि सहायता डेस्क विकल्प और सीमित कर सके।",
    "bho": "रउआ के बतावल जरूरत के हिसाब से पहिले {name} के जानकारी जाँचीं। ई जाँचे लायक रास्ता बा, पात्रता के गारंटी नइखे। जिला/राज्य आ खेती के स्थिति बताईं, ताकि सहायता डेस्क सही विकल्प छाँट सके।",
    "mai": "अहाँक बताओल जरूरतक आधार पर पहिले {name}क जानकारी देखू। ई जाँचबाक योग्य विकल्प अछि, पात्रताक गारंटी नहि। जिला/राज्य आ खेतीक स्थिति बताउ, जाहिसँ सहायता डेस्क विकल्प सीमित कऽ सकय।",
}


def detect_crop(text):
    q = str(text or "").lower()
    for crop, aliases in ALIASES.items():
        if any(a in q for a in aliases):
            return crop
    return ""


def recommend(crop="", district="", issue="", cultivator="", latest_result="", soil_percent=None,
              field_details=""):
    """Return up to three ranked, explainable referral candidates."""
    q = " ".join(str(x or "") for x in (crop, district, issue, cultivator, latest_result, field_details)).lower()
    scores = {}

    def add(key, score, reason):
        old = scores.get(key)
        if old is None or score > old["score"]:
            scores[key] = {**PROGRAMMES[key], "id": key, "score": score, "reason": reason}

    if any(w in q for w in WORDS["loss"]):
        add("pmfby", 100, "Your description mentions crop loss or insurance.")
    if any(w in q for w in WORDS["credit"]):
        add("kcc", 98, "Your description mentions farm credit or crop costs.")
    if any(w in q for w in WORDS["income"]):
        add("pmkisan", 95, "Your description asks about income support or a government scheme.")
    if any(w in q for w in WORDS["soil"]):
        add("soil", 92, "Your description asks about soil testing or soil health.")
    if any(w in q for w in WORDS["expert"]):
        add("expert", 96, "Your description asks for crop diagnosis or a specialist.")
    if any(w in q for w in WORDS["inputs"]):
        add("kcc", 82, "KCC is a route to ask a bank about farm working-capital credit; free inputs are not assumed.")
        add("state", 80, "Input support can vary by state, so the district agriculture office is a useful check.")

    crop_key = detect_crop(crop) or str(crop or "").strip().lower()
    horticulture = {"tomato", "potato", "chilli", "bell pepper"}
    scheme_query = any(w in q for w in WORDS["income"] + WORDS["inputs"])
    if crop_key in horticulture and scheme_query:
        add("midh", 98, "The 2025 MIDH guidance covers horticulture crops including vegetables and root/tuber crops. District and component availability must be confirmed with the State Horticulture Mission.")

    # Use the latest image result as context, but do not treat a leaf diagnosis as a
    # produce-quality result or as proof that a farmer qualifies for a programme.
    if latest_result and any(w in q for w in WORDS["expert"]):
        add("expert", 99, "The latest scan is relevant context; ask an agriculture specialist to verify it in the field.")
    if not scores:
        add("kcc", 60, "KCC is a useful first check for crop costs and working-capital needs.")
        add("pmkisan", 55, "PM-KISAN is a possible income-support route to check on the official portal.")
        add("state", 50, "State-specific benefits need your district and state.")

    ranked = sorted(scores.values(), key=lambda x: (-x["score"], x["id"]))[:3]
    crop_name = str(crop or detect_crop(q)).strip()
    if not crop_name:
        crop_name = detect_crop(q)
    location = str(district or "").strip()
    status = str(cultivator or "Not provided").strip()
    for item in ranked:
        item["reason"] = (item["reason"] + (" Crop: %s." % crop_name if crop_name else "") +
                          (" Location: %s." % location if location else " District/state not provided; state-specific options may be missing."))
    call_note = [
        "I am seeking agriculture support.",
        "District/state: " + (location or "Please ask me"),
        "Crop: " + (crop_name or "Please ask me"),
        "Cultivator status: " + status,
        "Field details: " + (str(field_details).strip() or "Please ask me"),
        "Need: " + (str(issue or "General crop, scheme, or field support").strip()),
    ]
    if latest_result:
        call_note.append("Latest AgriSahayak scan (please verify): " + str(latest_result).strip())
    call_note.append("Please confirm current eligibility, documents, deadlines, and the official application route for my location.")
    return {"crop": crop_name, "district": location, "cultivator": status,
            "field_details": str(field_details or "").strip(),
            "location_needed": not bool(location), "recommendations": ranked,
            "call_note": "\n".join(call_note),
            "notice": "Shortlist only. Rules, deadlines and benefits vary by location; confirm with the official department or bank. This tool does not submit applications."}


def reply(result, lang="en"):
    recs = result.get("recommendations") or []
    if not recs:
        return "Please add your crop and district/state in Farmer Support Desk so I can narrow the support options."
    template = REPLIES.get(lang, REPLIES["en"])
    return template.format(name=recs[0]["name"])

