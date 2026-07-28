"""Authentication routes — phone + PIN based login."""

import hashlib
import hmac
import json
import logging
import os
import random
import secrets
import time
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, Header
from jose import JWTError, jwt
from pydantic import BaseModel

from app.database import get_db, ADMIN_NUMBERS
from app.services.whatsapp import send_login_code

logger = logging.getLogger(__name__)
router = APIRouter()

JWT_SECRET = os.environ.get("JWT_SECRET") or secrets.token_urlsafe(48)
JWT_ALGORITHM = "HS256"
JWT_EXPIRE_DAYS = 90
DEMO_OTP_ENABLED = os.environ.get("DEMO_OTP_ENABLED", "false").lower() == "true"
PIN_MIN_LENGTH = int(os.environ.get("PIN_MIN_LENGTH", "8"))
ADMIN_BOOTSTRAP_PHONE = os.environ.get("ADMIN_BOOTSTRAP_PHONE", "")
ADMIN_BOOTSTRAP_PIN = os.environ.get("ADMIN_BOOTSTRAP_PIN", "")
LOGIN_MAX_FAILURES = int(os.environ.get("LOGIN_MAX_FAILURES", "5"))
LOGIN_WINDOW_SECONDS = int(os.environ.get("LOGIN_WINDOW_SECONDS", "900"))
SETUP_CODE_MAX_REQUESTS = 3
SETUP_CODE_WINDOW_SECONDS = 900
LOGIN_STATUS_MAX_REQUESTS = 20
_failed_pin_attempts: dict[str, list[float]] = {}
_setup_code_requests: dict[str, list[float]] = {}
_login_status_requests: dict[str, list[float]] = {}


# ---- Models ----

class PhoneRequest(BaseModel):
    phone: str

class VerifyOTPRequest(BaseModel):
    phone: str
    code: str

class SetPinRequest(BaseModel):
    pin: str

class LoginPinRequest(BaseModel):
    phone: str
    pin: str

class LoginStatusRequest(BaseModel):
    phone: str

class SetupPinRequest(BaseModel):
    phone: str
    code: str
    pin: str


# ---- Helpers ----

def _get_children_with_photos(children: list[dict]) -> list[dict]:
    """Enrich children list with photo URLs from student_photos table."""
    if not children:
        return children
    conn = get_db()
    enriched = []
    for child in children:
        name = child.get("name", "")
        grade = child.get("grade", "")
        photo_row = conn.execute(
            "SELECT id FROM student_photos WHERE student_name = ? AND grade = ?",
            (name, grade),
        ).fetchone()
        entry = {**child}
        if photo_row:
            entry["photo_id"] = photo_row["id"]
        enriched.append(entry)
    conn.close()
    return enriched


def _build_user_response(user_row) -> dict:
    """Build a consistent user response dict with children photo info."""
    children = json.loads(user_row["children"] or "[]")
    children_with_photos = _get_children_with_photos(children)
    # Safely access avatar_url (may not exist in older databases)
    try:
        avatar_url = user_row["avatar_url"] or ""
    except (IndexError, KeyError):
        avatar_url = ""

    return {
        "id": user_row["id"],
        "phone": user_row["phone"],
        "name": user_row["name"],
        "role": user_row["role"],
        "grade": user_row["grade"],
        "children": children_with_photos,
        "has_pin": bool(user_row["pin_hash"]),
        "avatar_url": avatar_url,
    }


def _normalize_phone(phone: str) -> str:
    phone = phone.strip().replace(" ", "").replace("-", "").replace("+", "")
    if phone.startswith("91") and len(phone) > 10:
        phone = phone[2:]
    return phone


def _hash_pin(pin: str) -> str:
    salt = secrets.token_bytes(16)
    digest = hashlib.scrypt(pin.encode(), salt=salt, n=2**14, r=8, p=1)
    return f"scrypt${salt.hex()}${digest.hex()}"


def _verify_pin(pin: str, pin_hash: str) -> bool:
    if pin_hash.startswith("scrypt$"):
        try:
            _, salt_hex, digest_hex = pin_hash.split("$", 2)
            digest = hashlib.scrypt(
                pin.encode(), salt=bytes.fromhex(salt_hex), n=2**14, r=8, p=1
            )
            return hmac.compare_digest(digest.hex(), digest_hex)
        except (ValueError, TypeError):
            return False
    return hmac.compare_digest(pin_hash, hashlib.sha256(pin.encode()).hexdigest())


