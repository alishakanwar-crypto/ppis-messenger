"""Chat routes — send/receive messages, direct and group."""

import json
import logging
import os
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form
from pydantic import BaseModel

from app.database import get_db
from app.routes.auth import get_current_user

logger = logging.getLogger(__name__)
router = APIRouter()

OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY", "")


class SendMessageRequest(BaseModel):
    content: str = ""
    group_id: int | None = None
    recipient_id: int | None = None
    message_type: str = "text"
    media_url: str = ""
    reply_to_id: int | None = None


class MarkReadRequest(BaseModel):
    message_ids: list[int]


# ---- Bot AI response ----

async def get_bot_response(message: str, user_name: str, grade: str) -> str:
    """Get AI response from OpenAI for the school bot."""
    if not OPENAI_API_KEY:
        return (
            "Thank you for your message. For any queries, please contact:\n"
            "School Helpline: 8800935552\n"
            "Ms. Harpreet Kaur (Administration Incharge): 9599488106\n\n"
            "Thank you for your cooperation.\n"
            "Warm regards,\nPP International School"
        )
    try:
        import httpx
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.post(
                "https://api.openai.com/v1/chat/completions",
                headers={"Authorization": f"Bearer {OPENAI_API_KEY}"},
                json={
                    "model": "gpt-4o-mini",
                    "messages": [
                        {
                            "role": "system",
                            "content": (
                                "You are the PP International School assistant. "
                                "You help parents with school-related queries. "
                                "Be polite, professional, and concise. "
                                "Use formal language. No emojis. "
                                "End with: Thank you for your cooperation. "
                                "Warm regards, PP International School. "
                                f"The parent's name is {user_name}, grade: {grade}."
                            ),
                        },
                        {"role": "user", "content": message},
                    ],
                    "max_tokens": 500,
                },
            )
            data = resp.json()
            return data["choices"][0]["message"]["content"]
    except Exception as e:
        logger.error(f"OpenAI error: {e}")
        return (
            "Thank you for your message. For any queries, please contact:\n"
            "School Helpline: 8800935552\n"
            "Ms. Harpreet Kaur: 9599488106\n\n"
            "Warm regards,\nPP International School"
        )


# ---- Endpoints ----

@router.post("/send")
async def send_message(body: SendMessageRequest, user: dict = Depends(get_current_user)):
    """Send a message to a group or direct to a user."""
    conn = get_db()

    if not body.group_id and not body.recipient_id:
        conn.close()
        raise HTTPException(status_code=400, detail="group_id or recipient_id required")

    if not body.content and not body.media_url:
        conn.close()
        raise HTTPException(status_code=400, detail="content or media_url required")

    # Insert message
    cursor = conn.execute(
        """INSERT INTO messages (sender_id, group_id, recipient_id, content,
           message_type, media_url, reply_to_id)
           VALUES (?, ?, ?, ?, ?, ?, ?)""",
        (
            user["user_id"],
            body.group_id,
            body.recipient_id,
            body.content,
            body.message_type,
            body.media_url or "",
            body.reply_to_id,
        ),
    )
    message_id = cursor.lastrowid

    # Auto-read own message
    conn.execute(
        "INSERT OR IGNORE INTO read_receipts (message_id, user_id) VALUES (?, ?)",
        (message_id, user["user_id"]),
    )

    conn.commit()

    # Get the inserted message
    msg = conn.execute("SELECT * FROM messages WHERE id = ?", (message_id,)).fetchone()
    sender = conn.execute(
        "SELECT name, role, phone FROM users WHERE id = ?", (user["user_id"],)
    ).fetchone()

    # If it's a direct message to the bot, generate auto-reply
    if body.recipient_id:
        bot_user = conn.execute("SELECT id FROM users WHERE phone = 'bot'").fetchone()
        if bot_user and body.recipient_id == bot_user["id"]:
            user_row = conn.execute(
                "SELECT name, grade, children FROM users WHERE id = ?",
                (user["user_id"],),
            ).fetchone()
            grade = user_row["grade"] if user_row else ""
            name = user_row["name"] if user_row else ""
            bot_reply = await get_bot_response(body.content, name, grade)
            conn.execute(
                """INSERT INTO messages (sender_id, group_id, recipient_id, content,
                   message_type, is_bot)
                   VALUES (?, NULL, ?, ?, 'text', 1)""",
                (bot_user["id"], user["user_id"], bot_reply),
            )
            conn.commit()

    conn.close()

    return {
        "success": True,
        "message": {
            "id": msg["id"],
            "sender_id": msg["sender_id"],
            "sender_name": sender["name"] if sender else "",
            "sender_role": sender["role"] if sender else "",
            "group_id": msg["group_id"],
            "recipient_id": msg["recipient_id"],
            "content": msg["content"],
            "message_type": msg["message_type"],
            "media_url": msg["media_url"],
            "reply_to_id": msg["reply_to_id"],
            "created_at": msg["created_at"],
            "is_bot": msg["is_bot"],
        },
    }


