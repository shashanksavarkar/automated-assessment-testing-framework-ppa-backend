import secrets
import time

import bcrypt
from fastapi import Cookie, HTTPException

from app import config

COOKIE_NAME = "session_token"
SESSION_TTL_SECONDS = 12 * 60 * 60  # 12 hours

# In-memory session store: token -> (trainer_email, expires_at). Simple on purpose -- this is
# a small internal tool for a handful of trainers, not a multi-instance deployment, so there's
# no need for a shared session backend. Restarting the backend logs everyone out; acceptable
# for this tool's scale.
_sessions: dict[str, tuple[str, float]] = {}

# A dummy hash to check against when the email doesn't exist, so a bad email takes roughly
# the same time as a bad password instead of short-circuiting instantly -- bcrypt.checkpw is
# already constant-time for a given hash, but skipping it entirely for unknown emails would
# leak which emails are registered via response timing.
_DUMMY_HASH = bcrypt.hashpw(b"", bcrypt.gensalt()).decode()


def login(email: str, password: str) -> str | None:
    expected_hash = config.TRAINER_ACCOUNTS.get(email)
    ok = bcrypt.checkpw(password.encode(), (expected_hash or _DUMMY_HASH).encode())
    if expected_hash is None or not ok:
        return None
    token = secrets.token_urlsafe(32)
    _sessions[token] = (email, time.time() + SESSION_TTL_SECONDS)
    return token


def logout(token: str | None):
    if token:
        _sessions.pop(token, None)


def resolve_session(token: str | None) -> str | None:
    if not token or token not in _sessions:
        return None
    email, expires_at = _sessions[token]
    if time.time() > expires_at:
        _sessions.pop(token, None)
        return None
    return email


def require_auth(session_token: str | None = Cookie(default=None)) -> str:
    email = resolve_session(session_token)
    if email is None:
        raise HTTPException(401, "Not logged in.")
    return email