def _recent_pin_failures(phone: str) -> list[float]:
    cutoff = time.monotonic() - LOGIN_WINDOW_SECONDS
    recent = [
        attempt
        for attempt in _failed_pin_attempts.get(phone, [])
        if attempt > cutoff
    ]
    if recent:
        _failed_pin_attempts[phone] = recent
    else:
        _failed_pin_attempts.pop(phone, None)
    return recent


def _record_pin_failure(phone: str) -> None:
    attempts = _recent_pin_failures(phone)
    attempts.append(time.monotonic())
    _failed_pin_attempts[phone] = attempts


def _recent_requests(
    requests: dict[str, list[float]], phone: str, window_seconds: int
) -> list[float]:
    cutoff = time.monotonic() - window_seconds
    recent = [attempt for attempt in requests.get(phone, []) if attempt > cutoff]
    if recent:
        requests[phone] = recent
    else:
        requests.pop(phone, None)
    return recent


def bootstrap_admin_pin() -> None:
    if not ADMIN_BOOTSTRAP_PHONE and not ADMIN_BOOTSTRAP_PIN:
        return
    if not ADMIN_BOOTSTRAP_PHONE or not ADMIN_BOOTSTRAP_PIN:
        raise RuntimeError(
            "Both ADMIN_BOOTSTRAP_PHONE and ADMIN_BOOTSTRAP_PIN are required"
        )
    if len(ADMIN_BOOTSTRAP_PIN) < PIN_MIN_LENGTH:
        raise RuntimeError(
            f"ADMIN_BOOTSTRAP_PIN must be at least {PIN_MIN_LENGTH} characters"
        )

    phone = _normalize_phone(ADMIN_BOOTSTRAP_PHONE)
    conn = get_db()
    user = conn.execute(
        "SELECT id, role FROM users WHERE phone = ?", (phone,)
    ).fetchone()
    if not user or user["role"] != "admin":
        conn.close()
        raise RuntimeError("ADMIN_BOOTSTRAP_PHONE must belong to a seeded admin")
    conn.execute(
        "UPDATE users SET pin_hash = ? WHERE id = ?",
        (_hash_pin(ADMIN_BOOTSTRAP_PIN), user["id"]),
    )
    conn.commit()
    conn.close()
    logger.info("Admin passcode configured for production login")


def create_token(user_id: int, role: str, phone: str) -> str:
    payload = {
        "sub": str(user_id),
        "role": role,
        "phone": phone,
        "exp": datetime.now(timezone.utc) + timedelta(days=JWT_EXPIRE_DAYS),
    }
    return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)


def get_current_user(authorization: str = Header(None)) -> dict:
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Not authenticated")
    token = authorization.split(" ", 1)[1]
    try:
        payload = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
        return {
            "user_id": int(payload["sub"]),
            "role": payload.get("role", "parent"),
            "phone": payload.get("phone", ""),
        }
    except JWTError:
        raise HTTPException(status_code=401, detail="Invalid token")


def require_admin(user: dict = Depends(get_current_user)) -> dict:
    if user["role"] not in ("admin",):
        raise HTTPException(status_code=403, detail="Admin access required")
    return user


def require_portal_user(user: dict = Depends(get_current_user)) -> dict:
    if user["role"] not in ("parent", "teacher"):
        raise HTTPException(status_code=403, detail="Portal access required")
    return user


# ---- Endpoints ----

@router.post("/request-otp")
async def request_otp(body: PhoneRequest):
    """Create a local-development OTP when demo mode is explicitly enabled."""
    if not DEMO_OTP_ENABLED:
        raise HTTPException(status_code=404, detail="OTP login is disabled")
    phone = _normalize_phone(body.phone)
    if not phone or len(phone) < 10:
        raise HTTPException(status_code=400, detail="Invalid phone number")

    code = f"{random.randint(100000, 999999)}"
    expires_at = (datetime.now(timezone.utc) + timedelta(minutes=10)).isoformat()

    conn = get_db()
    conn.execute(
        "INSERT INTO otp_codes (phone, code, expires_at) VALUES (?, ?, ?)",
        (phone, code, expires_at),
    )
    conn.commit()
    conn.close()

    return {"success": True, "message": "Demo OTP created", "otp_preview": code}


