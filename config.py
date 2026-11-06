# Edit this file only when the guide tells you to.

# "127.0.0.1" = USB mode only (safest).  "0.0.0.0" = also allow Wi-Fi.
HOST = "127.0.0.1"
PORT = 8000

# Arduino Uno port, for example "COM5". Leave None until the rover is built.
SERIAL_PORT = None
BAUD = 9600

# Below this confidence the result is marked "needs human review".
CONF_MIN = 0.60

# Soil moisture is now a PERCENT (0 = dry air, 100 = water), calculated by the Arduino.
# Below DRY_BELOW = dry, above WET_ABOVE = too wet. Adjust after calibration.
SOIL_DRY_BELOW = 30
SOIL_WET_ABOVE = 70

USE_LLM = True
LLM_MODEL = "qwen3:4b-instruct"
# Local Qwen is tried first. After this many seconds, use Groq or xAI if configured.
LOCAL_LLM_TIMEOUT_SEC = 1.8
XAI_API_KEY = ""
GROQ_API_KEY = ""
GROQ_MODEL = "openai/gpt-oss-20b"
GROQ_API_TIMEOUT_SEC = 8
XAI_MODEL = "grok-4.7"
XAI_API_TIMEOUT_SEC = 8
TTS_ENGINE = "parler"

