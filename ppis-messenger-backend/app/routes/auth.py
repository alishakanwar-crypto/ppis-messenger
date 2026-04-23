"""Authentication routes — phone + PIN based login."""

import hashlib
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

logger = logging.getLogger(__name__)
router = APIRouter()

JWT_SECRET = os.environ.get("JWT_SECRET", "ppis-messenger-secret-2026")
JWT_ALGORITHM = "HS256"
JWT_EXPIRE_DAYS = 90


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
    return hashlib.sha256(pin.encode()).hexdigest()


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


# ---- Endpoints ----

@router.post("/request-otp")
async def request_otp(body: PhoneRequest):
    """Send OTP to a phone number. For now, returns the OTP directly (demo mode)."""
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

    logger.info(f"OTP for {phone}: {code}")
    # In production, send OTP via SMS. For now, return it.
    return {"success": True, "message": "OTP sent", "otp_preview": code}


@router.post("/verify-otp")
async def verify_otp(body: VerifyOTPRequest):
    """Verify OTP and return JWT token. Auto-registers new users."""
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
    """Set a 4-digit PIN for quick login."""
    if len(body.pin) < 4:
        raise HTTPException(status_code=400, detail="PIN must be at least 4 digits")
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
    """Login with phone + PIN (quick login)."""
    phone = _normalize_phone(body.phone)
    conn = get_db()
    user = conn.execute("SELECT * FROM users WHERE phone = ?", (phone,)).fetchone()
    if not user or not user["pin_hash"]:
        conn.close()
        raise HTTPException(status_code=400, detail="No PIN set. Use OTP login.")
    if user["pin_hash"] != _hash_pin(body.pin):
        conn.close()
        raise HTTPException(status_code=400, detail="Invalid PIN")

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
