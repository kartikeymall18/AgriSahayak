"""Language packs for everything the voice helper says. Edit the .json files in voice/locale to change the words.
Languages: en (English), hi (Hindi), bho (Bhojpuri, DRAFT), mai (Maithili, DRAFT). A missing sentence falls back to Hindi, then English."""
import json
import os

HERE = os.path.dirname(os.path.abspath(__file__))
LANGS = ["hi", "bho", "mai", "en"]
_PACKS = {}


def load():
    for code in LANGS:
        try:
            with open(os.path.join(HERE, "locale", code + ".json"), encoding="utf-8") as f:
                _PACKS[code] = json.load(f)
        except Exception as e:
            print("[i18n] could not read locale/%s.json: %s" % (code, e))
            _PACKS[code] = {}


def norm(lang):
    return lang if lang in LANGS else "hi"


def names():
    return {c: _PACKS.get(c, {}).get("_name", c) for c in LANGS}


def has(lang, key):
    return bool(_PACKS.get(lang, {}).get(key))


def get(lang, key):
    """The sentence in exactly this language, or None."""
    return _PACKS.get(lang, {}).get(key)


def T(lang, key, **kw):
    for code in (lang, "hi", "en"):
        s = _PACKS.get(code, {}).get(key)
        if s:
            try:
                return s.format(**kw) if kw else s
            except (KeyError, IndexError):
                return s
    return key


load()
