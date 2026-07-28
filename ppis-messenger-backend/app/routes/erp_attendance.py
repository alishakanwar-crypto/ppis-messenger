"""Admin-only ERP attendance and leave management."""

import json
import re
from datetime import date, timedelta
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field

from app.database import _ist_now, get_db
from app.routes.auth import require_admin

router = APIRouter()

ATTENDANCE_STATUSES = {"present", "absent", "late", "half_day", "leave", "holiday"}
LEAVE_TYPES = {"sick", "casual", "other"}
LEAVE_STATUSES = {"pending", "approved", "rejected"}
DATE_PATTERN = re.compile(r"^\d{4}-\d{2}-\d{2}$")


def audit(conn, user_id, action, entity_type, entity_id, details=None):
    conn.execute(
        """INSERT INTO erp_audit_log
           (actor_user_id, action, entity_type, entity_id, details, created_at)
           VALUES (?, ?, ?, ?, ?, ?)""",
        (
            user_id,
            action,
            entity_type,
            entity_id,
            json.dumps(details or {}),
            _ist_now(),
        ),
    )


def _date(value: str, field_name: str = "date") -> str:
    if not DATE_PATTERN.fullmatch(value):
        raise HTTPException(400, f"Invalid {field_name}; expected YYYY-MM-DD")
    try:
        date.fromisoformat(value)
    except ValueError:
        raise HTTPException(400, f"Invalid {field_name}; expected YYYY-MM-DD")
    return value


def _session(conn, session_id: int):
    row = conn.execute(
        "SELECT * FROM erp_academic_sessions WHERE id = ?", (session_id,)
    ).fetchone()
    if not row:
        raise HTTPException(404, "Academic session not found")
    return row


def _student(conn, student_id: int):
    row = conn.execute(
        "SELECT * FROM erp_students WHERE id = ?", (student_id,)
    ).fetchone()
    if not row:
        raise HTTPException(404, "Student not found")
    return row


def _upsert_attendance(
    conn,
    student_id: int,
    session_id: int,
    attendance_date: str,
    status: str,
    remarks: str,
    marked_by: Optional[int],
    now: str,
):
    conn.execute(
        """INSERT INTO erp_attendance
           (student_id, session_id, date, status, remarks, marked_by, created_at, updated_at)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?)
           ON CONFLICT(student_id, date) DO UPDATE SET
             session_id = excluded.session_id,
             status = excluded.status,
             remarks = excluded.remarks,
             marked_by = excluded.marked_by,
             updated_at = excluded.updated_at""",
        (
            student_id,
            session_id,
            attendance_date,
            status,
            remarks,
            marked_by,
            now,
            now,
        ),
    )


class AttendanceEntry(BaseModel):
    student_id: int
    status: str
    remarks: str = ""


class AttendanceMarkIn(BaseModel):
    session_id: int
    date: str
    entries: list[AttendanceEntry] = Field(default_factory=list)


class LeaveCreateIn(BaseModel):
    student_id: int
    session_id: int
    from_date: str
    to_date: str
    leave_type: str
    reason: str = ""


class LeaveDecisionIn(BaseModel):
    decision: str


@router.get("/attendance")
async def attendance_roster(
    grade: str = "",
    date: Optional[str] = None,
    session_id: Optional[int] = None,
    user=Depends(require_admin),
):
    attendance_date = _date(date or _ist_now()[:10])
    conn = get_db()
    try:
        if session_id is not None:
            _session(conn, session_id)
        clauses = ["s.status = 'active'"]
        params = []
        if grade.strip():
            clauses.append("s.grade = ?")
            params.append(grade.strip())
        rows = conn.execute(
            f"""SELECT s.id AS student_id, s.admission_number, s.full_name, s.grade,
                       a.id AS attendance_id, a.status, a.remarks
                FROM erp_students s
                LEFT JOIN erp_attendance a
                  ON a.student_id = s.id AND a.date = ?
                WHERE {' AND '.join(clauses)}
                ORDER BY s.grade, s.full_name""",
            [attendance_date, *params],
        ).fetchall()
        entries = [dict(row) for row in rows]
        counts = {status: 0 for status in ATTENDANCE_STATUSES}
        counts["unmarked"] = 0
        for row in entries:
            if row["status"] in counts:
                counts[row["status"]] += 1
            else:
                counts["unmarked"] += 1
        return {
            "date": attendance_date,
            "grade": grade,
            "students": entries,
            "summary": {"total": len(entries), **counts},
        }
    finally:
        conn.close()


