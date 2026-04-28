"""Admin routes — view all conversations, broadcast, manage users."""

import base64
import json
import logging
import os

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form
from fastapi.responses import Response
from pydantic import BaseModel

from app.database import get_db
from app.routes.auth import get_current_user, require_admin

logger = logging.getLogger(__name__)
router = APIRouter()


class BroadcastRequest(BaseModel):
    title: str
    content: str
    target_grades: list[str] = []


@router.get("/stats")
async def get_stats(user: dict = Depends(require_admin)):
    """Get dashboard stats."""
    conn = get_db()
    total_users = conn.execute("SELECT COUNT(*) as c FROM users").fetchone()["c"]
    total_messages = conn.execute("SELECT COUNT(*) as c FROM messages").fetchone()["c"]
    messages_today = conn.execute(
        "SELECT COUNT(*) as c FROM messages WHERE date(created_at) = date('now')"
    ).fetchone()["c"]
    total_groups = conn.execute("SELECT COUNT(*) as c FROM groups_").fetchone()["c"]
    total_broadcasts = conn.execute("SELECT COUNT(*) as c FROM broadcasts").fetchone()["c"]

    # Users by role
    role_rows = conn.execute(
        "SELECT role, COUNT(*) as c FROM users GROUP BY role"
    ).fetchall()
    users_by_role = {r["role"]: r["c"] for r in role_rows}

    # Channel breakdown (app vs whatsapp)
    try:
        channel_rows = conn.execute(
            "SELECT COALESCE(channel, 'app') as ch, COUNT(*) as c FROM messages GROUP BY ch"
        ).fetchall()
        messages_by_channel = {r["ch"]: r["c"] for r in channel_rows}
    except Exception:
        messages_by_channel = {"app": total_messages}

    # Users by channel
    try:
        user_channel_rows = conn.execute(
            "SELECT COALESCE(channel, 'app') as ch, COUNT(*) as c FROM users WHERE role = 'parent' GROUP BY ch"
        ).fetchall()
        users_by_channel = {r["ch"]: r["c"] for r in user_channel_rows}
    except Exception:
        users_by_channel = {}

    conn.close()

    return {
        "total_users": total_users,
        "total_messages": total_messages,
        "total_groups": total_groups,
        "total_broadcasts": total_broadcasts,
        "users_by_role": users_by_role,
        "messages_today": messages_today,
        "messages_by_channel": messages_by_channel,
        "users_by_channel": users_by_channel,
    }


@router.get("/all-conversations")
async def get_all_conversations(
    page: int = 1,
    limit: int = 50,
    search: str = "",
    user: dict = Depends(require_admin),
):
    """Get all conversations across all users (admin only)."""
    conn = get_db()
    offset = (page - 1) * limit

    if search:
        query = """
            SELECT m.*, u.name as sender_name, u.role as sender_role, u.phone as sender_phone
            FROM messages m
            JOIN users u ON m.sender_id = u.id
            WHERE m.content LIKE ? OR u.name LIKE ? OR u.phone LIKE ?
            ORDER BY m.id DESC LIMIT ? OFFSET ?
        """
        search_term = f"%{search}%"
        rows = conn.execute(query, (search_term, search_term, search_term, limit, offset)).fetchall()
    else:
        rows = conn.execute(
            """SELECT m.*, u.name as sender_name, u.role as sender_role, u.phone as sender_phone
               FROM messages m
               JOIN users u ON m.sender_id = u.id
               ORDER BY m.id DESC LIMIT ? OFFSET ?""",
            (limit, offset),
        ).fetchall()

    total = conn.execute("SELECT COUNT(*) as c FROM messages").fetchone()["c"]

    messages = []
    for row in rows:
        group_name = ""
        if row["group_id"]:
            grp = conn.execute("SELECT name FROM groups_ WHERE id = ?", (row["group_id"],)).fetchone()
            group_name = grp["name"] if grp else ""

        recipient_name = ""
        if row["recipient_id"]:
            recip = conn.execute("SELECT name, phone FROM users WHERE id = ?", (row["recipient_id"],)).fetchone()
            recipient_name = recip["name"] or recip["phone"] if recip else ""

        # Safely read channel column (may not exist on older DBs)
        try:
            channel = row["channel"] or "app"
        except (IndexError, KeyError):
            channel = "app"

        messages.append({
            "id": row["id"],
            "sender_id": row["sender_id"],
            "sender_name": row["sender_name"] or row["sender_phone"],
            "sender_role": row["sender_role"],
            "sender_phone": row["sender_phone"],
            "group_id": row["group_id"],
            "group_name": group_name,
            "recipient_id": row["recipient_id"],
            "recipient_name": recipient_name,
            "content": row["content"],
            "message_type": row["message_type"],
            "media_url": row["media_url"],
            "created_at": row["created_at"],
            "is_bot": row["is_bot"],
            "channel": channel,
        })

    conn.close()
    # Frontend expects 'conversations' key
    conversations = []
    for m in messages:
        conversations.append({
            "type": "group" if m["group_id"] else "dm",
            "id": m["group_id"] if m["group_id"] else m["recipient_id"] or m["sender_id"],
            "name": m["group_name"] if m["group_id"] else m["sender_name"],
            "last_message": m["content"],
            "last_message_time": m["created_at"],
            "unread_count": 0,
            "grade": "",
            "channel": m.get("channel", "app"),
        })
    # Deduplicate by type+id
    seen = set()
    unique_convs = []
    for c in conversations:
        key = f"{c['type']}-{c['id']}"
        if key not in seen:
            seen.add(key)
            unique_convs.append(c)
    return {"conversations": unique_convs, "total": total, "page": page, "limit": limit}