@router.get("/messages")
async def get_messages(
    group_id: int | None = None,
    recipient_id: int | None = None,
    before_id: int | None = None,
    limit: int = 50,
    user: dict = Depends(get_current_user),
):
    """Get messages for a group or DM conversation."""
    conn = get_db()

    if group_id:
        # Verify membership
        member = conn.execute(
            "SELECT id FROM group_members WHERE group_id = ? AND user_id = ?",
            (group_id, user["user_id"]),
        ).fetchone()
        if not member and user["role"] != "admin":
            conn.close()
            raise HTTPException(status_code=403, detail="Not a member of this group")

        query = """
            SELECT m.*, u.name as sender_name, u.role as sender_role
            FROM messages m
            JOIN users u ON m.sender_id = u.id
            WHERE m.group_id = ?
        """
        params: list = [group_id]

    elif recipient_id:
        # DM: get messages between user and recipient (both directions)
        query = """
            SELECT m.*, u.name as sender_name, u.role as sender_role
            FROM messages m
            JOIN users u ON m.sender_id = u.id
            WHERE (
                (m.sender_id = ? AND m.recipient_id = ?)
                OR (m.sender_id = ? AND m.recipient_id = ?)
            ) AND m.group_id IS NULL
        """
        params = [user["user_id"], recipient_id, recipient_id, user["user_id"]]
    else:
        conn.close()
        raise HTTPException(status_code=400, detail="group_id or recipient_id required")

    if before_id:
        query += " AND m.id < ?"
        params.append(before_id)

    query += " ORDER BY m.id DESC LIMIT ?"
    params.append(limit)

    rows = conn.execute(query, params).fetchall()

    messages = []
    for row in reversed(rows):
        messages.append({
            "id": row["id"],
            "sender_id": row["sender_id"],
            "sender_name": row["sender_name"],
            "sender_role": row["sender_role"],
            "group_id": row["group_id"],
            "recipient_id": row["recipient_id"],
            "content": row["content"],
            "message_type": row["message_type"],
            "media_url": row["media_url"],
            "reply_to_id": row["reply_to_id"],
            "created_at": row["created_at"],
            "is_bot": row["is_bot"],
        })

    conn.close()
    return {"messages": messages}


@router.post("/mark-read")
async def mark_read(body: MarkReadRequest, user: dict = Depends(get_current_user)):
    """Mark messages as read."""
    conn = get_db()
    for msg_id in body.message_ids:
        conn.execute(
            "INSERT OR IGNORE INTO read_receipts (message_id, user_id) VALUES (?, ?)",
            (msg_id, user["user_id"]),
        )
    conn.commit()
    conn.close()
    return {"success": True}


