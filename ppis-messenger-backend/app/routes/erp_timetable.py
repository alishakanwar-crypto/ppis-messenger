"""Admin-only ERP timetable and homework management."""

import json
from datetime import date
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field

from app.database import _ist_now, get_db
from app.routes.auth import require_admin

router = APIRouter()
HOMEWORK_STATUSES = {"open", "closed"}


def audit(conn, user_id, action, entity_type, entity_id, details=None):
    conn.execute(
        """INSERT INTO erp_audit_log
           (actor_user_id, action, entity_type, entity_id, details, created_at)
           VALUES (?, ?, ?, ?, ?, ?)""",
        (user_id, action, entity_type, entity_id, json.dumps(details or {}), _ist_now()),
    )


def _date(value: str) -> str:
    try:
        parsed = date.fromisoformat(value)
    except (TypeError, ValueError) as exc:
        raise HTTPException(400, "Date must be YYYY-MM-DD") from exc
    if parsed.isoformat() != value:
        raise HTTPException(400, "Date must be YYYY-MM-DD")
    return value


def _session(conn, session_id: Optional[int]):
    if session_id is not None and not conn.execute(
        "SELECT id FROM erp_academic_sessions WHERE id = ?", (session_id,)
    ).fetchone():
        raise HTTPException(404, "Academic session not found")


def _homework_status(value: str) -> str:
    normalized = value.strip().lower()
    if normalized not in HOMEWORK_STATUSES:
        raise HTTPException(400, f"Invalid homework status: {value}")
    return normalized


def _validate_slot(slot):
    if slot.day_of_week < 1 or slot.day_of_week > 7:
        raise HTTPException(400, "day_of_week must be between 1 and 7")
    if slot.period < 1:
        raise HTTPException(400, "period must be at least 1")


def _get_homework(conn, homework_id: int):
    row = conn.execute("SELECT * FROM erp_homework WHERE id = ?", (homework_id,)).fetchone()
    if not row:
        raise HTTPException(404, "Homework not found")
    return row


class TimetableSlot(BaseModel):
    day_of_week: int
    period: int = Field(ge=1)
    subject: str = ""
    teacher: str = ""
    start_time: str = ""
    end_time: str = ""
    room: str = ""


class TimetableSlotIn(TimetableSlot):
    session_id: Optional[int] = None
    grade: str = ""


class TimetableBulkIn(BaseModel):
    session_id: Optional[int] = None
    grade: str
    slots: list[TimetableSlot] = Field(default_factory=list)


class HomeworkCreate(BaseModel):
    session_id: Optional[int] = None
    grade: str = Field(min_length=1)
    subject: str = ""
    title: str = Field(min_length=1)
    description: str = ""
    assigned_date: str
    due_date: str = ""


class HomeworkUpdate(BaseModel):
    session_id: Optional[int] = None
    grade: Optional[str] = None
    subject: Optional[str] = None
    title: Optional[str] = Field(default=None, min_length=1)
    description: Optional[str] = None
    assigned_date: Optional[str] = None
    due_date: Optional[str] = None
    status: Optional[str] = None


@router.get("/timetable")
async def get_timetable(
    session_id: Optional[int] = None,
    grade: str = "",
    user=Depends(require_admin),
):
    conn = get_db()
    try:
        _session(conn, session_id)
        clauses, params = [], []
        if session_id is not None:
            clauses.append("session_id = ?")
            params.append(session_id)
        if grade.strip():
            clauses.append("grade = ?")
            params.append(grade.strip())
        where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
        rows = conn.execute(
            f"SELECT * FROM erp_timetable_slots {where} ORDER BY day_of_week, period",
            params,
        ).fetchall()
        return {"slots": [dict(row) for row in rows]}
    finally:
        conn.close()


def _upsert_slot(conn, session_id, grade, slot, now):
    _validate_slot(slot)
    conn.execute(
        """INSERT INTO erp_timetable_slots
           (session_id, grade, day_of_week, period, subject, teacher, start_time,
            end_time, room, created_at, updated_at)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
           ON CONFLICT(session_id, grade, day_of_week, period) DO UPDATE SET
             subject = excluded.subject, teacher = excluded.teacher,
             start_time = excluded.start_time, end_time = excluded.end_time,
             room = excluded.room, updated_at = excluded.updated_at""",
        (
            session_id, grade, slot.day_of_week, slot.period, slot.subject, slot.teacher,
            slot.start_time, slot.end_time, slot.room, now, now,
        ),
    )


@router.post("/timetable/slots")
async def save_timetable_slot(body: TimetableSlotIn, user=Depends(require_admin)):
    conn = get_db()
    try:
        _session(conn, body.session_id)
        if not body.grade.strip():
            raise HTTPException(400, "Grade is required")
        now = _ist_now()
        _upsert_slot(conn, body.session_id, body.grade.strip(), body, now)
        row = conn.execute(
            """SELECT * FROM erp_timetable_slots
               WHERE session_id IS ? AND grade = ? AND day_of_week = ? AND period = ?""",
            (body.session_id, body.grade.strip(), body.day_of_week, body.period),
        ).fetchone()
        audit(conn, user["user_id"], "upsert", "timetable", row["id"], body.model_dump())
        conn.commit()
        return dict(row)
    finally:
        conn.close()