@router.post("/attendance/mark")
async def mark_attendance(body: AttendanceMarkIn, user=Depends(require_admin)):
    attendance_date = _date(body.date)
    conn = get_db()
    try:
        _session(conn, body.session_id)
        for entry in body.entries:
            if entry.status not in ATTENDANCE_STATUSES:
                raise HTTPException(400, f"Invalid attendance status: {entry.status}")
            _student(conn, entry.student_id)
        now = _ist_now()
        for entry in body.entries:
            _upsert_attendance(
                conn,
                entry.student_id,
                body.session_id,
                attendance_date,
                entry.status,
                entry.remarks,
                user["user_id"],
                now,
            )
        counts = {
            status: sum(entry.status == status for entry in body.entries)
            for status in ATTENDANCE_STATUSES
        }
        audit(
            conn,
            user["user_id"],
            "mark",
            "attendance",
            None,
            {"date": attendance_date, "session_id": body.session_id, "counts": counts},
        )
        conn.commit()
        return {"ok": True, "date": attendance_date, "marked": len(body.entries), "counts": counts}
    finally:
        conn.close()


@router.get("/attendance/summary")
async def attendance_summary(
    grade: str = "",
    from_: Optional[str] = Query(default=None, alias="from"),
    to: Optional[str] = None,
    session_id: Optional[int] = None,
    user=Depends(require_admin),
):
    from_date = _date(from_ or _ist_now()[:10], "from")
    to_date = _date(to or from_date, "to")
    if from_date > to_date:
        raise HTTPException(400, "from must be on or before to")
    conn = get_db()
    try:
        if session_id is not None:
            _session(conn, session_id)
        student_clauses = ["s.status = 'active'"]
        student_params = []
        if grade.strip():
            student_clauses.append("s.grade = ?")
            student_params.append(grade.strip())
        attendance_clauses = ["a.date BETWEEN ? AND ?"]
        attendance_params = [from_date, to_date]
        if session_id is not None:
            attendance_clauses.append("a.session_id = ?")
            attendance_params.append(session_id)
        if grade.strip():
            attendance_clauses.append("s.grade = ?")
            attendance_params.append(grade.strip())
        daily_rows = conn.execute(
            f"""SELECT a.date, a.status, COUNT(*) AS count
                FROM erp_attendance a
                JOIN erp_students s ON s.id = a.student_id
                WHERE {' AND '.join(attendance_clauses)}
                GROUP BY a.date, a.status
                ORDER BY a.date""",
            attendance_params,
        ).fetchall()
        by_day = {}
        for row in daily_rows:
            by_day.setdefault(row["date"], {})[row["status"]] = row["count"]
        student_rows = conn.execute(
            f"""SELECT s.id AS student_id, s.full_name, s.grade,
                       COUNT(a.id) AS total,
                       SUM(CASE WHEN a.status = 'present' THEN 1 ELSE 0 END) AS present
                FROM erp_students s
                LEFT JOIN erp_attendance a
                  ON a.student_id = s.id AND a.date BETWEEN ? AND ?
                  {'AND a.session_id = ?' if session_id is not None else ''}
                WHERE {' AND '.join(student_clauses)}
                GROUP BY s.id
                ORDER BY s.grade, s.full_name""",
            [from_date, to_date, *([session_id] if session_id is not None else []), *student_params],
        ).fetchall()
        students_result = []
        for row in student_rows:
            total = row["total"] or 0
            present = row["present"] or 0
            students_result.append(
                {
                    **dict(row),
                    "present": present,
                    "total": total,
                    "percentage": round((present / total) * 100, 2) if total else 0,
                }
            )
        return {
            "from": from_date,
            "to": to_date,
            "days": [{"date": key, "counts": value} for key, value in by_day.items()],
            "students": students_result,
        }
    finally:
        conn.close()


