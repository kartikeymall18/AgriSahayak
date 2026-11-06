# Security and privacy

AgriSahayak is a demonstration prototype, not a hardened internet service. The local dashboard API has no user authentication. Bind to `127.0.0.1` unless you intentionally need a tablet to reach the laptop over a trusted private network; never port-forward it to the public internet.

Never commit API tokens, `.env` files, records, field photos, voice recordings, or model/data artifacts. Before committing, stage the intended source files and run:

```powershell
python scripts/privacy_audit.py
```

The scanner checks staged paths and common token formats; it is a useful guard, not a guarantee that all personal or confidential content has been found. Review the staged file list and inspect the GitHub repository before publishing.

