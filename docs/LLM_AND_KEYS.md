# Fasal Saathi: local model and API keys

## Local Ollama model

AgriSahayak's default `config.py` selects `qwen3:4b-instruct` and enables the LLM. Install Ollama from its official site, then use:

```powershell
ollama pull qwen3:4b-instruct
ollama list
```

Keep Ollama running when you start `server.py`. The app tries this local endpoint first. `LOCAL_LLM_TIMEOUT_SEC` sets the time allowed before fallback. A local model is private/offline after download but needs RAM/VRAM and can be slower on CPU.

## Optional Groq or xAI fallback

Create a provider key in your own account. Do not paste the key into source code, a screenshot, GitHub, or this chat. In the same PowerShell window used to launch the app, set only the provider you use:

```powershell
$env:GROQ_API_KEY = "PASTE_YOUR_GROQ_KEY_HERE"
# or, if using xAI:
$env:XAI_API_KEY = "PASTE_YOUR_XAI_KEY_HERE"
python server.py
```

The key is inherited by the server process for that PowerShell session. Close the window to clear the temporary environment value. The public `config.py` values are intentionally blank; `voice/llm.py` reads the environment variables as overrides.

An online fallback requires network access and may incur account-specific usage or rate limits. The API is optional; without it, the local model and fixed safe replies remain available.