@router.get("/attendance/student/{student_id}")
async def student_attendance(
    student_id: int,
    from_: Optional[str] = Query(default=None, alias="from"),
    to: Optional[str] = None,
    user=Depends(require_admin),
):
    from_date = _date(from_ or _ist_now()[:10], "from")
    to_date = _date(to or from_date, "to")
    if from_date > to_date:
        raise HTTPException(400, "from must be on or before to")
    conn = get_db()
    try:
        student = _student(conn, student_id)
        rows = conn.execute(
            """SELECT id, session_id, date, status, remarks, marked_by, created_at, updated_at
               FROM erp_attendance
               WHERE student_id = ? AND date BETWEEN ? AND ?
               ORDER BY date""",
            (student_id, from_date, to_date),
        ).fetchall()
        total = len(rows)
        present = sum(row["status"] == "present" for row in rows)
        return {
            "student": dict(student),
            "from": from_date,
            "to": to_date,
            "records": [dict(row) for row in rows],
            "present": present,
            "total": total,
            "percentage": round((present / total) * 100, 2) if total else 0,
        }
    finally:
        conn.close()


@router.get("/leave")
async def leave_requests(
    status: str = "",
    user=Depends(require_admin),
):
    if status and status not in LEAVE_STATUSES:
        raise HTTPException(400, "Invalid leave status")
    conn = get_db()
    try:
        clauses = []
        params = []
        if status:
            clauses.append("l.status = ?")
            params.append(status)
        rows = conn.execute(
            f"""SELECT l.*, s.full_name, s.grade
                FROM erp_leave_requests l
                JOIN erp_students s ON s.id = l.student_id
                {('WHERE ' + ' AND '.join(clauses)) if clauses else ''}
                ORDER BY l.created_at DESC, l.id DESC""",
            params,
        ).fetchall()
        return {"leave_requests": [dict(row) for row in rows]}
    finally:
        conn.close()


@router.post("/leave", status_code=201)
async def create_leave(body: LeaveCreateIn, user=Depends(require_admin)):
    from_date = _date(body.from_date, "from_date")
    to_date = _date(body.to_date, "to_date")
    if from_date > to_date:
        raise HTTPException(400, "from_date must be on or before to_date")
    if body.leave_type not in LEAVE_TYPES:
        raise HTTPException(400, f"Invalid leave type: {body.leave_type}")
    conn = get_db()
    try:
        _student(conn, body.student_id)
        _session(conn, body.session_id)
        now = _ist_now()
        cur = conn.execute(
            """INSERT INTO erp_leave_requests
               (student_id, session_id, from_date, to_date, leave_type, reason, created_at, updated_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                body.student_id,
                body.session_id,
                from_date,
                to_date,
                body.leave_type,
                body.reason,
                now,
                now,
            ),
        )
        audit(conn, user["user_id"], "create", "leave", cur.lastrowid, body.model_dump())
        conn.commit()
        return dict(
            conn.execute(
                "SELECT * FROM erp_leave_requests WHERE id = ?", (cur.lastrowid,)
            ).fetchone()
        )
    finally:
        conn.close()


@router.post("/leave/{leave_id}/decision")
async def decide_leave(
    leave_id: int,
    body: LeaveDecisionIn,
    user=Depends(require_admin),
):
    if body.decision not in {"approved", "rejected"}:
        raise HTTPException(400, "Decision must be approved or rejected")
    conn = get_db()
    try:
        leave = conn.execute(
            "SELECT * FROM erp_leave_requests WHERE id = ?", (leave_id,)
        ).fetchone()
        if not leave:
            raise HTTPException(404, "Leave request not found")
        now = _ist_now()
        conn.execute(
            """UPDATE erp_leave_requests
               SET status = ?, decided_by = ?, decided_at = ?, updated_at = ?
               WHERE id = ?""",
            (body.decision, user["user_id"], now, now, leave_id),
        )
        if body.decision == "approved":
            current = date.fromisoformat(leave["from_date"])
            end = date.fromisoformat(leave["to_date"])
            while current <= end:
                _upsert_attendance(
                    conn,
                    leave["student_id"],
                    leave["session_id"],
                    current.isoformat(),
                    "leave",
                    leave["reason"],
                    user["user_id"],
                    now,
                )
                current += timedelta(days=1)
        audit(
            conn,
            user["user_id"],
            "decision",
            "leave",
            leave_id,
            {"decision": body.decision},
        )
        conn.commit()
        return dict(
            conn.execute(
                "SELECT * FROM erp_leave_requests WHERE id = ?", (leave_id,)
            ).fetchone()
        )
    finally:
        conn.close()
