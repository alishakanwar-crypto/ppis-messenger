"""WhatsApp Cloud API integration for PPIS Messenger.

Sends messages and media via Meta Cloud API so the bot can respond
to parents who are still on WhatsApp (not yet on the app).
Also receives webhook events from Meta and stores them in the
messenger database for unified dashboard visibility.
"""

import base64
import logging
import os

import httpx

logger = logging.getLogger(__name__)


def get_cloud_token() -> str:
    return os.environ.get("WHATSAPP_CLOUD_TOKEN", "")


def get_cloud_phone_id() -> str:
    return os.environ.get("WHATSAPP_PHONE_ID", "")


def is_whatsapp_configured() -> bool:
    return bool(get_cloud_token() and get_cloud_phone_id())


async def send_whatsapp_message(to: str, message: str) -> bool:
    """Send a text message via Meta Cloud API."""
    token = get_cloud_token()
    phone_id = get_cloud_phone_id()
    if not token or not phone_id:
        logger.warning("WhatsApp Cloud API not configured, skipping send")
        return False

    recipient = to.split("@")[0] if "@" in to else to
    if len(recipient) == 10:
        recipient = "91" + recipient

    url = f"https://graph.facebook.com/v25.0/{phone_id}/messages"
    headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
    payload = {
        "messaging_product": "whatsapp",
        "to": recipient,
        "type": "text",
        "text": {"body": message},
    }

    try:
        async with httpx.AsyncClient() as client:
            response = await client.post(url, headers=headers, json=payload, timeout=30.0)
            data = response.json()
            if "messages" in data:
                logger.info(f"WhatsApp message sent to {recipient}")
                return True
            logger.error(f"WhatsApp send failed: {data}")
            return False
    except Exception as e:
        logger.error(f"WhatsApp send error: {e}")
        return False


async def send_whatsapp_image(to: str, image_base64: str, caption: str = "") -> bool:
    """Upload a base64 image to Meta and send it via WhatsApp."""
    token = get_cloud_token()
    phone_id = get_cloud_phone_id()
    if not token or not phone_id:
        return False

    # Upload the image first
    image_bytes = base64.b64decode(image_base64)
    upload_url = f"https://graph.facebook.com/v25.0/{phone_id}/media"
    headers = {"Authorization": f"Bearer {token}"}
    files = {
        "file": ("snapshot.jpg", image_bytes, "image/jpeg"),
        "type": (None, "image/jpeg"),
        "messaging_product": (None, "whatsapp"),
    }

    try:
        async with httpx.AsyncClient() as client:
            resp = await client.post(upload_url, headers=headers, files=files, timeout=60.0)
            data = resp.json()
            media_id = data.get("id")
            if not media_id:
                logger.error(f"WhatsApp media upload failed: {data}")
                return False

        # Send the image
        recipient = to.split("@")[0] if "@" in to else to
        if len(recipient) == 10:
            recipient = "91" + recipient

        send_url = f"https://graph.facebook.com/v25.0/{phone_id}/messages"
        send_headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
        payload = {
            "messaging_product": "whatsapp",
            "to": recipient,
            "type": "image",
            "image": {"id": media_id, "caption": caption} if caption else {"id": media_id},
        }
        async with httpx.AsyncClient() as client:
            resp = await client.post(send_url, headers=send_headers, json=payload, timeout=30.0)
            data = resp.json()
            if "messages" in data:
                logger.info(f"WhatsApp image sent to {recipient}")
                return True
            logger.error(f"WhatsApp image send failed: {data}")
            return False
    except Exception as e:
        logger.error(f"WhatsApp image send error: {e}")
        return False


def parse_cloud_webhook(body: dict) -> dict | None:
    """Parse an incoming Meta Cloud API webhook payload.

    Returns a dict with keys: sender, message_id, text, media_type, media_id
    or None if not a message event.
    """
    try:
        entry = body.get("entry", [{}])[0]
        changes = entry.get("changes", [{}])[0]
        value = changes.get("value", {})
        messages = value.get("messages", [])
        if not messages:
            return None

        msg = messages[0]
        sender = msg.get("from", "")
        message_id = msg.get("id", "")
        msg_type = msg.get("type", "")

        text = ""
        media_id = ""
        media_type = ""

        if msg_type == "text":
            text = msg.get("text", {}).get("body", "")
        elif msg_type in ("image", "video", "audio", "document"):
            media_obj = msg.get(msg_type, {})
            media_id = media_obj.get("id", "")
            media_type = msg_type
            text = media_obj.get("caption", "")
        elif msg_type == "interactive":
            interactive = msg.get("interactive", {})
            itype = interactive.get("type", "")
            if itype == "button_reply":
                text = interactive.get("button_reply", {}).get("title", "")
            elif itype == "list_reply":
                text = interactive.get("list_reply", {}).get("title", "")

        return {
            "sender": sender,
            "message_id": message_id,
            "text": text,
            "media_type": media_type,
            "media_id": media_id,
        }
    except (IndexError, KeyError, TypeError):
        return None