@router.post("/login-status")
async def login_status(body: LoginStatusRequest):
    """Report whether a phone is allow-listed and has completed PIN setup."""
    phone = _normalize_phone(body.phone)
    if len(_recent_requests(
        _login_status_requests, phone, SETUP_CODE_WINDOW_SECONDS
    )) >= LOGIN_STATUS_MAX_REQUESTS:
        raise HTTPException(
            status_code=429, detail="Too many requests. Try again later."
        )
    _login_status_requests.setdefault(phone, []).append(time.monotonic())
    conn = get_db()
    user = conn.execute(
        "SELECT pin_hash FROM users WHERE phone = ?", (phone,)
    ).fetchone()
    conn.close()
    return {
        "authorized": phone in ADMIN_NUMBERS,
        "has_pin": bool(user and user["pin_hash"]),
    }


@router.post("/request-setup-code")
async def request_setup_code(body: PhoneRequest):
    """Send a one-time WhatsApp code for first-run or reset enrollment."""
    phone = _normalize_phone(body.phone)
    if phone not in ADMIN_NUMBERS:
        raise HTTPException(
            status_code=403,
            detail="This number is not authorized to access the ERP",
        )
    if len(_recent_requests(
        _setup_code_requests, phone, SETUP_CODE_WINDOW_SECONDS
    )) >= SETUP_CODE_MAX_REQUESTS:
        raise HTTPException(
            status_code=429, detail="Too many requests. Try again later."
        )
    _setup_code_requests.setdefault(phone, []).append(time.monotonic())

    code = f"{secrets.randbelow(900000) + 100000}"
    expires_at = (datetime.now(timezone.utc) + timedelta(minutes=10)).isoformat()
    conn = get_db()
    conn.execute(
        "INSERT INTO otp_codes (phone, code, expires_at) VALUES (?, ?, ?)",
        (phone, code, expires_at),
    )
    conn.commit()
    conn.close()

    if not await send_login_code(phone, code):
        raise HTTPException(
            status_code=502, detail="Unable to send login code. Try again later."
        )
    return {"success": True}


@router.post("/setup-pin")
async def setup_pin(body: SetupPinRequest):
    """Verify ownership, set or reset a passcode, and log the user in."""
    phone = _normalize_phone(body.phone)
    if phone not in ADMIN_NUMBERS:
        raise HTTPException(
            status_code=403,
            detail="This number is not authorized to access the ERP",
        )
    if len(body.pin) < PIN_MIN_LENGTH:
        raise HTTPException(
            status_code=400,
            detail=f"Passcode must be at least {PIN_MIN_LENGTH} characters",
        )
    if len(_recent_pin_failures(phone)) >= LOGIN_MAX_FAILURES:
        raise HTTPException(
            status_code=429, detail="Too many failed attempts. Try again later."
        )

    conn = get_db()
    conn.execute("BEGIN IMMEDIATE")
    now = datetime.now(timezone.utc).isoformat()
    otp = conn.execute(
        """SELECT id, code FROM otp_codes
           WHERE phone = ? AND used = 0 AND expires_at > ?
           ORDER BY id DESC LIMIT 1""",
        (phone, now),
    ).fetchone()
    if not otp or otp["code"] != body.code:
        _record_pin_failure(phone)
        conn.close()
        raise HTTPException(status_code=400, detail="Invalid or expired code")
    conn.execute("UPDATE otp_codes SET used = 1 WHERE id = ?", (otp["id"],))

    user = conn.execute(
        "SELECT * FROM users WHERE phone = ?", (phone,)
    ).fetchone()
    if not user:
        conn.execute(
            "INSERT INTO users (phone, name, role) VALUES (?, ?, ?)",
            (phone, "", "admin"),
        )
    elif user["role"] != "admin":
        conn.execute(
            "UPDATE users SET role = 'admin' WHERE id = ?", (user["id"],)
        )

    conn.execute(
        "UPDATE users SET pin_hash = ? WHERE phone = ?",
        (_hash_pin(body.pin), phone),
    )
    conn.commit()
    user = conn.execute(
        "SELECT * FROM users WHERE phone = ?", (phone,)
    ).fetchone()
    _failed_pin_attempts.pop(phone, None)
    token = create_token(user["id"], user["role"], phone)
    conn.close()

    return {
        "success": True,
        "token": token,
        "user": _build_user_response(user),
    }


