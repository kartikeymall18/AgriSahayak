# Voice setup

Voice is optional. The dashboard and vision features can run without speech recognition or speech output.

## Windows speech output

AgriSahayak can use Windows' installed voices. For Hindi, install a Hindi speech voice from **Settings → Time & language → Speech → Add voices**. English uses an installed English voice. Bhojpuri and Maithili are spoken approximately using a Hindi voice; Windows may not provide native voices for them.

## SraVaani speech recognition

1. Create and activate the repository `.venv` and install `requirements.txt`.
2. Follow the SraVaani model access terms on its [Hugging Face page](https://huggingface.co/ARTPARK-IISc/SraVaani-1.0).
3. Create a Hugging Face **read** token in your own account. Do not put it in a file or commit it.
4. In the same PowerShell session, run:

   ```powershell
   $env:HF_TOKEN = "PASTE_YOUR_READ_TOKEN_HERE"
   python download_voice.py
   Remove-Item Env:HF_TOKEN
   ```

5. Run `python voice_check.py` and review the result. The model files stay in the ignored `voice_models/` directory.

## Optional Indic Parler-TTS

The neural TTS service uses a separate `tts_env` so its heavy packages do not conflict with the main app. It needs a compatible PyTorch build, `soundfile`, the Parler-TTS package, and the gated voice model files.

1. Create the separate environment:

   ```powershell
   py -3.11 -m venv tts_env
   tts_env\Scripts\python.exe -m pip install --upgrade pip
   ```

2. Use the [official PyTorch selector](https://pytorch.org/get-started/locally/) to choose a Windows wheel and install it with `tts_env\Scripts\python.exe -m pip install ...` (use the same selected command, replacing `pip3`/`python -m pip` with this environment's Python).
3. Install the optional voice packages:

   ```powershell
   tts_env\Scripts\python.exe -m pip install soundfile
   tts_env\Scripts\python.exe -m pip install git+https://github.com/huggingface/parler-tts.git
   ```

4. After accepting the relevant Hugging Face model terms, set a temporary read token and fetch the voice model files:

   ```powershell
   $env:HF_TOKEN = "PASTE_YOUR_READ_TOKEN_HERE"
   python download_voice.py --parler
   Remove-Item Env:HF_TOKEN
   ```

5. Start the neural voice server in a second terminal with `start_tts.bat`. Set `TTS_ENGINE = "parler"` in `config.py` if it is not already selected, then start the dashboard.

The public source does not include the neural voice model files or a populated environment. Windows speech remains the fallback when the optional voice service is unavailable. The Git package and model terms can change; review upstream requirements before installation.

