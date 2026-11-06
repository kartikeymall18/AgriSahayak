"""Fail closed if staged repository files contain common secrets or private artifacts."""
from pathlib import Path
import hashlib
import re
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
TOKEN_PATTERNS = (
    re.compile(r"(?i)\b(?:gsk_[A-Za-z0-9]{20,}|xai-[A-Za-z0-9_-]{20,}|hf_[A-Za-z0-9]{20,}|gh[pousr]_[A-Za-z0-9]{20,}|github_pat_[A-Za-z0-9_]{20,}|sk-[A-Za-z0-9]{20,}|AKIA[0-9A-Z]{16})\b"),
    re.compile(r"(?im)^[ \t]*(?:GROQ_API_KEY|XAI_API_KEY|HF_TOKEN|GITHUB_TOKEN|OPENAI_API_KEY)[ \t]*=[ \t]*['\"]?[^ \t\r\n'\"#]{8,}"),
)
PRIVATE_SUFFIXES = {
    ".env", ".pem", ".key", ".jsonl", ".sqlite", ".db", ".safetensors", ".onnx",
    ".pt", ".pth", ".ckpt", ".h5", ".tflite", ".zip", ".7z", ".rar", ".wav",
    ".mp3", ".mp4", ".mov", ".jpg", ".jpeg", ".png", ".webp",
}
PRIVATE_NAMES = {"records.jsonl", "voice_log.jsonl", "settings.json", "credentials.json"}
# These six screenshots were captured from the sanitized review copy's empty
# record store and visually checked. Only the exact reviewed PNG bytes are allowed.
SAFE_PREVIEW_IMAGE_HASHES = {
    Path("docs/dashboard-previews/fasal-saathi-open.png"): "8ad3e12cdedb605489df24235b2784e1c535f2368485e0efa366a6ab491dd4ca",
    Path("docs/dashboard-previews/live-monitor.png"): "8dc549b546890c2d5317f4754126c72f93b4481966c426c9daba3bb08fe255d4",
    Path("docs/dashboard-previews/overview.png"): "ba8aa36aaeb6fd9ca5c7ed6e0f05cacf81ac2009544442ddf4309dbbc3b47a60",
    Path("docs/dashboard-previews/records.png"): "1b5ccab99d7aa2309ccfde73f58d9e0d40cb693508a5729c2bb52459d345c413",
    Path("docs/dashboard-previews/rover.png"): "457f3dbab514074d54fb3beac4a6c2775304f0a3cdc434cfb14f03d98e970313",
    Path("docs/dashboard-previews/support-desk.png"): "47ca9234a9c86df882f330501344ee13e8f4963ac60db8c41d5a730f07398387",
}
USER_PATH = re.compile(r"(?i)\\Users\\[^\\\s]+\\")
EMAIL = re.compile(r"\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b", re.I)


def staged_paths():
    result = subprocess.run(
        ["git", "-C", str(ROOT), "ls-files", "--cached", "-z"],
        check=True, capture_output=True,
    )
    return [Path(item.decode("utf-8")) for item in result.stdout.split(b"\0") if item]


def main():
    issues = []
    try:
        files = staged_paths()
    except (OSError, subprocess.CalledProcessError):
        print("FAIL: run this from an initialized Git repository after staging files.")
        return 2
    if not files:
        print("FAIL: no staged/tracked files found. Stage the files you intend to publish, then scan again.")
        return 2

    for relative in files:
        name = relative.name.lower()
        path = ROOT / relative
        if name == ".env" or (name.startswith(".env.") and name != ".env.example"):
            issues.append((str(relative), "environment secret file"))
        approved_preview = relative in SAFE_PREVIEW_IMAGE_HASHES
        if approved_preview:
            try:
                digest = hashlib.sha256(path.read_bytes()).hexdigest()
            except OSError:
                issues.append((str(relative), "approved dashboard screenshot is missing or unreadable"))
                continue
            if digest != SAFE_PREVIEW_IMAGE_HASHES[relative]:
                issues.append((str(relative), "dashboard screenshot differs from the visually reviewed privacy-safe image"))
            continue
        if name in PRIVATE_NAMES or relative.suffix.lower() in PRIVATE_SUFFIXES:
            issues.append((str(relative), "private data, media, cache, or model artifact"))
        try:
            text = path.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            issues.append((str(relative), "file could not be inspected"))
            continue
        if USER_PATH.search(text):
            issues.append((str(relative), "personal Windows user path"))
        if EMAIL.search(text):
            issues.append((str(relative), "email address; confirm it is intentionally public"))
        for pattern in TOKEN_PATTERNS:
            if pattern.search(text):
                issues.append((str(relative), "credential-like value"))
                break

    if issues:
        for path, reason in sorted(set(issues)):
            print(f"BLOCK: {path} — {reason}")
        print("Privacy scan failed. Remove sensitive files/values from the staged changes and scan again.")
        return 1
    print(f"PASS: scanned {len(files)} staged files; no common API keys, personal paths/emails, or private artifact types found.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