@router.get("/users")
async def list_users(
    role: str = "",
    search: str = "",
    page: int = 1,
    limit: int = 50,
    user: dict = Depends(require_admin),
):
    """List all users."""
    conn = get_db()
    offset = (page - 1) * limit
    conditions = []
    params: list = []

    if role:
        conditions.append("role = ?")
        params.append(role)
    if search:
        conditions.append("(name LIKE ? OR phone LIKE ?)")
        params.extend([f"%{search}%", f"%{search}%"])

    where = " AND ".join(conditions) if conditions else "1=1"
    rows = conn.execute(
        f"""SELECT id, phone, name, role, grade, children, created_at, last_seen
            FROM users WHERE {where}
            ORDER BY last_seen DESC LIMIT ? OFFSET ?""",
        params + [limit, offset],
    ).fetchall()

    total = conn.execute(f"SELECT COUNT(*) as c FROM users WHERE {where}", params).fetchone()["c"]
    conn.close()

    return {
        "users": [
            {
                "id": r["id"],
                "phone": r["phone"],
                "name": r["name"],
                "role": r["role"],
                "grade": r["grade"],
                "children": json.loads(r["children"] or "[]"),
                "created_at": r["created_at"],
                "last_seen": r["last_seen"],
            }
            for r in rows
        ],
        "total": total,
        "page": page,
    }


@router.post("/broadcast")
async def send_broadcast(body: BroadcastRequest, user: dict = Depends(require_admin)):
    """Send broadcast message to all parents (or specific grades)."""
    conn = get_db()

    # Save broadcast
    cursor = conn.execute(
        "INSERT INTO broadcasts (sender_id, title, content, target_grades) VALUES (?, ?, ?, ?)",
        (user["user_id"], body.title, body.content, json.dumps(body.target_grades)),
    )
    broadcast_id = cursor.lastrowid

    # Find target parents
    if body.target_grades:
        parents = []
        for grade in body.target_grades:
            grade_parents = conn.execute(
                """SELECT DISTINCT u.id FROM users u
                   JOIN group_members gm ON u.id = gm.user_id
                   JOIN groups_ g ON gm.group_id = g.id
                   WHERE g.grade = ? AND u.role = 'parent'""",
                (grade,),
            ).fetchall()
            parents.extend(grade_parents)
        parent_ids = list(set(p["id"] for p in parents))
    else:
        parent_ids = [
            r["id"] for r in conn.execute(
                "SELECT id FROM users WHERE role = 'parent'"
            ).fetchall()
        ]

    # Send message to each parent as a DM from the bot
    bot_user = conn.execute("SELECT id FROM users WHERE phone = 'bot'").fetchone()
    sender_id = bot_user["id"] if bot_user else user["user_id"]

    sent_count = 0
    for pid in parent_ids:
        conn.execute(
            """INSERT INTO messages (sender_id, recipient_id, content, message_type, is_bot)
               VALUES (?, ?, ?, 'text', 1)""",
            (sender_id, pid, f"*{body.title}*\n\n{body.content}"),
        )
        sent_count += 1

    conn.commit()
    conn.close()

    return {
        "success": True,
        "broadcast_id": broadcast_id,
        "sent_count": sent_count,
        "recipients_count": sent_count,
    }


