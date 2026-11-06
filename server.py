import os, io, re, csv, json, time, hashlib, threading, socket, datetime
from collections import deque
from concurrent.futures import ThreadPoolExecutor
from flask import send_file, Flask, request, jsonify, Response
from PIL import Image
import config
import advice
import assistant
import support
from voice.pipeline import Voice
from voice import i18n, introduction
from classifier import Classifier
from gate import LeafGate
from produce import ProduceDetector

BASE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(BASE, "data")
os.makedirs(DATA, exist_ok=True)
JSONL = os.path.join(DATA, "records.jsonl")

app = Flask(__name__, static_folder=os.path.join(BASE, "static"), static_url_path="")
app.config["MAX_CONTENT_LENGTH"] = 100 * 1024 * 1024

LOCK = threading.Lock()
RECORDS, ORDER = {}, []
STATE = {"lang": "en", "field": "Demo Field"}
FARM_PROFILE = {}
SPEAK = []
LATEST = {"soil": None, "soil_time": 0.0, "frame": None, "frame_time": 0.0}
ROVER = {"cmd": "S", "time": 0.0, "speed": 150, "sent_speed": None, "error": None}
SER = None
CLF = Classifier()
GATE = LeafGate()
PRODUCE = ProduceDetector(os.path.join(BASE, "model", "produce-rtdetrv1-50-obj365"))
START = time.time()
SOIL_HIST = deque(maxlen=120)          # recent soil readings for the little graph
LIVE = {"t": 0.0, "ran": 0.0, "pred": None, "fut": None}   # last live prediction on the preview frame
# ALL PyTorch work runs on this ONE long-lived thread. (Flask makes a new thread for every request; running
# PyTorch inside each of them can pile up thousands of threads and eat the laptop's memory.)
INFER = ThreadPoolExecutor(max_workers=1, thread_name_prefix="infer")
GPS = {}                       # source name -> {lat, lon, acc, t}   (tablet, phone, ...)
TABLET = {"state": {}, "seen": 0.0}   # what the tablet last reported about itself
CMDQ = []                      # commands from the dashboard to the tablet (camera, photo, ...)
SETTINGS_FILE = os.path.join(DATA, "settings.json")
SENS = {"t": 0.0, "d": {"safety": 1}}   # latest values from the Arduino (temperature, distance, pump, ...)
DEVQ = []                               # lines for the Arduino (pump, servo, scan ...) waiting for the tablet to write them
VOICE = Voice(DATA, lambda fn, *a: infer(fn, *a))
TTS_EXEC = ThreadPoolExecutor(max_workers=1, thread_name_prefix="speech")
TTS_JOBS, TTS_JOBS_LOCK = {}, threading.Lock()


@app.after_request
def cors(resp):
    resp.headers["Access-Control-Allow-Origin"] = "*"
    resp.headers["Access-Control-Allow-Headers"] = "*"
    if request.path.startswith("/api/") and not request.path.startswith(("/api/file/", "/api/thumb/")):
        resp.headers["Cache-Control"] = "no-store"
    return resp


# ---------- helpers ----------
def clean(s, n=40):
    s = re.sub(r"[^A-Za-z0-9_-]+", "_", (s or "").strip()).strip("_")
    return (s or "unknown")[:n]