@router.post("/verify-otp")
async def verify_otp(body: VerifyOTPRequest):
    """Verify a local-development OTP and return a JWT token."""
    if not DEMO_OTP_ENABLED:
        raise HTTPException(status_code=404, detail="OTP login is disabled")
    phone = _normalize_phone(body.phone)
    conn = get_db()

    otp = conn.execute(
        "SELECT id, code, expires_at, used FROM otp_codes WHERE phone = ? ORDER BY id DESC LIMIT 1",
        (phone,),
    ).fetchone()

    if not otp or otp["used"]:
        conn.close()
        raise HTTPException(status_code=400, detail="No OTP found. Request a new one.")

    if otp["code"] != body.code:
        conn.close()
        raise HTTPException(status_code=400, detail="Invalid OTP")

    # Mark used
    conn.execute("UPDATE otp_codes SET used = 1 WHERE id = ?", (otp["id"],))

    # Find or create user
    user = conn.execute("SELECT * FROM users WHERE phone = ?", (phone,)).fetchone()
    if not user:
        role = "admin" if phone in ADMIN_NUMBERS else "parent"
        conn.execute(
            "INSERT INTO users (phone, name, role) VALUES (?, ?, ?)",
            (phone, "", role),
        )
        conn.commit()
        user = conn.execute("SELECT * FROM users WHERE phone = ?", (phone,)).fetchone()

    conn.execute(
        "UPDATE users SET last_seen = CURRENT_TIMESTAMP WHERE id = ?", (user["id"],)
    )
    conn.commit()

    token = create_token(user["id"], user["role"], phone)
    conn.close()

    return {
        "success": True,
        "token": token,
        "user": _build_user_response(user),
    }


@router.post("/set-pin")
async def set_pin(body: SetPinRequest, user: dict = Depends(get_current_user)):
    """Set a passcode for phone-based login."""
    if len(body.pin) < PIN_MIN_LENGTH:
        raise HTTPException(
            status_code=400,
            detail=f"Passcode must be at least {PIN_MIN_LENGTH} characters",
        )
    conn = get_db()
    conn.execute(
        "UPDATE users SET pin_hash = ? WHERE id = ?",
        (_hash_pin(body.pin), user["user_id"]),
    )
    conn.commit()
    conn.close()
    return {"success": True}


@router.post("/login-pin")
async def login_pin(body: LoginPinRequest):
    """Login with phone and a throttled passcode check."""
    phone = _normalize_phone(body.phone)
    if len(_recent_pin_failures(phone)) >= LOGIN_MAX_FAILURES:
        raise HTTPException(
            status_code=429,
            detail="Too many failed attempts. Try again later.",
        )

    conn = get_db()
    user = conn.execute("SELECT * FROM users WHERE phone = ?", (phone,)).fetchone()
    if (
        not user
        or not user["pin_hash"]
        or not _verify_pin(body.pin, user["pin_hash"])
    ):
        conn.close()
        _record_pin_failure(phone)
        raise HTTPException(status_code=400, detail="Invalid phone or passcode")

    _failed_pin_attempts.pop(phone, None)
    conn.execute(
        "UPDATE users SET last_seen = CURRENT_TIMESTAMP WHERE id = ?", (user["id"],)
    )
    conn.commit()
    token = create_token(user["id"], user["role"], phone)
    conn.close()

    return {
        "success": True,
        "token": token,
        "user": _build_user_response(user),
    }


@router.get("/me")
async def get_me(user: dict = Depends(get_current_user)):
    """Get current user profile."""
    conn = get_db()
    row = conn.execute("SELECT * FROM users WHERE id = ?", (user["user_id"],)).fetchone()
    conn.close()
    if not row:
        raise HTTPException(status_code=404, detail="User not found")
    return _build_user_response(row)


@router.put("/profile")
async def update_profile(body: dict, user: dict = Depends(get_current_user)):
    """Update user name."""
    conn = get_db()
    name = body.get("name", "")
    if name:
        conn.execute("UPDATE users SET name = ? WHERE id = ?", (name, user["user_id"]))
        conn.commit()
    conn.close()
    return {"success": True}
