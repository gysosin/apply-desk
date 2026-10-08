"""Single-user login: PBKDF2 password hash in the config, in-memory session tokens."""
import hashlib
import hmac
import secrets
import time

from app import store

SESSION_TTL = 30 * 24 * 3600
_sessions = {}  # token -> (username, expires_at); ponytail: in-memory, a restart signs you out


def _hash(password, salt):
    return hashlib.pbkdf2_hmac("sha256", password.encode(), bytes.fromhex(salt), 310_000).hex()


def set_password(username, password):
    cfg = store.load_config()
    salt = secrets.token_hex(16)
    cfg["auth"] = {"username": username, "salt": salt, "hash": _hash(password, salt)}
    store.save_config(cfg)
    _sessions.clear()


def verify(username, password):
    a = store.load_config().get("auth") or {}
    if not a:
        return False
    ok_user = hmac.compare_digest(username.strip().lower(), a["username"].lower())
    ok_pass = hmac.compare_digest(_hash(password, a["salt"]), a["hash"])
    return ok_user and ok_pass


def login(username):
    token = secrets.token_urlsafe(32)
    _sessions[token] = (username, time.time() + SESSION_TTL)
    return token


def user_for(token):
    entry = _sessions.get(token or "")
    if not entry or entry[1] < time.time():
        _sessions.pop(token or "", None)
        return None
    return entry[0]


def logout(token):
    _sessions.pop(token or "", None)
