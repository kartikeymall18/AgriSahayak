"""Short, accurate spoken introduction for live project demonstrations."""

INTRODUCTIONS = {
    "en": (
        "Welcome to AgriSahayak, your smart field companion. The live dashboard connects rover sensors, leaf-disease screening, "
        "and camera boxes that estimate counts of supported fruit and vegetables. Fasal Saathi combines offline and online AI "
        "for farm questions. Farmer Support Desk matches crop, field details and recent scans to scheme and expert-help routes. "
        "The tablet saves photos offline and syncs them when connected. Counts are estimates; disease screening is for leaves."
    ),
    "hi": (
        "AgriSahayak में आपका स्वागत है—खेत का स्मार्ट साथी। लाइव डैशबोर्ड रोवर सेंसर, पत्तियों की बीमारी-जाँच और समर्थित "
        "फलों-सब्ज़ियों के कैमरा बॉक्स व अनुमानित गिनती दिखाता है। फसल साथी खेती के सवालों के लिए ऑफलाइन और ऑनलाइन AI का उपयोग "
        "करता है। किसान सहायता डेस्क फसल, खेत और हाल की जाँच के अनुसार योजनाओं व विशेषज्ञ मदद के रास्ते सुझाता है। टैबलेट फोटो "
        "ऑफलाइन सहेजकर कनेक्शन आने पर भेजता है। गिनती अनुमान है; बीमारी-जाँच पत्तियों के लिए है।"
    ),
    "bho": (
        "AgriSahayak में रउआ सभे के स्वागत बा—ई खेत के स्मार्ट साथी ह। लाइव डैशबोर्ड रोवर सेंसर, पत्ता के बेमारी-जाँच, "
        "आ समर्थित फल-सब्जी पर कैमरा बॉक्स आ अनुमानित गिनती देखावेला। फसल साथी खेती के सवाल खातिर ऑफलाइन आ ऑनलाइन AI चलावेला। "
        "किसान सहायता डेस्क फसल, खेत आ पिछला जाँच के आधार पर योजना आ कृषि विशेषज्ञ के मदद के राह सुझावेला। टैबलेट फोटो बिना "
        "नेटवर्क सहेजेला, कनेक्शन लौटला पर भेजेला। गिनती अनुमान बा; बेमारी-जाँच खाली पत्ता के होला।"
    ),
    "mai": (
        "AgriSahayak में अहाँक स्वागत अछि—ई खेतक स्मार्ट साथी अछि। लाइव डैशबोर्ड रोवर सेंसर, पातक रोग-जाँच आ समर्थित "
        "फल-सब्जी पर कैमरा बॉक्स सहित अनुमानित गिनती देखबैत अछि। फसल साथी खेतीक सवाल लेल ऑफलाइन आ ऑनलाइन AI उपयोग करैत अछि। "
        "किसान सहायता डेस्क फसल, खेत आ हालक जाँचक आधार पर योजना आ विशेषज्ञ मददक रास्ता सुझबैत अछि। टैबलेट फोटो नेटवर्क बिना "
        "सहेजैत अछि आ कनेक्शन लौटलापर पठबैत अछि। गिनती अनुमान अछि; रोग-जाँच केवल पात लेल अछि।"
    ),
}


def get(lang):
    return INTRODUCTIONS.get(lang, INTRODUCTIONS["en"])
