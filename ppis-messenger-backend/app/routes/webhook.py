"""WhatsApp webhook routes for PPIS Messenger.

Receives incoming WhatsApp messages from Meta Cloud API, stores them in
the messenger database (so they appear on the app dashboard), and sends
bot replies both back to WhatsApp and into the messenger messages table.
"""

import logging
import os
from collections import OrderedDict

from fastapi import APIRouter, Request, Response

from app.database import get_db
from app.services.bot_service import get_bot_response
from app.services.whatsapp_service import (
    is_whatsapp_configured,
    parse_cloud_webhook,
    send_whatsapp_message,
)

logger = logging.getLogger(__name__)
router = APIRouter()

VERIFY_TOKEN = os.environ.get("WHATSAPP_VERIFY_TOKEN", "ppis-messenger-verify-2026")

# Deduplication: track recently processed message IDs (OrderedDict preserves insertion order)
_processed_ids: OrderedDict[str, None] = OrderedDict()
_MAX_PROCESSED = 5000


def _normalize_phone(phone: str) -> str:
    phone = phone.strip().replace(" ", "").replace("-", "").replace("+", "")
    if phone.startswith("91") and len(phone) > 10:
        phone = phone[2:]
    return phone


def _get_or_create_whatsapp_user(conn, phone: str) -> int:
    """Find or create a user record for a WhatsApp sender. Returns user id."""
    normalized = _normalize_phone(phone)
    row = conn.execute("SELECT id FROM users WHERE phone = ?", (normalized,)).fetchone()
    if row:
        return row["id"]
    # Create a new user with whatsapp channel marker
    conn.execute(
        "INSERT OR IGNORE INTO users (phone, name, role, channel) VALUES (?, ?, 'parent', 'whatsapp')",
        (normalized, f"WhatsApp {normalized[-4:]}"),
    )
    conn.commit()
    new_row = conn.execute("SELECT id FROM users WHERE phone = ?", (normalized,)).fetchone()
    return new_row["id"]


def _get_bot_user_id(conn) -> int:
    """Get or create the bot user."""
    row = conn.execute("SELECT id FROM users WHERE phone = 'bot'").fetchone()
    if row:
        return row["id"]
    conn.execute(
        "INSERT INTO users (phone, name, role) VALUES ('bot', 'PPIS Bot', 'bot')"
    )
    conn.commit()
    return conn.execute("SELECT id FROM users WHERE phone = 'bot'").fetchone()["id"]


# ---------------------------------------------------------------------------
# Meta webhook verification (GET)
# ---------------------------------------------------------------------------

@router.get("/webhook/cloud")
async def verify_webhook(request: Request):
    """Meta webhook verification challenge."""
    mode = request.query_params.get("hub.mode")
    token = request.query_params.get("hub.verify_token")
    challenge = request.query_params.get("hub.challenge")

    if mode == "subscribe" and token == VERIFY_TOKEN:
        logger.info("WhatsApp webhook verified")
        return Response(content=challenge, media_type="text/plain")
    return Response(status_code=403)


# ---------------------------------------------------------------------------
# Incoming message handler (POST)
# ---------------------------------------------------------------------------

@router.post("/webhook/cloud")
async def receive_webhook(request: Request):
    """Receive WhatsApp messages from Meta Cloud API.

    Stores the message in the messenger DB and generates a bot reply
    that is sent both to WhatsApp and stored in the DB.
    """
    body = await request.json()
    parsed = parse_cloud_webhook(body)

    if not parsed:
        return {"status": "ok"}

    message_id = parsed["message_id"]
    sender_phone = parsed["sender"]
    text = parsed["text"]

    # Deduplication — optimistic mark to prevent concurrent duplicates during
    # async processing (OpenAI can take 20-30s, Meta retries within ~20s)
    if message_id in _processed_ids:
        return {"status": "duplicate"}
    _processed_ids[message_id] = None
    while len(_processed_ids) > _MAX_PROCESSED:
        _processed_ids.popitem(last=False)

    if not text:
        return {"status": "ok"}

    logger.info(f"WhatsApp message from {sender_phone}: {text[:100]}")

    # Store in messenger database
    conn = get_db()
    try:
        user_id = _get_or_create_whatsapp_user(conn, sender_phone)
        bot_user_id = _get_bot_user_id(conn)

        # Store incoming message
        conn.execute(
            """INSERT INTO messages (sender_id, recipient_id, content,
               message_type, channel)
               VALUES (?, ?, ?, 'text', 'whatsapp')""",
            (user_id, bot_user_id, text),
        )
        conn.commit()

        # Get user info for bot context
        user_row = conn.execute(
            "SELECT name, grade FROM users WHERE id = ?", (user_id,)
        ).fetchone()
        user_name = user_row["name"] if user_row else ""
        user_grade = user_row["grade"] if user_row else ""

        # Generate bot reply
        bot_reply = await get_bot_response(text, user_name, user_grade)

        # Store bot reply in DB
        conn.execute(
            """INSERT INTO messages (sender_id, recipient_id, content,
               message_type, is_bot, channel)
               VALUES (?, ?, ?, 'text', 1, 'whatsapp')""",
            (bot_user_id, user_id, bot_reply),
        )
        conn.commit()
    except Exception:
        # Roll back dedup mark so Meta can retry on transient failures
        _processed_ids.pop(message_id, None)
        conn.close()
        raise

    conn.close()

    # Send reply back via WhatsApp
    if is_whatsapp_configured():
        await send_whatsapp_message(sender_phone, bot_reply)

    return {"status": "ok"}
