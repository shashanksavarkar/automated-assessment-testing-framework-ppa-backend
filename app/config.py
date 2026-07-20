import json
import os
import sys
from pathlib import Path

from dotenv import dotenv_values

# backend/ is a sibling of TestCase1/ (the assessment engine), not nested inside it -- both
# live directly under this repo's parent folder. Deliberately does NOT import TestCase1's own
# `config.settings` module: the whole point of the frontend/backend/assessment split is that
# the backend treats the assessment engine as an external program it invokes (via subprocess +
# env vars), not a Python package it links against. That duplicates a handful of small config
# values below, but keeps the two genuinely decoupled -- e.g. backend can be redeployed
# independently without the assessment engine's dependencies (selenium, openai) ever being
# importable in this process. ASSESSMENT_DIR is overridable via env var in case the sibling
# folder is ever renamed or relocated again.
BACKEND_DIR = Path(__file__).resolve().parent.parent
ASSESSMENT_DIR = Path(os.environ.get("ASSESSMENT_DIR", BACKEND_DIR.parent / "TestCase1"))
OUTPUT_DIR = ASSESSMENT_DIR / "output"

# The assessment engine has its own venv with selenium/openai installed; the backend's venv
# does not (and should not -- it only needs fastapi/uvicorn/dotenv). Subprocess calls must use
# the assessment engine's interpreter explicitly, never `sys.executable` from inside this
# process, or every run would fail immediately with ModuleNotFoundError.
if os.name == "nt":
    ASSESSMENT_PYTHON = ASSESSMENT_DIR / ".venv" / "Scripts" / "python.exe"
else:
    ASSESSMENT_PYTHON = ASSESSMENT_DIR / ".venv" / "bin" / "python"
if not ASSESSMENT_PYTHON.exists():
    # Fall back to whatever's on PATH rather than a hard failure at import time -- lets the
    # backend still start (e.g. in a fresh checkout before `pip install` has been run in
    # TestCase1/.venv), failing loudly and specifically only when a run is actually attempted.
    ASSESSMENT_PYTHON = Path(sys.executable)

_env_path = ASSESSMENT_DIR / ".env"
_env = dotenv_values(_env_path) if _env_path.exists() else {}

DEFAULT_MODEL = _env.get("NVIDIA_MODEL", "meta/llama-3.1-8b-instruct")
DEFAULT_RETRIES = int(_env.get("CODING_MAX_RETRIES", "2"))

# Only models confirmed not to queue indefinitely on this NVIDIA NIM account tier -- see
# TestCase1/v1_logs.md bug #2. Kept in sync by hand with config/settings.py's RECOMMENDED_MODELS.
RECOMMENDED_MODELS = ["meta/llama-3.1-8b-instruct"]

TEST_ACCOUNTS = {
    "Default": {
        "email": _env.get("TEST_USER_EMAIL", "ppa@yopmail.com"),
        "name": _env.get("TEST_USER_NAME", "BOT"),
        "mobile": _env.get("TEST_USER_MOBILE", "9999999999"),
        "roll_number": _env.get("TEST_USER_ROLL", "9988774455"),
    }
}
_extra_accounts_json = _env.get("TEST_ACCOUNTS_JSON", "")
if _extra_accounts_json:
    try:
        for _acct in json.loads(_extra_accounts_json):
            TEST_ACCOUNTS[_acct["label"]] = {
                "email": _acct["email"],
                "name": _acct.get("name", "BOT"),
                "mobile": _acct.get("mobile", "9999999999"),
                "roll_number": _acct.get("roll_number", "9988774455"),
            }
    except Exception:
        pass

# Trainers/question setters who can log into this tool -- {email: bcrypt_hash}. Configured
# via TRAINER_ACCOUNTS_JSON in TestCase1/.env as a JSON list:
# [{"email": "priya@programmingpathshala.com", "password_hash": "$2b$..."}].
# Passwords are never stored in plaintext, even in a private .env -- generate a hash with
# `python scripts/hash_password.py "the real password"` and paste the output in.
# Falls back to a single obvious-placeholder account so the tool still runs out of the box in
# dev, with a loud stderr warning so nobody mistakes it for a real credential in production.
import bcrypt

TRAINER_ACCOUNTS = {}
_trainer_accounts_json = _env.get("TRAINER_ACCOUNTS_JSON", "")
if _trainer_accounts_json:
    try:
        for _t in json.loads(_trainer_accounts_json):
            TRAINER_ACCOUNTS[_t["email"]] = _t["password_hash"]
    except Exception:
        pass
if not TRAINER_ACCOUNTS:
    print(
        "[auth] WARNING: TRAINER_ACCOUNTS_JSON not set in TestCase1/.env -- using a "
        "placeholder login (admin / Pass@123) for demo/dev purposes. Set real trainer "
        "accounts before sharing this tool outside your own machine.",
        file=sys.stderr,
    )
    TRAINER_ACCOUNTS = {"admin": bcrypt.hashpw(b"Pass@123", bcrypt.gensalt()).decode()}

# Vite's default dev port, plus an override for wherever the built frontend ends up served
# from on a shared deployment.
CORS_ORIGINS = [o.strip() for o in os.environ.get(
    "BACKEND_CORS_ORIGINS", "http://localhost:5173,http://127.0.0.1:5173"
).split(",") if o.strip()]

RUN_TIMEOUT_SECONDS = 20 * 60