def load_records():
    if not os.path.exists(JSONL):
        return
    with open(JSONL, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                r = json.loads(line)
            except ValueError:
                continue
            if r.get("id") and r["id"] not in RECORDS:
                RECORDS[r["id"]] = r
                ORDER.append(r["id"])


def view(rec, lang):
    v = dict(rec)
    r = rec.get("result") or {}
    v["name"] = advice.pretty(r["label"]) if r.get("label") else (r.get("candidate") if r.get("status") == "produce_hint" else None)
    v["soil_state"] = advice.soil_state(rec.get("soil"))
    v["text"] = advice.speech_text(rec, lang)
    return v


def gate_observation(gate_result, produce_error=None):
    """Make the gate's non-leaf decision visible without pretending it has a box detector."""
    best = str((gate_result or {}).get("best", "")).lower()
    score = float((gate_result or {}).get("best_score", 0.0) or 0.0)
    produce_scores = (gate_result or {}).get("produce_scores") or {}
    common = {"plant_score": (gate_result or {}).get("plant_score"),
              "seen": (gate_result or {}).get("best"), "seen_confidence": round(score, 4)}
    scene_score = max((score if "hand" in best or "person" in best or "human face" in best else 0.0), 0.0)
    candidates = sorted(produce_scores.items(), key=lambda item: item[1], reverse=True)
    if candidates:
        candidate, candidate_score = candidates[0]
        # Keep a weak zero-shot crop guess visible when it is plausibly present,
        # including a chilli held in a hand, but never call it a box detection.
        if candidate_score >= 0.06 and candidate_score >= scene_score * 0.22:
            label = {"green chilli": "Possible green chilli", "bell pepper": "Possible bell pepper",
                     "tomato": "Possible tomato", "potato": "Possible potato"}.get(candidate, "Possible produce")
            return dict(common, status="produce_hint", name=label, candidate=label,
                        candidate_kind=candidate, confidence=round(candidate_score, 4),
                        category="produce", produce_error=produce_error)
    if "hand" in best:
        return dict(common, status="not_plant", scene="hand", scene_name="Hand in view",
                    produce_error=produce_error)
    if "person" in best or "human face" in best:
        return dict(common, status="not_plant", scene="person", scene_name="Person in view",
                    produce_error=produce_error)
    # This zero-shot gate can suggest these items, but it cannot draw boxes or count them.
    return dict(common, status="not_plant", produce_error=produce_error)


def analyse(img):
    # Do not let a background person/hand prediction from CLIP veto a visible
    # tomato, potato or bell pepper. The box detector knows these produce classes.
    produced = PRODUCE.predict(img)
    if produced["detections"]:
        return produce_result_from_prediction(img, produced)
    g = GATE.check(img) if GATE.ready else None
    if g and not g["is_plant"]:
        return gate_observation(g, produced.get("error"))
    if not CLF.ready:
        return {"status": "no_model", "error": CLF.error}
    top = CLF.predict(img)
    best = top[0]
    reasons = []
    if best["score"] < config.CONF_MIN:
        reasons.append("low_confidence")
    return {"status": "review" if reasons else "ok",
            "label": best["label"], "confidence": round(best["score"], 4),
            "category": advice.categorize(best["label"]),
            "top": [{"label": t["label"], "score": round(t["score"], 4)} for t in top],
            "reasons": reasons}


def produce_result_from_prediction(img, p):
    counts = p["counts"]
    label = ", ".join("%s x%d" % (name, count) for name, count in counts.items())
    tomato_color_stages = {}
    tomato_sample_screen = p.get("tomato_sample_screen")
    for detection in p["detections"]:
        if str(detection.get("label", "")).strip().lower() == "tomato":
            stage = detection.get("color_stage", "uncertain")
            tomato_color_stages[stage] = tomato_color_stages.get(stage, 0) + 1
    has_tomato = tomato_color_stages != {}
    health_note = (
        "Tomato photo screen: %s (%.0f%% confidence). This is a prototype image-level screen, not a named disease diagnosis, and does not score each fruit separately; confirm visually."
        % (tomato_sample_screen.get("status", "uncertain").replace("_", " "),
           float(tomato_sample_screen.get("confidence", 0)) * 100)
        if has_tomato and tomato_sample_screen and tomato_sample_screen.get("status") in ("healthy", "possible_disease") else
        "Tomato fruit screen is uncertain or unavailable for this photo; no health result was produced."
        if has_tomato else
        "No tomato fruit is in this scan; other produce is detected and counted only, with no health diagnosis."
    )
    return {"status": "produce", "label": label, "name": label, "confidence": p["detections"][0]["score"],
            "category": "produce", "produce_counts": counts, "detections": p["detections"],
            "tomato_color_stages": tomato_color_stages,
            "tomato_sample_screen": tomato_sample_screen,
            "tomato_screen_available": bool(has_tomato and tomato_sample_screen and
                                              tomato_sample_screen.get("status") in ("healthy", "possible_disease")),
            "produce_analysis_note": health_note + " Surface color is a rough stage cue only; it cannot confirm maturity, freshness, or quality.",
            "frame_width": img.width, "frame_height": img.height,
            "top": [{"label": d["label"], "score": d["score"]} for d in p["detections"]],
            "reasons": ["prototype_tomato_fruit_screen"] if has_tomato else ["produce_count_only"]}


def infer(fn, *args, timeout=120):
    """Run a model job on the single inference thread and wait for it."""
    return INFER.submit(fn, *args).result(timeout=timeout)


def load_settings():
    try:
        with open(SETTINGS_FILE, encoding="utf-8") as f:
            d = json.load(f)
        if d.get("field"):
            STATE["field"] = str(d["field"])[:60]
    except Exception:
        pass


def save_settings():
    try:
        with open(SETTINGS_FILE, "w", encoding="utf-8") as f:
            json.dump({"field": STATE["field"]}, f, ensure_ascii=False)
    except Exception:
        pass


def set_gps(src, lat, lon, acc):
    try:
        lat, lon = float(lat), float(lon)
        acc = float(acc) if acc not in (None, "") else None
    except (TypeError, ValueError):
        return False
    if not (-90 <= lat <= 90 and -180 <= lon <= 180):
        return False
    GPS[src] = {"lat": lat, "lon": lon, "acc": acc, "t": time.time()}
    return True


def best_gps(max_age=30):
    """The freshest and most accurate position from any source (tablet, phone, ...)."""
    now = time.time()
    # the laptop does not move during a demo, so its position stays valid for hours; tablet and phone go stale in 30 s
    c = [dict(v, src=k) for k, v in GPS.items() if now - v["t"] <= (6 * 3600 if k == "laptop" else max_age)]
    return min(c, key=lambda g: g["acc"] if g.get("acc") else 1e9) if c else None


def tablet_online():
    return time.time() - TABLET["seen"] < 4


def queue_speech(text, lang):
    """Synthesize longer neural replies off the request thread so the text appears immediately."""
    job_id = hashlib.sha256((str(time.time_ns()) + str(text)).encode("utf-8")).hexdigest()[:20]
    def render():
        audio_url = VOICE.synth_url(text, lang)
        VOICE._cleanup()
        return audio_url
    future = TTS_EXEC.submit(render)
    with TTS_JOBS_LOCK:
        expired = [key for key, job in TTS_JOBS.items() if job["created"] < time.time() - 120 and job["future"].done()]
        for key in expired:
            TTS_JOBS.pop(key, None)
        TTS_JOBS[job_id] = {"future": future, "created": time.time()}
    return job_id


def rover_link():
    st = TABLET["state"]
    if tablet_online() and st.get("serial") == "connected":
        return "Arduino via tablet (%s)" % st.get("serial_kind", "USB")
    if SER:
        return "Arduino connected on " + str(config.SERIAL_PORT)
    return "SIMULATION (no Arduino connected)"


def proc_mem_mb():
    """Memory used by this server process, in MB (None if it cannot be read)."""
    try:
        if os.name == "nt":
            import ctypes
            from ctypes import wintypes

            class PMC(ctypes.Structure):
                _fields_ = [("cb", wintypes.DWORD), ("PageFaultCount", wintypes.DWORD), ("PeakWorkingSetSize", ctypes.c_size_t),
                            ("WorkingSetSize", ctypes.c_size_t), ("QuotaPeakPagedPoolUsage", ctypes.c_size_t),
                            ("QuotaPagedPoolUsage", ctypes.c_size_t), ("QuotaPeakNonPagedPoolUsage", ctypes.c_size_t),
                            ("QuotaNonPagedPoolUsage", ctypes.c_size_t), ("PagefileUsage", ctypes.c_size_t),
                            ("PeakPagefileUsage", ctypes.c_size_t)]
            k32, ps = ctypes.windll.kernel32, ctypes.windll.psapi
            k32.GetCurrentProcess.restype = wintypes.HANDLE
            ps.GetProcessMemoryInfo.argtypes = [wintypes.HANDLE, ctypes.POINTER(PMC), wintypes.DWORD]
            pmc = PMC()
            pmc.cb = ctypes.sizeof(pmc)
            ps.GetProcessMemoryInfo(k32.GetCurrentProcess(), ctypes.byref(pmc), pmc.cb)
            return round(pmc.WorkingSetSize / 1048576)
        with open("/proc/self/statm") as f:
            return round(int(f.read().split()[1]) * os.sysconf("SC_PAGE_SIZE") / 1048576)
    except Exception:
        return None


def health_logger():
    while True:
        time.sleep(60)
        m = proc_mem_mb()
        print("[health] server memory %s MB, python threads %d" % (m, threading.active_count()))
        if m and m > 3000:
            print("[health] WARNING: the server is using more than 3 GB. Tell Claude.")


def ingest_line(line):
    """One Arduino line (from the tablet or from a USB cable on the laptop) -> latest values."""
    now, d = time.time(), SENS["d"]
    try:
        p = line.strip().split(",")
        k = p[0]
        if k == "SOIL":
            LATEST["soil"], LATEST["soil_time"] = float(p[1]), now
            SOIL_HIST.append(LATEST["soil"])
        elif k == "ENV":
            d["temp"], d["hum"] = (None, None) if p[1] == "ERR" else (int(p[1]), int(p[2]))
        elif k == "DIST":
            d["dist"] = int(p[1])
        elif k == "EDGE":
            d["edge"] = int(p[1])
        elif k == "PUMP":
            d["pump"] = int(p[1])
        elif k == "BLOCK":
            d["block"], d["block_t"] = p[1], now
        elif k == "SCAN":
            d["scan"], d["scan_t"] = [int(x) for x in p[1:4]], now
        elif k == "STAT":
            v = [int(x) for x in p[1:10]]
            LATEST["soil"], LATEST["soil_time"] = float(v[0]), now
            d.update(temp=None if v[1] == -99 else v[1], hum=None if v[2] < 0 else v[2], dist=v[3], edge=v[4], pump=v[5], servo=v[6], auto=v[7], safety=v[8])
        elif k == "OK" and len(p) > 1:
            if p[1] == "SERVO":
                d["servo"] = int(p[2])
            elif p[1].startswith("AUTOWATER"):
                d["auto"] = 1 if p[1].endswith("ON") else 0
            elif p[1].startswith("SAFETY"):
                d["safety"] = 1 if p[1].endswith("ON") else 0
            elif p[1] == "CAL":
                d["cal"] = [int(p[2]), int(p[3])]
        elif k == "ERR":
            d["err"], d["err_t"] = p[1], now
        elif k == "RAW":
            d["raw"] = int(p[1])
        elif k in ("READY", "PONG"):
            d["ready_t"] = now
        else:
            return False
        SENS["t"] = now
        return True
    except (IndexError, ValueError):
        return False


def sens_view():
    now = time.time()
    d = dict(SENS["d"])
    d["alive"] = now - SENS["t"] < 6
    d["age"] = round(now - SENS["t"], 1) if SENS["t"] else None
    d["block_recent"] = bool(d.get("block_t") and now - d["block_t"] < 6)
    return d


def device_line(line):
    """Queue one line for the Arduino. The tablet writes it; a USB cable on the laptop gets it directly."""
    with LOCK:
        DEVQ.append({"n": len(DEVQ) + 1, "line": line, "t": time.time()})
    if SER and not (tablet_online() and TABLET["state"].get("serial") == "connected"):
        send_serial((line + "\n").encode())


def apply_action(out):
    """Things the helper may do by voice. It can take photos, switch the camera and run the pump for 3 s. It cannot drive the rover."""
    a = out.get("action")
    if a == "pump":
        device_line("P3")
    elif a in ("photo", "camera_on", "camera_off"):
        with LOCK:
            CMDQ.append({"n": len(CMDQ) + 1, "cmd": a, "interval": 10, "t": time.time()})


def push_speak(text, lang, audio=None):
    with LOCK:
        SPEAK.append({"n": len(SPEAK) + 1, "lang": "en-US" if lang == "en" else "hi-IN", "text": text, "audio": audio})


# ---------- serial (Arduino) ----------
def open_serial():
    global SER
    if not config.SERIAL_PORT:
        return
    try:
        import serial
        SER = serial.Serial(config.SERIAL_PORT, config.BAUD, timeout=0.2)
        threading.Thread(target=serial_reader, daemon=True).start()
    except Exception as e:
        ROVER["error"] = str(e)
        print("Could not open serial port:", e)


def serial_reader():
    while SER:
        try:
            line = SER.readline().decode(errors="ignore").strip()
        except Exception as e:
            ROVER["error"] = str(e)
            break
        ingest_line(line)


def send_serial(data):
    if SER:
        try:
            SER.write(data)
        except Exception as e:
            ROVER["error"] = str(e)


def watchdog():
    while True:
        time.sleep(0.1)
        if ROVER["cmd"] != "S" and time.time() - ROVER["time"] > 0.5:
            ROVER["cmd"] = "S"
            send_serial(b"S\n")
            print("[rover] no command for 0.5 s -> STOP")


# ---------- routes ----------
@app.get("/")
def home():
    return app.send_static_file("dashboard.html")


@app.get("/api/ping")
def ping():
    return jsonify(ok=True, time=time.time())


@app.get("/api/status")
def status():
    now = time.time()
    return jsonify(
        model="ready" if CLF.ready else "not ready",
        model_error=CLF.error, device=CLF.device,
        produce_model=("Ready" if PRODUCE.ready else
                       "Installed (loads on first produce scan)" if os.path.isfile(os.path.join(PRODUCE.model_dir, "model.safetensors")) else
                       "Not installed"),
        produce_error=PRODUCE.error,
        tomato_fruit_model=("Ready" if PRODUCE.fruit_health.ready else
                            "Installed (loads on first tomato scan)" if PRODUCE.fruit_health.installed else
                            "Not installed"),
        tomato_fruit_error=PRODUCE.fruit_health.error,
        rover=rover_link(),
        rover_error=ROVER["error"], last_cmd=ROVER["cmd"],
        soil=LATEST["soil"] if now - LATEST["soil_time"] < 30 else None,
        frame_age=round(now - LATEST["frame_time"], 1) if LATEST["frame"] else None,
        lang=STATE["lang"], records=len(ORDER), field=STATE["field"],
        uptime=int(now - START), lan_ips=lan_ips(), port=config.PORT,
        gate="ready" if GATE.ready else "off", gate_note=GATE.error,
        server_mem_mb=proc_mem_mb(), tablet=dict(TABLET["state"], online=tablet_online()), gps=best_gps(),
        sensors=sens_view(), voice=VOICE.status())


def analyse_live(img):
    """Quick look at the live preview frame. Nothing is saved."""
    produced = PRODUCE.predict(img)
    if produced["detections"]:
        return produce_result_from_prediction(img, produced)
    g = GATE.check(img) if GATE.ready else None
    if g and not g["is_plant"]:
        return gate_observation(g, produced.get("error"))
    if not CLF.ready:
        return {"status": "no_model", "error": CLF.error}
    top = CLF.predict(img)
    best = top[0]
    return {"status": "ok" if best["score"] >= config.CONF_MIN else "uncertain",
            "label": best["label"], "name": advice.pretty(best["label"]),
            "confidence": round(best["score"], 4), "category": advice.categorize(best["label"]),
            "top": [{"name": advice.pretty(t["label"]), "score": round(t["score"], 4)} for t in top]}


def live_update(now):
    """Start (never wait for) a model look at the newest preview frame; collect finished results."""
    fut = LIVE["fut"]
    if fut is not None and fut.done():
        try:
            LIVE["pred"] = fut.result()
        except Exception as e:
            LIVE["pred"] = {"status": "error", "error": str(e)}
        LIVE["fut"], LIVE["ran"] = None, time.time()
    fresh = LATEST["frame"] is not None and now - LATEST["frame_time"] < 5
    if not fresh:
        LIVE["pred"] = None
    elif (CLF.ready or os.path.isfile(os.path.join(PRODUCE.model_dir, "model.safetensors"))) and LIVE["fut"] is None and LIVE["t"] != LATEST["frame_time"] and now - LIVE["ran"] > 0.35:
        try:
            img = Image.open(io.BytesIO(LATEST["frame"])).convert("RGB")
            LIVE["t"] = LATEST["frame_time"]
            LIVE["fut"] = INFER.submit(analyse_live, img)
        except Exception as e:
            LIVE["pred"] = {"status": "error", "error": str(e)}
    return fresh


@app.get("/api/live")
def live():
    """Everything the live screens need in ONE call: preview age, model view, soil, rover, tablet, GPS."""
    now = time.time()
    lang = request.args.get("lang") or STATE["lang"]
    lang = lang if lang in i18n.LANGS else "en"
    live_update(now)
    soil = LATEST["soil"] if now - LATEST["soil_time"] < 30 else None
    pred = LIVE["pred"]
    if pred and pred.get("status") == "ok":
        pred = dict(pred, advice=advice.cat_text(pred["category"], lang))
    return jsonify(
        frame_age=round(now - LATEST["frame_time"], 1) if LATEST["frame"] else None,
        model="ready" if CLF.ready else "not ready",
        vision_model="ready" if CLF.ready or os.path.isfile(os.path.join(PRODUCE.model_dir, "model.safetensors")) else "not ready",
        device=CLF.device, gate=GATE.ready,
        soil=soil, soil_state=advice.soil_state(soil), soil_hist=list(SOIL_HIST)[-60:],
        pred=pred, rover=rover_link(), last_cmd=ROVER["cmd"], records=len(ORDER), lang=STATE["lang"],
        field=STATE["field"], tablet=dict(TABLET["state"], online=tablet_online()), gps=best_gps(), sensors=sens_view())


@app.post("/api/lang")
def set_lang():
    d = request.get_json(silent=True) or {}
    STATE["lang"] = d.get("lang") if d.get("lang") in i18n.LANGS else "en"
    return jsonify(ok=True, lang=STATE["lang"])


@app.post("/api/upload")
def upload():
    f = request.files.get("file")
    rid = clean(request.form.get("id"), 64)
    if not f or rid == "unknown":
        return jsonify(ok=False, error="missing file or id"), 400
    with LOCK:
        if rid in RECORDS:
            return jsonify(ok=True, duplicate=True, record=RECORDS[rid],
                           view=view(RECORDS[rid], STATE["lang"]))
    blob = f.read()
    sha = request.form.get("sha256", "").strip().lower()
    if sha and hashlib.sha256(blob).hexdigest() != sha:
        return jsonify(ok=False, error="checksum mismatch, send again"), 400
    kind = "video" if request.form.get("kind") == "video" else "photo"
    ts = request.form.get("ts") or datetime.datetime.now().astimezone().isoformat(timespec="seconds")
    day = ts[:10] if re.match(r"^\d{4}-\d{2}-\d{2}", ts) else datetime.date.today().isoformat()
    field = request.form.get("field", "").strip() or STATE["field"]
    result = None
    if kind == "photo":
        try:
            img = Image.open(io.BytesIO(blob))
            img.load()
            img = img.convert("RGB")
        except Exception:
            return jsonify(ok=False, error="not a valid image"), 400
        result = infer(analyse, img)
    crop = ("Produce" if result and result.get("status") == "produce" else
            advice.crop_of(result["label"]) if result and result.get("label") else "Unknown")
    folder = os.path.join(DATA, clean(field), clean(crop), day)
    os.makedirs(folder, exist_ok=True)
    fname = "%s_%s.%s" % (clean(ts.replace(":", "-"), 30), rid[:8], "webm" if kind == "video" else "jpg")
    path = os.path.join(folder, fname)
    with open(path, "wb") as out:
        out.write(blob)
    soil, src = None, None
    if time.time() - LATEST["soil_time"] < 30:
        soil, src = LATEST["soil"], "sensor"
    lat = lon = acc = gsrc = None            # where the photo was taken (GPS of the tablet or the phone)
    try:
        lat, lon = float(request.form.get("lat", "")), float(request.form.get("lon", ""))
        if not (-90 <= lat <= 90 and -180 <= lon <= 180):
            raise ValueError
        acc = float(request.form.get("acc") or 0) or None
        gsrc = "tablet"
    except ValueError:
        lat = lon = None
        g = best_gps()
        if g:
            lat, lon, acc, gsrc = g["lat"], g["lon"], g.get("acc"), g["src"]
    rec = {"id": rid, "ts": ts, "received": datetime.datetime.now().astimezone().isoformat(timespec="seconds"),
           "field": field, "crop": crop, "plot": "-", "kind": kind,
           "file": os.path.relpath(path, DATA).replace("\\", "/"),
           "soil": soil, "soil_source": src, "result": result,
           "lat": lat, "lon": lon, "acc": acc, "gps_src": gsrc}
    sv = sens_view()
    if sv["alive"] and sv.get("temp") is not None:
        rec["temp"], rec["hum"] = sv["temp"], sv.get("hum")
    with LOCK:
        if kind == "video":
            rec["plot"] = "Clip"
        elif result and result.get("status") == "produce":
            rec["plot"] = "Produce sample"
        elif result and (result.get("label") or result.get("status") == "no_model"):
            n = sum(1 for r in RECORDS.values() if r["kind"] == "photo" and r["field"] == field and r.get("plot", "-").startswith("Plant"))
            rec["plot"] = "Plant %d" % (n + 1)
        RECORDS[rid] = rec
        ORDER.append(rid)
        with open(JSONL, "a", encoding="utf-8") as j:
            j.write(json.dumps(rec, ensure_ascii=False) + "\n")
    print("[upload] %s %s %s/%s/%s -> %s" % (kind, rid[:8], field, crop, rec["plot"],
          (result or {}).get("label") or (result or {}).get("status") or "video"))
    return jsonify(ok=True, record=rec, view=view(rec, STATE["lang"]))


@app.get("/api/records")
def records():
    lang = request.args.get("lang") or STATE["lang"]
    with LOCK:
        ids = list(ORDER)[-300:]
    return jsonify(records=[view(RECORDS[i], lang) for i in reversed(ids)], lang=STATE["lang"])


@app.delete("/api/records/<rid>")
def delete_record(rid):
    """Remove one saved record and its media without allowing paths outside data/ to be deleted."""
    tmp = JSONL + ".tmp"
    with LOCK:
        rec = RECORDS.get(rid)
        if not rec:
            return jsonify(ok=False, error="Record not found"), 404
        keep = [key for key in ORDER if key != rid]
        try:
            with open(tmp, "w", encoding="utf-8", newline="\n") as f:
                for key in keep:
                    if key in RECORDS:
                        f.write(json.dumps(RECORDS[key], ensure_ascii=False) + "\n")
            os.replace(tmp, JSONL)
        except OSError as e:
            try:
                if os.path.exists(tmp):
                    os.remove(tmp)
            except OSError:
                pass
            return jsonify(ok=False, error="Could not update the records file: " + str(e)[:120]), 500
        RECORDS.pop(rid, None)
        ORDER[:] = keep

    file_deleted = False
    rel = rec.get("file")
    if rel:
        path = os.path.realpath(os.path.join(DATA, rel))
        root = os.path.realpath(DATA)
        try:
            if os.path.commonpath([root, path]) == root and os.path.isfile(path):
                os.remove(path)
                file_deleted = True
        except (OSError, ValueError):
            pass
    return jsonify(ok=True, deleted=rid, file_deleted=file_deleted)


def summary_text(lang):
    seen, lines = set(), []
    with LOCK:
        ids = list(ORDER)
    for rid in reversed(ids):
        r = RECORDS[rid]
        key = (r["field"], r["plot"])
        if r["kind"] != "photo" or key in seen:
            continue
        seen.add(key)
        res = r.get("result") or {}
        if res.get("status") == "produce":
            lines.append(advice.speech_text(r, lang))
        elif res.get("label"):
            name = advice.label_hi(res["label"]) if lang == "hi" else advice.pretty(res["label"]).replace(" - ", ", ")
            flag = (" (जाँच करें)" if lang == "hi" else " (needs checking)") if res.get("reasons") else ""
            num = r["plot"].replace("Plant ", "")
            lines.append(("पौधा %s: %s%s।" if lang == "hi" else "Plant %s: %s%s.") % (num, name, flag))
    if not lines:
        return "अभी कोई नतीजा नहीं है।" if lang == "hi" else "There are no results yet."
    return " ".join(lines)


@app.post("/api/speak")
def speak_post():
    d = request.get_json(silent=True) or {}
    lang = d.get("lang") if d.get("lang") in i18n.LANGS else "en"
    if d.get("text"):
        text = str(d["text"])[:600]
    elif d.get("summary"):
        text = summary_text(lang)
    else:
        rec = RECORDS.get(d.get("id"))
        if not rec:
            return jsonify(ok=False, error="unknown record"), 404
        text = advice.speech_text(rec, lang)
    push_speak(text, lang, VOICE.synth_url(text, lang))     # laptop voice if available, otherwise the tablet speaks it itself
    return jsonify(ok=True)


@app.get("/api/speak")
def speak_get():
    try:
        after = int(request.args.get("after", "0"))
    except ValueError:
        after = 0
    with LOCK:
        items = [s for s in SPEAK if s["n"] > after][-5:]
        last = len(SPEAK)
    return jsonify(items=items, last=last)


@app.get("/api/report.csv")
def report():
    lang = request.args.get("lang") or STATE["lang"]
    out = io.StringIO()
    w = csv.writer(out, lineterminator="\r\n")
    w.writerow(["Record ID", "Captured At", "Field", "Crop", "Plant / Sample", "Observation Type",
                "Diagnosis", "Category", "Confidence (%)", "Review Status", "Review Reasons",
                "Soil Moisture (%)", "Soil Condition", "Temperature (°C)", "Humidity (%)",
                "Latitude", "Longitude", "GPS Accuracy (m)", "Advice / Notes", "Media File"])
    with LOCK:
        snapshot = [dict(RECORDS[rid]) for rid in ORDER if rid in RECORDS]
    def cell(value):
        if value is None:
            return ""
        if isinstance(value, str) and value.lstrip(" \t\r")[:1] in ("=", "+", "-", "@"):
            return "'" + value
        return value
    for rec in snapshot:
        v = view(rec, lang)
        r = v.get("result") or {}
        reasons = ", ".join(x.replace("_", " ") for x in r.get("reasons", []))
        review = "Needs review" if r.get("reasons") else ("Model result" if r.get("label") else r.get("status", ""))
        w.writerow([cell(v.get("id")), cell(v.get("ts")), cell(v.get("field")), cell(v.get("crop")), cell(v.get("plot")),
                    cell(v.get("kind")), cell(v.get("name")), cell(r.get("category")),
                    round(r["confidence"] * 100, 1) if r.get("confidence") is not None else "", review, cell(reasons),
                    v.get("soil") if v.get("soil") is not None else "", cell(v.get("soil_state")),
                    v.get("temp") if v.get("temp") is not None else "", v.get("hum") if v.get("hum") is not None else "",
                    v.get("lat") if v.get("lat") is not None else "", v.get("lon") if v.get("lon") is not None else "",
                    v.get("acc") if v.get("acc") is not None else "", cell(v.get("text")), cell(v.get("file"))])
    filename = "agrisahayak-field-report-" + datetime.date.today().strftime("%Y%m%d") + ".csv"
    return Response("\ufeff" + out.getvalue(), mimetype="text/csv; charset=utf-8",
                    headers={"Content-Disposition": "attachment; filename=" + filename})


def _path(rid):
    rec = RECORDS.get(rid)
    return os.path.join(DATA, rec["file"]) if rec else None


@app.get("/api/file/<rid>")
def get_file(rid):
    p = _path(rid)
    if not p or not os.path.exists(p):
        return "not found", 404
    with open(p, "rb") as f:
        return Response(f.read(), mimetype="video/webm" if p.endswith(".webm") else "image/jpeg")


@app.get("/api/thumb/<rid>")
def thumb(rid):
    p = _path(rid)
    if not p or not p.endswith(".jpg") or not os.path.exists(p):
        return "not found", 404
    im = Image.open(p)
    im.thumbnail((220, 220))
    buf = io.BytesIO()
    im.convert("RGB").save(buf, "JPEG", quality=80)
    return Response(buf.getvalue(), mimetype="image/jpeg")


@app.post("/api/frame")
def frame():
    f = request.files.get("file")
    if not f:
        return jsonify(ok=False), 400
    LATEST["frame"] = f.read()
    LATEST["frame_time"] = time.time()
    return jsonify(ok=True)


@app.get("/api/latest.jpg")
def latest():
    if not LATEST["frame"]:
        return "no frame", 404
    return Response(LATEST["frame"], mimetype="image/jpeg", headers={"Cache-Control": "no-store"})


@app.post("/api/rover")
def rover():
    d = request.get_json(silent=True) or {}
    cmd = str(d.get("cmd", "S")).upper()[:1]
    if cmd not in ("F", "B", "L", "R", "S"):
        return jsonify(ok=False, error="bad command"), 400
    try:
        speed = max(0, min(255, int(d.get("speed", 150))))
    except (TypeError, ValueError):
        speed = 150
    if speed != ROVER["sent_speed"]:
        send_serial(("V%d\n" % speed).encode())
        ROVER["sent_speed"] = speed
    if cmd != ROVER["cmd"]:
        print("[rover] command %s speed %d%s" % (cmd, speed, "" if SER else "   (simulation, nothing sent)"))
    ROVER["cmd"], ROVER["time"], ROVER["speed"] = cmd, time.time(), speed
    send_serial((cmd + "\n").encode())
    return jsonify(ok=True, cmd=cmd, speed=speed)


@app.route("/api/setup", methods=["GET", "POST"])
def setup():
    if request.method == "POST":
        d = request.get_json(silent=True) or {}
        f = str(d.get("field", "")).strip()[:60]
        if f:
            STATE["field"] = f
            save_settings()
    return jsonify(ok=True, field=STATE["field"])


@app.post("/api/gps")
def gps_post():
    d = request.get_json(silent=True) or {}
    ok = set_gps(clean(d.get("src") or "phone", 20), d.get("lat"), d.get("lon"), d.get("acc"))
    return jsonify(ok=ok)


CMD_OK = ("camera_on", "camera_off", "photo", "clip", "auto_on", "auto_off")


@app.post("/api/tablet/cmd")
def tablet_cmd():
    d = request.get_json(silent=True) or {}
    cmd = d.get("cmd")
    if cmd not in CMD_OK:
        return jsonify(ok=False, error="unknown command"), 400
    try:
        interval = max(2, min(600, int(d.get("interval", 10))))
    except (TypeError, ValueError):
        interval = 10
    with LOCK:
        CMDQ.append({"n": len(CMDQ) + 1, "cmd": cmd, "interval": interval, "t": time.time()})
    return jsonify(ok=True, tablet_online=tablet_online())


@app.post("/api/tablet/sync")
def tablet_sync():
    """The tablet calls this about 4 times a second: it reports its state, the Arduino lines it read, and its GPS.
    It gets back new commands from the dashboard, lines to write to the Arduino, and the current rover command."""
    d = request.get_json(silent=True) or {}
    TABLET["state"], TABLET["seen"] = (d.get("state") or {}), time.time()
    for line in (d.get("lines") or [])[-60:]:
        if isinstance(line, str):
            ingest_line(line[:80])
    s_val = d.get("soil")
    if isinstance(s_val, (int, float)):
        LATEST["soil"], LATEST["soil_time"] = float(s_val), time.time()
        SOIL_HIST.append(float(s_val))
    g = d.get("gps")
    if isinstance(g, dict):
        set_gps("tablet", g.get("lat"), g.get("lon"), g.get("acc"))
    try:
        after, dev_after = int(d.get("after") or 0), int(d.get("dev_after") or 0)
    except (TypeError, ValueError):
        after, dev_after = 0, 0
    with LOCK:
        last, dlast = len(CMDQ), len(DEVQ)
        cmds = [c for c in CMDQ if c["n"] > after][-10:]
        dev = [x for x in DEVQ if x["n"] > dev_after][-10:]
    return jsonify(cmds=cmds, last=last, dev=dev, dev_last=dlast, now=time.time(), rover={"cmd": ROVER["cmd"], "speed": ROVER["speed"]})


DEV_OK = {"pump": lambda v: "P%d" % max(1, min(10, int(v or 3))), "pump_off": lambda v: "Q", "servo": lambda v: "A%d" % max(0, min(180, int(v or 90))),
          "scan": lambda v: "N", "auto_water": lambda v: "W%d" % (1 if v else 0), "safety": lambda v: "I%d" % (1 if v else 0),
          "stop_all": lambda v: "X", "cal_air": lambda v: "K0", "cal_water": lambda v: "K1", "status": lambda v: "?", "ping": lambda v: "H", "raw": lambda v: "C"}


@app.post("/api/device")
def device():
    """Dashboard buttons for the Arduino tools (pump, servo, scan, safety, calibration)."""
    d = request.get_json(silent=True) or {}
    cmd = d.get("cmd")
    if cmd not in DEV_OK:
        return jsonify(ok=False, error="unknown device command"), 400
    try:
        line = DEV_OK[cmd](d.get("value"))
    except (TypeError, ValueError):
        return jsonify(ok=False, error="bad value"), 400
    device_line(line)
    linked = (tablet_online() and TABLET["state"].get("serial") == "connected") or bool(SER)
    return jsonify(ok=True, line=line, arduino_linked=linked)


@app.get("/api/voice/status")
def voice_status():
    return jsonify(VOICE.status())


@app.get("/api/tts/<job_id>")
def tts_job(job_id):
    if not re.fullmatch(r"[a-f0-9]{20}", job_id):
        return jsonify(state="missing"), 404
    with TTS_JOBS_LOCK:
        job = TTS_JOBS.get(job_id)
    if not job:
        return jsonify(state="missing"), 404
    future = job["future"]
    if not future.done():
        return jsonify(state="pending")
    try:
        audio_url = future.result()
        result = jsonify(state="done", audio_url=audio_url)
    except Exception:
        result = jsonify(state="done", audio_url=None)
    with TTS_JOBS_LOCK:
        TTS_JOBS.pop(job_id, None)
    return result


@app.get("/api/audio/<name>")
def audio_file(name):
    path = os.path.join(VOICE.dir, name)
    if not re.fullmatch(r"[A-Za-z0-9_]{1,60}\.wav", name) or not os.path.isfile(path):
        return "not found", 404
    return send_file(path, mimetype="audio/wav", max_age=0)


def voice_context(lang):
    """What the answers are built from: saved scans, soil, sensors."""
    with LOCK:
        ids = list(ORDER)[-300:]
    views = [view(RECORDS[i], "en") for i in reversed(ids)]
    soil = LATEST["soil"] if time.time() - LATEST["soil_time"] < 30 else None
    sens = sens_view()
    return views, soil, sens


def llm_facts():
    views, soil, sens = voice_context("en")
    f = assistant.facts_from(views)
    last = f["scored"][0] if f["scored"] else None
    return {"scans_checked": len(f["scored"]), "healthy": len(f["healthy"]), "plants_with_disease": len(f["sick"]), "needs_second_look": len(f["review"]),
            "latest_result": advice.pretty(last["result"]["label"]) if last else None, "latest_confidence_percent": round(last["result"]["confidence"] * 100) if last else None,
            "soil_moisture_percent": soil, "temperature_c": sens.get("temp"), "humidity_percent": sens.get("hum"), "front_distance_cm": sens.get("dist"),
            "crop_reference": {"potato": "Potato is an edible underground stem tuber, not a fruit.",
                               "tomato": "A tomato is the fruit of a tomato plant.",
                               "chilli": "A chilli is the fruit of a Capsicum plant.",
                               "bell pepper": "Bell pepper is the fruit of a Capsicum plant."},
            "vision_capabilities": "AgriSahayak has a leaf disease classifier, including tomato-leaf diseases, and a live fruit-and-vegetable box detector for apple, cherry, fig, olive, pomegranate, orange, rockmelon, strawberry, potato, tomato, watermelon, and bell pepper. Tomato boxes include only a rough surface-color stage estimate (mostly green, turning, mostly red, or unclear); this cannot confirm maturity. Other supported produce is detected and counted only. It does not diagnose disease on fruit, freshness, or quality, and does not support green chilli with boxes/counts."}


@app.post("/api/voice")
def voice_turn():
    """Audio question in (16 kHz WAV from the tablet or the laptop microphone) -> text, answer and speech out."""
    f = request.files.get("audio")
    if not f:
        return jsonify(ok=False, error="no audio sent"), 400
    in_lang = request.form.get("in_lang", "hi")
    out_lang = request.form.get("out_lang") or (in_lang if in_lang in i18n.LANGS else "hi")
    views, soil, sens = voice_context(out_lang)
    neural_tts = VOICE.tts.engine == "parler"
    out = VOICE.turn(f.read(), in_lang, out_lang, lambda t, l: assistant.answer(t, l, views, soil, summary_text, sens, FARM_PROFILE), llm_facts,
                     synthesize=not neural_tts)
    if out.get("ok"):
        if neural_tts:
            out["audio_job_id"] = queue_speech(out["reply"], out["lang"])
        apply_action(out)
        if request.form.get("to_tablet") == "1":
            push_speak(out["reply"], out["lang"], out.get("audio_url"))
    return jsonify(out)


@app.post("/api/ask")
def ask():
    d = request.get_json(silent=True) or {}
    text = str(d.get("text", ""))[:300]
    lang = d.get("lang") if d.get("lang") in i18n.LANGS else "auto"
    views, soil, sens = voice_context(lang)
    out = assistant.answer(text, lang, views, soil, summary_text, sens, FARM_PROFILE)
    llm_ms = None
    if out["intent"] == "unknown" and VOICE.llm.enabled:
        llm_started = time.perf_counter()
        t = VOICE.llm.answer(text, llm_facts(), out["lang"])
        llm_ms = round((time.perf_counter() - llm_started) * 1000)
        if t:
            out["reply"], out["intent"] = t, "llm"
    out["llm_provider"] = VOICE.llm.last_provider if out["intent"] == "llm" else None
    out["llm_ms"] = llm_ms
    apply_action(out)
    needs_audio = bool(d.get("audio"))
    audio_job_id = None
    if needs_audio and VOICE.tts.engine == "parler":
        audio_job_id = queue_speech(out["reply"], out["lang"])
        out["audio_url"] = None
    else:
        out["audio_url"] = VOICE.synth_url(out["reply"], out["lang"]) if needs_audio else None
    out["audio_job_id"] = audio_job_id
    if d.get("speak_on_tablet"):
        push_speak(out["reply"], out["lang"], out["audio_url"])
    return jsonify(out)


@app.post("/api/support/recommend")
def support_recommend_api():
    """Rank official support routes using the farmer's details and recent field context."""
    d = request.get_json(silent=True) or {}
    views, soil, sens = voice_context("en")
    f = assistant.facts_from(views)
    latest = f["scored"][0] if f["scored"] else None
    latest_name = (latest.get("name") or advice.pretty(latest["result"].get("label"))) if latest else ""
    crop = str(d.get("crop", ""))[:80].strip() or support.detect_crop(latest_name)
    district = str(d.get("district", ""))[:100].strip()
    cultivator = str(d.get("cultivator", ""))[:80].strip()
    field_details = str(d.get("field_details", ""))[:500].strip()
    FARM_PROFILE.clear()
    FARM_PROFILE.update(crop=crop, district=district, cultivator=cultivator,
                       field_details=field_details)
    result = support.recommend(
        crop=crop,
        district=district,
        issue=str(d.get("issue", ""))[:600],
        cultivator=cultivator,
        latest_result=latest_name,
        soil_percent=soil,
        field_details=field_details,
    )
    result["latest_scan"] = latest_name or None
    result["soil_moisture_percent"] = soil
    result["temperature_c"] = sens.get("temp")
    return jsonify(ok=True, **result)


@app.post("/api/introduction")
def project_introduction():
    """Return a localized script and queue it on the natural voice when configured."""
    d = request.get_json(silent=True) or {}
    lang = d.get("lang") if d.get("lang") in i18n.LANGS else "en"
    text = introduction.get(lang)
    audio_job_id = queue_speech(text, lang) if VOICE.tts.engine == "parler" else None
    return jsonify(ok=True, lang=lang, text=text, audio_url=None, audio_job_id=audio_job_id,
                   voice=VOICE.tts.last_voice)


def lan_ips():
    ips = set()
    try:
        for info in socket.getaddrinfo(socket.gethostname(), None, socket.AF_INET):
            ip = info[4][0]
            if not ip.startswith("127."):
                ips.add(ip)
    except Exception:
        pass
    return sorted(ips)


load_records()
load_settings()

if __name__ == "__main__":
    threading.Thread(target=health_logger, daemon=True).start()
    VOICE.start(INFER.submit)
    open_serial()
    threading.Thread(target=watchdog, daemon=True).start()
    print("=" * 60)
    print("AgriSahayak server")
    print("Dashboard (on this laptop):  http://localhost:%d" % config.PORT)
    print("Tablet page (USB mode):      http://localhost:%d/tablet.html" % config.PORT)
    if config.HOST != "127.0.0.1":
        for ip in lan_ips():
            print("Tablet page (Wi-Fi mode):    http://%s:%d/tablet.html" % (ip, config.PORT))
    print("Disease model:", "READY on " + CLF.device if CLF.ready else "NOT READY - " + str(CLF.error))
    vs = VOICE.status()
    print("Voice:         speech recognition %s, speaker %s, LLM %s" % (vs["asr"]["state"] + (" - " + vs["asr"]["error"] if vs["asr"]["error"] else ""), vs["tts"]["engine"], "on" if vs["llm"]["enabled"] else "off"))
    print("Leaf check:   ", "READY (limit %.2f)" % GATE.min if GATE.ready else "OFF - " + str(GATE.error))
    print("Rover:", "Arduino on " + str(config.SERIAL_PORT) if SER else "no Arduino on this laptop (the tablet can link it over USB-OTG)")
    print("Field name:", STATE["field"], "(change it in the dashboard)")
    print("Records already stored:", len(ORDER))
    print("Press Ctrl+C to stop.")
    print("=" * 60)
    app.run(host=config.HOST, port=config.PORT, threaded=True)