@router.get("/conversations")
async def get_conversations(user: dict = Depends(get_current_user)):
    """Get list of conversations (groups + DMs) with last message."""
    conn = get_db()
    conversations = []

    # Group conversations
    groups = conn.execute(
        """SELECT g.id, g.name, g.grade, g.type,
           (SELECT COUNT(*) FROM group_members WHERE group_id = g.id) as member_count
           FROM groups_ g
           JOIN group_members gm ON g.id = gm.group_id
           WHERE gm.user_id = ?
           ORDER BY g.name""",
        (user["user_id"],),
    ).fetchall()

    for g in groups:
        last_msg = conn.execute(
            """SELECT m.content, m.created_at, u.name as sender_name
               FROM messages m JOIN users u ON m.sender_id = u.id
               WHERE m.group_id = ?
               ORDER BY m.id DESC LIMIT 1""",
            (g["id"],),
        ).fetchone()

        unread = conn.execute(
            """SELECT COUNT(*) as cnt FROM messages m
               WHERE m.group_id = ? AND m.sender_id != ?
               AND m.id NOT IN (
                   SELECT message_id FROM read_receipts WHERE user_id = ?
               )""",
            (g["id"], user["user_id"], user["user_id"]),
        ).fetchone()

        conversations.append({
            "type": "group",
            "id": g["id"],
            "name": g["name"],
            "grade": g["grade"],
            "group_type": g["type"],
            "member_count": g["member_count"],
            "last_message": last_msg["content"][:100] if last_msg else None,
            "last_message_at": last_msg["created_at"] if last_msg else None,
            "last_sender": last_msg["sender_name"] if last_msg else None,
            "unread_count": unread["cnt"] if unread else 0,
        })

    # DM conversations
    dms = conn.execute(
        """SELECT DISTINCT
           CASE WHEN m.sender_id = ? THEN m.recipient_id ELSE m.sender_id END as other_id
           FROM messages m
           WHERE m.group_id IS NULL
           AND (m.sender_id = ? OR m.recipient_id = ?)""",
        (user["user_id"], user["user_id"], user["user_id"]),
    ).fetchall()

    for dm in dms:
        other_user = conn.execute(
            "SELECT id, name, role, phone FROM users WHERE id = ?", (dm["other_id"],)
        ).fetchone()
        if not other_user:
            continue

        last_msg = conn.execute(
            """SELECT m.content, m.created_at, u.name as sender_name
               FROM messages m JOIN users u ON m.sender_id = u.id
               WHERE m.group_id IS NULL
               AND ((m.sender_id = ? AND m.recipient_id = ?)
                    OR (m.sender_id = ? AND m.recipient_id = ?))
               ORDER BY m.id DESC LIMIT 1""",
            (user["user_id"], dm["other_id"], dm["other_id"], user["user_id"]),
        ).fetchone()

        unread = conn.execute(
            """SELECT COUNT(*) as cnt FROM messages m
               WHERE m.group_id IS NULL AND m.sender_id = ? AND m.recipient_id = ?
               AND m.id NOT IN (
                   SELECT message_id FROM read_receipts WHERE user_id = ?
               )""",
            (dm["other_id"], user["user_id"], user["user_id"]),
        ).fetchone()

        conversations.append({
            "type": "dm",
            "id": other_user["id"],
            "name": other_user["name"] or other_user["phone"],
            "role": other_user["role"],
            "last_message": last_msg["content"][:100] if last_msg else None,
            "last_message_at": last_msg["created_at"] if last_msg else None,
            "last_sender": last_msg["sender_name"] if last_msg else None,
            "unread_count": unread["cnt"] if unread else 0,
        })

    # Sort by last message time
    conversations.sort(
        key=lambda c: c["last_message_at"] or "0000", reverse=True
    )

    conn.close()
    return {"conversations": conversations}


@router.get("/new-messages")
async def poll_new_messages(
    after_id: int = 0,
    user: dict = Depends(get_current_user),
):
    """Long-poll for new messages across all conversations."""
    conn = get_db()

    # Get user's group IDs
    group_ids = [
        row["group_id"]
        for row in conn.execute(
            "SELECT group_id FROM group_members WHERE user_id = ?",
            (user["user_id"],),
        ).fetchall()
    ]

    messages = []

    if group_ids:
        placeholders = ",".join("?" for _ in group_ids)
        group_msgs = conn.execute(
            f"""SELECT m.*, u.name as sender_name, u.role as sender_role
                FROM messages m JOIN users u ON m.sender_id = u.id
                WHERE m.id > ? AND m.group_id IN ({placeholders})
                ORDER BY m.id LIMIT 100""",
            [after_id] + group_ids,
        ).fetchall()
        for row in group_msgs:
            messages.append({
                "id": row["id"],
                "sender_id": row["sender_id"],
                "sender_name": row["sender_name"],
                "sender_role": row["sender_role"],
                "group_id": row["group_id"],
                "recipient_id": row["recipient_id"],
                "content": row["content"],
                "message_type": row["message_type"],
                "media_url": row["media_url"],
                "created_at": row["created_at"],
                "is_bot": row["is_bot"],
            })

    # DMs
    dm_msgs = conn.execute(
        """SELECT m.*, u.name as sender_name, u.role as sender_role
           FROM messages m JOIN users u ON m.sender_id = u.id
           WHERE m.id > ? AND m.group_id IS NULL
           AND (m.sender_id = ? OR m.recipient_id = ?)
           ORDER BY m.id LIMIT 100""",
        (after_id, user["user_id"], user["user_id"]),
    ).fetchall()
    for row in dm_msgs:
        messages.append({
            "id": row["id"],
            "sender_id": row["sender_id"],
            "sender_name": row["sender_name"],
            "sender_role": row["sender_role"],
            "group_id": row["group_id"],
            "recipient_id": row["recipient_id"],
            "content": row["content"],
            "message_type": row["message_type"],
            "media_url": row["media_url"],
            "created_at": row["created_at"],
            "is_bot": row["is_bot"],
        })

    messages.sort(key=lambda m: m["id"])
    conn.close()
    return {"messages": messages}
