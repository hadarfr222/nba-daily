"""Keys come from environment variables (GitHub Secrets) or a local .env file."""
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def _load_dotenv():
    env = ROOT / ".env"
    if not env.exists():
        return
    for line in env.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, v = line.split("=", 1)
        os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))


_load_dotenv()

YOUTUBE_API_KEY = os.environ.get("YOUTUBE_API_KEY", "").strip()
ODDS_API_KEY = os.environ.get("ODDS_API_KEY", "").strip()
