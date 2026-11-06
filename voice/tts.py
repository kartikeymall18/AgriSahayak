"""Text to speech. Engines (set TTS_ENGINE in config.py or AGRI_TTS_ENGINE):
  windows : the voices built into Windows (works offline, needs a Hindi voice installed for Hindi, Bhojpuri, Maithili)
  parler  : Indic Parler-TTS neural voice, runs in its own program (tts_server.py) so its packages cannot break this one
  fake    : a short beep, for tests
  none    : no audio from the laptop (the tablet then uses its own voice)
Bhojpuri has no native voice anywhere yet: its Devanagari text is read with the Hindi voice and is only approximate."""
import json
import os
import struct
import subprocess
import tempfile
import time
import urllib.request
import wave
import math
import threading

CULTURES = {"hi": "hi-IN", "bho": "hi-IN", "mai": "hi-IN", "en": "en-US,en-GB,en-IN"}
PS_SCRIPT = r'''
$ErrorActionPreference = 'Stop'
$winrtVoices = @()
try {
  Add-Type -AssemblyName System.Runtime.WindowsRuntime
  $synthType = [Windows.Media.SpeechSynthesis.SpeechSynthesizer, Windows.Media.SpeechSynthesis, ContentType=WindowsRuntime]
  $winrtVoices = @($synthType::AllVoices)
} catch { $winrtVoices = @() }
function Wait-WinRTOperation($operation, [Type]$resultType) {
  $method = [System.WindowsRuntimeSystemExtensions].GetMethods([System.Reflection.BindingFlags]'Public,Static') |
    Where-Object { $_.Name -eq 'AsTask' -and $_.IsGenericMethodDefinition -and $_.GetGenericArguments().Length -eq 1 -and $_.GetParameters().Length -eq 1 -and $_.GetParameters()[0].ParameterType.Name -eq 'IAsyncOperation`1' } |
    Select-Object -First 1
  $task = $method.MakeGenericMethod($resultType).Invoke($null, @($operation))
  $task.Wait()
  return $task.Result
}
if ($env:AGRI_TTS_LIST -eq '1') {
  $seen = @{}
  foreach ($voice in $winrtVoices) {
    $key = $voice.DisplayName + '|' + $voice.Language
    $seen[$key] = $true
    Write-Output ('V:' + $key)
  }
  try {
    Add-Type -AssemblyName System.Speech
    $sapi = New-Object System.Speech.Synthesis.SpeechSynthesizer
    foreach ($voice in $sapi.GetInstalledVoices()) {
      if ($voice.Enabled) {
        $key = $voice.VoiceInfo.Name + '|' + $voice.VoiceInfo.Culture.Name
        if (-not $seen.ContainsKey($key)) { Write-Output ('V:' + $key) }
      }
    }
    $sapi.Dispose()
  } catch {}
  exit 0
}
$cultures = $env:AGRI_TTS_CULTURES -split ','
$v = $null
$preferred = $env:AGRI_TTS_PREFERRED
if ($preferred) { $v = $winrtVoices | Where-Object { $_.DisplayName -like ('*' + $preferred + '*') } | Select-Object -First 1 }
foreach ($c in $cultures) {
  if ($v) { break }
  $v = $winrtVoices | Where-Object { $_.Language -eq $c } | Select-Object -First 1
  if ($v) { break }
}
if ($v) {
  try {
    $synth = New-Object Windows.Media.SpeechSynthesis.SpeechSynthesizer
    $synth.Voice = $v
    $audio = Wait-WinRTOperation ($synth.SynthesizeTextToStreamAsync($env:AGRI_TTS_TEXT)) ([Windows.Media.SpeechSynthesis.SpeechSynthesisStream, Windows.Media.SpeechSynthesis, ContentType=WindowsRuntime])
    $reader = New-Object Windows.Storage.Streams.DataReader($audio.GetInputStreamAt(0))
    $null = Wait-WinRTOperation ($reader.LoadAsync([uint32]$audio.Size)) ([uint32])
    $bytes = New-Object byte[] ([int]$audio.Size)
    $reader.ReadBytes($bytes)
    [System.IO.File]::WriteAllBytes($env:AGRI_TTS_OUT, $bytes)
    $reader.Dispose()
    $synth.Dispose()
    Write-Output ('VOICE:' + $v.DisplayName)
    exit 0
  } catch {
    if ($reader) { $reader.Dispose() }
    if ($synth) { $synth.Dispose() }
  }
}
Add-Type -AssemblyName System.Speech
$s = New-Object System.Speech.Synthesis.SpeechSynthesizer
$v = $null
if ($preferred) { $v = $s.GetInstalledVoices() | Where-Object { $_.Enabled -and $_.VoiceInfo.Name -like ('*' + $preferred + '*') } | Select-Object -First 1 }
foreach ($c in $cultures) {
  if ($v) { break }
  $v = $s.GetInstalledVoices() | Where-Object { $_.Enabled -and $_.VoiceInfo.Culture.Name -eq $c } | Select-Object -First 1
  if ($v) { break }
}
if (-not $v) { Write-Output 'NOVOICE'; exit 3 }
$s.SelectVoice($v.VoiceInfo.Name)
$s.Rate = [int]$env:AGRI_TTS_RATE
$s.SetOutputToWaveFile($env:AGRI_TTS_OUT)
$s.Speak($env:AGRI_TTS_TEXT)
$s.Dispose()
if ($v.VoiceInfo) { Write-Output ('VOICE:' + $v.VoiceInfo.Name) } else { Write-Output ('VOICE:' + $v.DisplayName) }
'''