@router.post("/timetable/bulk")
async def save_timetable_bulk(body: TimetableBulkIn, user=Depends(require_admin)):
    conn = get_db()
    try:
        _session(conn, body.session_id)
        if not body.grade.strip():
            raise HTTPException(400, "Grade is required")
        now = _ist_now()
        for slot in body.slots:
            _upsert_slot(conn, body.session_id, body.grade.strip(), slot, now)
        audit(conn, user["user_id"], "bulk_upsert", "timetable", body.session_id or 0, {
            "grade": body.grade, "slots": len(body.slots),
        })
        conn.commit()
        return {"ok": True, "saved": len(body.slots)}
    finally:
        conn.close()


@router.delete("/timetable/slots/{slot_id}")
async def delete_timetable_slot(slot_id: int, user=Depends(require_admin)):
    conn = get_db()
    try:
        row = conn.execute("SELECT id FROM erp_timetable_slots WHERE id = ?", (slot_id,)).fetchone()
        if not row:
            raise HTTPException(404, "Timetable slot not found")
        conn.execute("DELETE FROM erp_timetable_slots WHERE id = ?", (slot_id,))
        audit(conn, user["user_id"], "delete", "timetable", slot_id)
        conn.commit()
        return {"ok": True}
    finally:
        conn.close()


@router.get("/homework")
async def list_homework(
    session_id: Optional[int] = None,
    grade: str = "",
    status: str = "",
    from_date: str = Query(default="", alias="from"),
    to_date: str = Query(default="", alias="to"),
    user=Depends(require_admin),
):
    conn = get_db()
    try:
        _session(conn, session_id)
        clauses, params = [], []
        if session_id is not None:
            clauses.append("h.session_id = ?")
            params.append(session_id)
        if grade.strip():
            clauses.append("h.grade = ?")
            params.append(grade.strip())
        if status.strip():
            clauses.append("h.status = ?")
            params.append(_homework_status(status))
        if from_date:
            _date(from_date)
            clauses.append("h.assigned_date >= ?")
            params.append(from_date)
        if to_date:
            _date(to_date)
            clauses.append("h.assigned_date <= ?")
            params.append(to_date)
        where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
        rows = conn.execute(
            f"""SELECT h.*, u.name AS assigned_by_name FROM erp_homework h
                LEFT JOIN users u ON u.id = h.assigned_by {where}
                ORDER BY h.assigned_date DESC, h.id DESC""",
            params,
        ).fetchall()
        return {"homework": [dict(row) for row in rows]}
    finally:
        conn.close()


def _validate_homework_dates(assigned_date, due_date):
    assigned = _date(assigned_date)
    if due_date:
        due = _date(due_date)
        if assigned > due:
            raise HTTPException(400, "assigned_date must not be after due_date")


@router.post("/homework", status_code=201)
async def create_homework(body: HomeworkCreate, user=Depends(require_admin)):
    _validate_homework_dates(body.assigned_date, body.due_date)
    if not body.grade.strip() or not body.title.strip():
        raise HTTPException(400, "Grade and title are required")
    conn = get_db()
    try:
        _session(conn, body.session_id)
        now = _ist_now()
        cur = conn.execute(
            """INSERT INTO erp_homework
               (session_id, grade, subject, title, description, assigned_date, due_date,
                assigned_by, status, created_at, updated_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'open', ?, ?)""",
            (
                body.session_id, body.grade.strip(), body.subject, body.title.strip(), body.description,
                body.assigned_date, body.due_date, user["user_id"], now, now,
            ),
        )
        audit(conn, user["user_id"], "create", "homework", cur.lastrowid, body.model_dump())
        conn.commit()
        return dict(_get_homework(conn, cur.lastrowid))
    finally:
        conn.close()


@router.put("/homework/{homework_id}")
async def update_homework(homework_id: int, body: HomeworkUpdate, user=Depends(require_admin)):
    conn = get_db()
    try:
        existing = _get_homework(conn, homework_id)
        values = body.model_dump(exclude_unset=True)
        if not values:
            return dict(existing)
        _validate_homework_dates(
            values.get("assigned_date", existing["assigned_date"]),
            values.get("due_date", existing["due_date"]),
        )
        if "session_id" in values:
            _session(conn, values["session_id"])
        if "status" in values:
            values["status"] = _homework_status(values["status"])
        if "title" in values:
            values["title"] = values["title"].strip()
        assignments = ", ".join(f"{key} = ?" for key in values)
        now = _ist_now()
        conn.execute(
            f"UPDATE erp_homework SET {assignments}, updated_at = ? WHERE id = ?",
            [*values.values(), now, homework_id],
        )
        audit(conn, user["user_id"], "update", "homework", homework_id, values)
        conn.commit()
        return dict(_get_homework(conn, homework_id))
    finally:
        conn.close()


@router.delete("/homework/{homework_id}")
async def delete_homework(homework_id: int, user=Depends(require_admin)):
    conn = get_db()
    try:
        _get_homework(conn, homework_id)
        conn.execute("DELETE FROM erp_homework WHERE id = ?", (homework_id,))
        audit(conn, user["user_id"], "delete", "homework", homework_id)
        conn.commit()
        return {"ok": True}
    finally:
        conn.close()
