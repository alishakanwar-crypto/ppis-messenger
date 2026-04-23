"""Group management routes."""

import json
import logging

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from app.database import get_db
from app.routes.auth import get_current_user

logger = logging.getLogger(__name__)
router = APIRouter()


@router.get("/")
async def list_groups(user: dict = Depends(get_current_user)):
    """List groups the user belongs to."""
    conn = get_db()
    rows = conn.execute(
        """SELECT g.id, g.name, g.grade, g.type,
           gm.role as my_role,
           (SELECT COUNT(*) FROM group_members WHERE group_id = g.id) as member_count
           FROM groups_ g
           JOIN group_members gm ON g.id = gm.group_id
           WHERE gm.user_id = ?
           ORDER BY g.name""",
        (user["user_id"],),
    ).fetchall()
    conn.close()

    return {
        "groups": [
            {
                "id": r["id"],
                "name": r["name"],
                "grade": r["grade"],
                "type": r["type"],
                "my_role": r["my_role"],
                "member_count": r["member_count"],
            }
            for r in rows
        ]
    }


@router.get("/{group_id}")
async def get_group(group_id: int, user: dict = Depends(get_current_user)):
    """Get group details with members."""
    conn = get_db()
    group = conn.execute("SELECT * FROM groups_ WHERE id = ?", (group_id,)).fetchone()
    if not group:
        conn.close()
        raise HTTPException(status_code=404, detail="Group not found")

    members = conn.execute(
        """SELECT u.id, u.name, u.phone, u.role, gm.role as group_role
           FROM group_members gm
           JOIN users u ON gm.user_id = u.id
           WHERE gm.group_id = ?
           ORDER BY u.name""",
        (group_id,),
    ).fetchall()
    conn.close()

    return {
        "group": {
            "id": group["id"],
            "name": group["name"],
            "grade": group["grade"],
            "type": group["type"],
        },
        "members": [
            {
                "id": m["id"],
                "name": m["name"] or m["phone"],
                "phone": m["phone"],
                "role": m["role"],
                "group_role": m["group_role"],
            }
            for m in members
        ],
    }


@router.get("/{group_id}/members")
async def get_group_members(group_id: int, user: dict = Depends(get_current_user)):
    """Get group members."""
    conn = get_db()
    members = conn.execute(
        """SELECT u.id, u.name, u.phone, u.role, gm.role as group_role
           FROM group_members gm
           JOIN users u ON gm.user_id = u.id
           WHERE gm.group_id = ?
           ORDER BY u.role, u.name""",
        (group_id,),
    ).fetchall()
    conn.close()
    return {
        "members": [
            {
                "id": m["id"],
                "name": m["name"] or m["phone"],
                "phone": m["phone"],
                "role": m["role"],
                "group_role": m["group_role"],
            }
            for m in members
        ]
    }