def _engine():
    e = os.environ.get("AGRI_TTS_ENGINE")
    if e:
        return e.strip().lower()
    try:
        import config
        return str(getattr(config, "TTS_ENGINE", "windows")).lower()
    except Exception:
        return "windows"


def _url():
    try:
        import config
        return getattr(config, "TTS_URL", "http://127.0.0.1:5005/tts")
    except Exception:
        return "http://127.0.0.1:5005/tts"


class TTS:
    def __init__(self, outdir):
        self.outdir = outdir
        os.makedirs(outdir, exist_ok=True)
        self.engine = _engine()
        self.last_voice = None
        self.note = ""
        self._voices = None
        self._ps = None
        self._neural_proc = None
        self._neural_lock = threading.Lock()
        self._neural_retry_after = 0.0

    def _neural_ready(self):
        try:
            health = _url().rsplit("/", 1)[0] + "/health"
            with urllib.request.urlopen(health, timeout=0.35) as r:
                ready = json.loads(r.read()).get("ready") is True
                if ready:
                    self._neural_retry_after = 0.0
                return ready
        except Exception:
            return False

    def prepare(self):
        """Start the optional Indic neural voice without delaying dashboard startup."""
        if self.engine != "parler" or os.name != "nt" or self._neural_ready():
            return
        with self._neural_lock:
            if self._neural_ready() or (self._neural_proc is not None and self._neural_proc.poll() is None):
                return
            if time.time() < self._neural_retry_after:
                return
            if self._neural_proc is not None and self._neural_proc.poll() is not None:
                self._neural_retry_after = time.time() + 60
            root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            py = os.path.join(root, "tts_env", "Scripts", "python.exe")
            server = os.path.join(root, "tts_server.py")
            if not (os.path.isfile(py) and os.path.isfile(server)):
                self.note = "Indic neural voice files are missing; Windows voice will be used."
                return
            env = dict(os.environ)
            env.update({"HF_HUB_OFFLINE": "1", "TRANSFORMERS_OFFLINE": "1", "PYTHONUTF8": "1"})
            try:
                flags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
                self._neural_proc = subprocess.Popen([py, server], cwd=root, env=env,
                    stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                    creationflags=flags)
                self.note = "Loading Indic neural voice in the background; Windows voice is the fallback."
            except Exception as e:
                self.note = "Could not start Indic neural voice; Windows voice will be used: " + str(e)[:100]

    # ---------- Windows built-in voices ----------
    def _run_ps(self, env_extra, timeout=40):
        if os.name != "nt":
            raise RuntimeError("The Windows voice engine only works on Windows.")
        if self._ps is None:
            self._ps = os.path.join(tempfile.gettempdir(), "agri_tts.ps1")
            with open(self._ps, "w", encoding="utf-8-sig") as f:
                f.write(PS_SCRIPT)
        env = dict(os.environ)
        env.update(env_extra)
        return subprocess.run(["powershell", "-NoProfile", "-NonInteractive", "-ExecutionPolicy", "Bypass", "-File", self._ps],
                              env=env, capture_output=True, text=True, timeout=timeout, encoding="utf-8", errors="replace")

    def voices(self, refresh=False):
        """Installed Windows voices as [(name, culture)]."""
        if self._voices is None or refresh:
            try:
                r = self._run_ps({"AGRI_TTS_LIST": "1"})
                self._voices = [tuple(line[2:].split("|", 1)) for line in r.stdout.splitlines() if line.startswith("V:") and "|" in line]
            except Exception as e:
                self.note = str(e)
                self._voices = []
        return self._voices

    def _synth_windows(self, text, lang, out):
        preferred = "Microsoft Zira" if lang == "en" else "Microsoft Kalpana"
        r = self._run_ps({"AGRI_TTS_TEXT": text, "AGRI_TTS_OUT": out, "AGRI_TTS_CULTURES": CULTURES.get(lang, CULTURES["hi"]),
                          "AGRI_TTS_PREFERRED": preferred, "AGRI_TTS_RATE": "0", "AGRI_TTS_LIST": "0"})
        if "NOVOICE" in r.stdout:
            self.note = "No Windows voice for this language. Add it: Settings, Time and language, Speech, Add voices (Hindi)."
            return False
        for line in r.stdout.splitlines():
            if line.startswith("VOICE:"):
                self.last_voice = line[6:].strip()
        ok = os.path.isfile(out) and os.path.getsize(out) > 1000
        if not ok:
            self.note = "Windows voice made no audio. " + (r.stderr or "")[:200]
        return ok

    # ---------- neural voice server ----------
    def _synth_http(self, text, lang, out):
        req = urllib.request.Request(_url(), data=json.dumps({"text": text, "lang": lang}).encode("utf-8"), headers={"Content-Type": "application/json"})
        with urllib.request.urlopen(req, timeout=180) as r:
            data = r.read()
        if len(data) < 1000:
            raise RuntimeError("the voice server sent no audio")
        with open(out, "wb") as f:
            f.write(data)
        self.last_voice = "Indic Parler-TTS"
        return True

    # ---------- tests ----------
    def _synth_fake(self, text, lang, out):
        rate = 16000
        with wave.open(out, "wb") as w:
            w.setnchannels(1); w.setsampwidth(2); w.setframerate(rate)
            w.writeframes(b"".join(struct.pack("<h", int(8000 * math.sin(2 * math.pi * 440 * i / rate))) for i in range(rate // 4)))
        self.last_voice = "fake"
        return True

    def synth(self, text, lang):
        """Returns the file name of the WAV (inside outdir) or None. Never raises."""
        if self.engine in ("none", "off", ""):
            return None
        english_windows = self.engine == "parler" and lang == "en"
        if self.engine == "parler" and not english_windows and not self._neural_ready():
            self.prepare()                         # load the neural voice lazily; this turn still has Windows fallback
        name = "r_%d_%s.wav" % (int(time.time() * 1000), lang)
        out = os.path.join(self.outdir, name)
        try:
            synth_fn = self._synth_windows if english_windows else {"windows": self._synth_windows, "parler": self._synth_http, "fake": self._synth_fake}.get(self.engine, self._synth_windows)
            ok = synth_fn(text, lang, out)
            if ok:
                self.note = ""
        except Exception as e:
            self.note = "%s voice failed: %s" % (self.engine, str(e)[:160])
            ok = False
            if self.engine == "parler" and not english_windows:   # the neural server is down: use the Windows voice instead
                try:
                    ok = self._synth_windows(text, lang, out)
                except Exception as e2:
                    self.note += " | Windows voice also failed: " + str(e2)[:120]
        return name if ok else None

    def status(self):
        return {"engine": self.engine, "voice": self.last_voice, "note": self.note,
                "natural_ready": self._neural_ready() if self.engine == "parler" else False}
