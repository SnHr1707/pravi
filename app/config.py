"""Runtime configuration, read from environment variables (or a local .env file)."""
import os
import secrets
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent

# Load a local .env file if present (never committed; see .env.example)
_env = BASE_DIR / ".env"
if _env.exists():
    for line in _env.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, v = line.split("=", 1)
        os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))

# On serverless hosts (Vercel) only /tmp is writable; there you should always set DATABASE_URL (Neon).
_local_db = "/tmp/pravi.db" if os.getenv("VERCEL") else BASE_DIR / "pravi.db"
DATABASE_URL = os.getenv("DATABASE_URL", "").strip() or f"sqlite:///{_local_db}"
if DATABASE_URL.startswith("postgres://"):  # Neon/Heroku style URLs
    DATABASE_URL = "postgresql://" + DATABASE_URL[len("postgres://"):]

_jwt = os.getenv("JWT_SECRET", "").strip()
JWT_SECRET_FROM_ENV = bool(_jwt)
if not _jwt and not DATABASE_URL.startswith("sqlite"):
    # stable across serverless instances even if JWT_SECRET was forgotten (set JWT_SECRET in production!)
    import hashlib
    _jwt = hashlib.sha256(("pravi-jwt::" + DATABASE_URL).encode()).hexdigest()
JWT_SECRET = _jwt or secrets.token_urlsafe(48)
JWT_HOURS = int(os.getenv("JWT_HOURS", "").strip() or "8")

# Document reading. The rule-based reader always runs; an LLM is optional.
#   LLM_PROVIDER = none | openai_compatible | anthropic
#   openai_compatible works with open-source models served by Ollama (http://localhost:11434/v1),
#   vLLM, Groq (https://api.groq.com/openai/v1), Together, OpenRouter, ...
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "")
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY", "")
LLM_BASE_URL = os.getenv("LLM_BASE_URL", "") or ("https://openrouter.ai/api/v1" if OPENROUTER_API_KEY else "")
LLM_API_KEY = os.getenv("LLM_API_KEY", "") or OPENROUTER_API_KEY
LLM_PROVIDER = os.getenv("LLM_PROVIDER", "").strip().lower() or (
    "openai_compatible" if LLM_BASE_URL else ("anthropic" if ANTHROPIC_API_KEY else "none"))
# Default: open-weight Qwen on OpenRouter (check current slugs at https://openrouter.ai/qwen),
# or a local Ollama model when LLM_BASE_URL points at Ollama.
_default_model = ("qwen/qwen3.6-27b" if "openrouter.ai" in LLM_BASE_URL else "qwen2.5:7b-instruct") \
    if LLM_PROVIDER == "openai_compatible" else ("claude-sonnet-5" if LLM_PROVIDER == "anthropic" else "")
LLM_MODEL = os.getenv("LLM_MODEL", "").strip() or _default_model

DISTRICT = os.getenv("DISTRICT", "Vadodara")
RESET_DB_ON_START = os.getenv("RESET_DB_ON_START", "false").lower() == "true"
# SEED_DEMO=false starts with only the login accounts and an empty inventory (build everything from your own PDFs)
SEED_DEMO = os.getenv("SEED_DEMO", "true").lower() != "false"

FRONTEND_DIST = BASE_DIR / "frontend" / "dist"
SAMPLE_DIR = BASE_DIR / "sample_docs"
