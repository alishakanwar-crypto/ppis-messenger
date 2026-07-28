"""Minimal Meta WhatsApp Cloud API integration for login codes."""

import logging
import os

import httpx

logger = logging.getLogger(__name__)


async def send_login_code(phone_10digit: str, code: str) -> bool:
    """Send a login code through the approved WhatsApp template."""
    token = os.environ.get("WHATSAPP_CLOUD_TOKEN", "")
    phone_id = os.environ.get("WHATSAPP_PHONE_ID", "")
    if not token or not phone_id:
        logger.error("WhatsApp Cloud API credentials are not configured")
        return False

    recipient = f"91{phone_10digit}"
    url = f"https://graph.facebook.com/v25.0/{phone_id}/messages"
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
    }
    body = (
        f"Your PPIS Campus Care login code is {code}. "
        "It is valid for 10 minutes. Do not share it with anyone."
    )
    payload = {
        "messaging_product": "whatsapp",
        "to": recipient,
        "type": "template",
        "template": {
            "name": "ppis_emergency_alert",
            "language": {"code": "en"},
            "components": [
                {
                    "type": "body",
                    "parameters": [{"type": "text", "text": body}],
                }
            ],
        },
    }

    try:
        async with httpx.AsyncClient() as client:
            response = await client.post(
                url, headers=headers, json=payload, timeout=30.0
            )
            data = response.json()
            if "messages" in data:
                return True
            logger.error(
                "WhatsApp login-code template failed: HTTP %s, response=%s",
                response.status_code,
                data,
            )
    except Exception:
        logger.exception("WhatsApp login-code template request failed")
    return False