@router.post("/reply")
async def admin_reply(body: dict, user: dict = Depends(require_admin)):
    """Admin sends a reply to a specific user."""
    recipient_id = body.get("recipient_id")
    content = body.get("content", "")
    group_id = body.get("group_id")

    if not content:
        raise HTTPException(status_code=400, detail="content required")
    if not recipient_id and not group_id:
        raise HTTPException(status_code=400, detail="recipient_id or group_id required")

    conn = get_db()
    conn.execute(
        """INSERT INTO messages (sender_id, group_id, recipient_id, content, message_type)
           VALUES (?, ?, ?, ?, 'text')""",
        (user["user_id"], group_id, recipient_id, content),
    )
    conn.commit()
    conn.close()
    return {"success": True}


# ---- Student Photo Management ----

@router.post("/upload-student-photo")
async def upload_student_photo(
    student_name: str = Form(...),
    grade: str = Form(...),
    photo: UploadFile = File(...),
    user: dict = Depends(require_admin),
):
    """Upload a student photo. Admins only."""
    if not photo.content_type or not photo.content_type.startswith("image/"):
        raise HTTPException(status_code=400, detail="Only image files are allowed")

    contents = await photo.read()
    if len(contents) > 5 * 1024 * 1024:  # 5MB limit
        raise HTTPException(status_code=400, detail="Image too large (max 5MB)")

    photo_b64 = base64.b64encode(contents).decode("utf-8")
    content_type = photo.content_type or "image/jpeg"
    photo_data = f"data:{content_type};base64,{photo_b64}"

    conn = get_db()
    conn.execute(
        """INSERT INTO student_photos (student_name, grade, photo_data)
           VALUES (?, ?, ?)
           ON CONFLICT(student_name, grade) DO UPDATE SET photo_data = ?, uploaded_at = CURRENT_TIMESTAMP""",
        (student_name.strip(), grade.strip(), photo_data, photo_data),
    )
    conn.commit()
    conn.close()
    logger.info(f"Photo uploaded for {student_name} ({grade})")
    return {"success": True, "student_name": student_name, "grade": grade}


@router.get("/student-photos")
async def list_student_photos(
    grade: str = "",
    search: str = "",
    user: dict = Depends(require_admin),
):
    """List all student photos (metadata only, no photo data). Admins only."""
    conn = get_db()
    conditions = []
    params: list = []
    if grade:
        conditions.append("grade = ?")
        params.append(grade)
    if search:
        conditions.append("student_name LIKE ?")
        params.append(f"%{search}%")
    where = " AND ".join(conditions) if conditions else "1=1"
    rows = conn.execute(
        f"""SELECT id, student_name, grade, uploaded_at
            FROM student_photos WHERE {where}
            ORDER BY grade, student_name""",
        params,
    ).fetchall()
    conn.close()
    return {
        "photos": [
            {
                "id": r["id"],
                "student_name": r["student_name"],
                "grade": r["grade"],
                "uploaded_at": r["uploaded_at"],
            }
            for r in rows
        ]
    }


@router.delete("/student-photos/{photo_id}")
async def delete_student_photo(photo_id: int, user: dict = Depends(require_admin)):
    """Delete a student photo. Admins only."""
    conn = get_db()
    conn.execute("DELETE FROM student_photos WHERE id = ?", (photo_id,))
    conn.commit()
    conn.close()
    return {"success": True}


@router.get("/student-photo-image/{photo_id}")
async def get_student_photo_image(photo_id: int):
    """Get the actual photo image by ID. Returns image binary."""
    conn = get_db()
    row = conn.execute(
        "SELECT photo_data FROM student_photos WHERE id = ?", (photo_id,)
    ).fetchone()
    conn.close()
    if not row:
        raise HTTPException(status_code=404, detail="Photo not found")
    photo_data = row["photo_data"]
    # Parse data URI: data:image/jpeg;base64,...
    if photo_data.startswith("data:"):
        header, b64data = photo_data.split(",", 1)
        content_type = header.split(":")[1].split(";")[0]
    else:
        b64data = photo_data
        content_type = "image/jpeg"
    image_bytes = base64.b64decode(b64data)
    return Response(content=image_bytes, media_type=content_type)


@router.get("/broadcasts")
async def list_broadcasts(user: dict = Depends(require_admin)):
    """List all broadcasts."""
    conn = get_db()
    rows = conn.execute(
        """SELECT b.*, u.name as sender_name
           FROM broadcasts b JOIN users u ON b.sender_id = u.id
           ORDER BY b.id DESC LIMIT 50"""
    ).fetchall()
    conn.close()

    return {
        "broadcasts": [
            {
                "id": r["id"],
                "sender_name": r["sender_name"],
                "title": r["title"],
                "content": r["content"],
                "target_grades": json.loads(r["target_grades"] or "[]"),
                "created_at": r["created_at"],
            }
            for r in rows
        ]
    }
