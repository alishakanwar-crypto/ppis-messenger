"""School ERP routes for the student-information foundation."""

import json
import sqlite3

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field

from app.database import _ist_now, _upsert_erp_guardian, get_db
from app.routes.auth import require_admin

router = APIRouter()
STUDENT_STATUSES = {"active", "inactive", "alumni", "withdrawn"}


class GuardianInput(BaseModel):
    full_name: str = ""
    phone: str = ""
    email: str = ""
    relationship: str = "guardian"
    is_primary: bool = False


class StudentCreate(BaseModel):
    admission_number: str = ""
    full_name: str = Field(min_length=2)
    grade: str = Field(min_length=1)
    date_of_birth: str = ""
    gender: str = ""
    address: str = ""
    transport: str = ""
    status: str = "active"
    guardians: list[GuardianInput] = Field(default_factory=list)


class StudentUpdate(BaseModel):
    admission_number: str | None = None
    full_name: str | None = Field(default=None, min_length=2)
    grade: str | None = Field(default=None, min_length=1)
    date_of_birth: str | None = None
    gender: str | None = None
    address: str | None = None
    transport: str | None = None
    status: str | None = None


def _validate_status(status: str) -> str:
    normalized = status.strip().lower()
    if normalized not in STUDENT_STATUSES:
        raise HTTPException(status_code=400, detail="Invalid student status")
    return normalized


def _record_audit(
    conn: sqlite3.Connection,
    actor_user_id: int,
    action: str,
    entity_id: int,
    details: dict,
) -> None:
    conn.execute(
        """INSERT INTO erp_audit_log
           (actor_user_id, action, entity_type, entity_id, details, created_at)
           VALUES (?, ?, 'student', ?, ?, ?)""",
        (actor_user_id, action, entity_id, json.dumps(details), _ist_now()),
    )


def _get_student_detail(conn: sqlite3.Connection, student_id: int) -> dict:
    student = conn.execute(
        "SELECT * FROM erp_students WHERE id = ?",
        (student_id,),
    ).fetchone()
    if not student:
        raise HTTPException(status_code=404, detail="Student not found")

    guardians = conn.execute(
        """SELECT g.id, g.full_name, g.phone, g.email,
                  sg.relationship, sg.is_primary
           FROM erp_guardians g
           JOIN erp_student_guardians sg ON sg.guardian_id = g.id
           WHERE sg.student_id = ?
           ORDER BY sg.is_primary DESC, sg.relationship, g.full_name""",
        (student_id,),
    ).fetchall()
    return {
        **dict(student),
        "guardians": [
            {
                **dict(guardian),
                "is_primary": bool(guardian["is_primary"]),
            }
            for guardian in guardians
        ],
    }


@router.get("/overview")
async def get_erp_overview(user: dict = Depends(require_admin)):
    conn = get_db()
    try:
        active_students = conn.execute(
            "SELECT COUNT(*) AS count FROM erp_students WHERE status = 'active'"
        ).fetchone()["count"]
        total_guardians = conn.execute(
            "SELECT COUNT(*) AS count FROM erp_guardians"
        ).fetchone()["count"]
        transport_students = conn.execute(
            """SELECT COUNT(*) AS count FROM erp_students
               WHERE status = 'active' AND trim(transport) != ''
                 AND upper(trim(transport)) NOT IN ('NO', 'NA', 'N/A')"""
        ).fetchone()["count"]
        grade_rows = conn.execute(
            """SELECT grade, COUNT(*) AS count FROM erp_students
               WHERE status = 'active'
               GROUP BY grade ORDER BY grade"""
        ).fetchall()
        recent_updates = conn.execute(
            """SELECT id, action, entity_id, details, created_at
               FROM erp_audit_log ORDER BY id DESC LIMIT 8"""
        ).fetchall()
        fees_outstanding = conn.execute(
            "SELECT COALESCE(SUM(net_paise-paid_paise),0) AS n FROM erp_invoices WHERE status != 'cancelled'"
        ).fetchone()["n"]
        fees_collected_month = conn.execute(
            "SELECT COALESCE(SUM(amount_paise),0) AS n FROM erp_payments WHERE status='confirmed' AND substr(paid_at,1,7)=substr(?,1,7)",
            (_ist_now(),),
        ).fetchone()["n"]
    finally:
        conn.close()

    return {
        "active_students": active_students,
        "total_guardians": total_guardians,
        "transport_students": transport_students,
        "grade_count": len(grade_rows),
        "students_by_grade": [dict(row) for row in grade_rows],
        "recent_updates": [
            {
                **dict(row),
                "details": json.loads(row["details"] or "{}"),
            }
            for row in recent_updates
        ],
        "fees_outstanding_paise": fees_outstanding,
        "fees_collected_this_month_paise": fees_collected_month,
    }


@router.get("/students")
async def list_students(
    search: str = "",
    grade: str = "",
    status: str = "active",
    page: int = Query(default=1, ge=1),
    limit: int = Query(default=50, ge=1, le=200),
    user: dict = Depends(require_admin),
):
    conditions = []
    params: list[str | int] = []
    if search.strip():
        conditions.append("(s.full_name LIKE ? OR s.admission_number LIKE ?)")
        search_term = f"%{search.strip()}%"
        params.extend([search_term, search_term])
    if grade.strip():
        conditions.append("s.grade = ?")
        params.append(grade.strip())
    if status.strip():
        conditions.append("s.status = ?")
        params.append(_validate_status(status))

    where = " AND ".join(conditions) if conditions else "1=1"
    offset = (page - 1) * limit
    conn = get_db()
    try:
        rows = conn.execute(
            f"""SELECT s.id, s.admission_number, s.full_name, s.grade,
                       s.status, s.transport, s.updated_at,
                       COUNT(sg.guardian_id) AS guardian_count,
                       MAX(CASE WHEN sg.is_primary = 1 THEN g.full_name ELSE '' END)
                           AS primary_guardian
                FROM erp_students s
                LEFT JOIN erp_student_guardians sg ON sg.student_id = s.id
                LEFT JOIN erp_guardians g ON g.id = sg.guardian_id
                WHERE {where}
                GROUP BY s.id
                ORDER BY s.grade, s.full_name
                LIMIT ? OFFSET ?""",
            [*params, limit, offset],
        ).fetchall()
        total = conn.execute(
            f"SELECT COUNT(*) AS count FROM erp_students s WHERE {where}",
            params,
        ).fetchone()["count"]
        grade_rows = conn.execute(
            "SELECT DISTINCT grade FROM erp_students ORDER BY grade"
        ).fetchall()
    finally:
        conn.close()

    return {
        "students": [dict(row) for row in rows],
        "grades": [row["grade"] for row in grade_rows],
        "total": total,
        "page": page,
        "limit": limit,
    }


@router.get("/students/{student_id}")
async def get_student(student_id: int, user: dict = Depends(require_admin)):
    conn = get_db()
    try:
        return _get_student_detail(conn, student_id)
    finally:
        conn.close()


@router.post("/students", status_code=201)
async def create_student(body: StudentCreate, user: dict = Depends(require_admin)):
    status = _validate_status(body.status)
    now = _ist_now()
    conn = get_db()
    try:
        cursor = conn.execute(
            """INSERT INTO erp_students
               (admission_number, full_name, grade, date_of_birth, gender,
                address, transport, status, source, created_at, updated_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'manual', ?, ?)""",
            (
                body.admission_number.strip(),
                body.full_name.strip(),
                body.grade.strip(),
                body.date_of_birth.strip(),
                body.gender.strip(),
                body.address.strip(),
                body.transport.strip(),
                status,
                now,
                now,
            ),
        )
        student_id = cursor.lastrowid
        for guardian in body.guardians:
            if not guardian.full_name.strip() and not guardian.phone.strip():
                continue
            _upsert_erp_guardian(
                conn,
                student_id,
                guardian.full_name.strip(),
                guardian.phone.strip(),
                guardian.relationship.strip().lower() or "guardian",
                guardian.is_primary,
                now,
            )
        _record_audit(
            conn,
            user["user_id"],
            "create",
            student_id,
            {"full_name": body.full_name.strip(), "grade": body.grade.strip()},
        )
        conn.commit()
        return _get_student_detail(conn, student_id)
    except sqlite3.IntegrityError as exc:
        conn.rollback()
        raise HTTPException(
            status_code=409,
            detail="This admission number is already assigned",
        ) from exc
    finally:
        conn.close()


@router.put("/students/{student_id}")
async def update_student(
    student_id: int,
    body: StudentUpdate,
    user: dict = Depends(require_admin),
):
    changes = body.model_dump(exclude_unset=True)
    if not changes:
        raise HTTPException(status_code=400, detail="No changes supplied")
    if "status" in changes and changes["status"] is not None:
        changes["status"] = _validate_status(changes["status"])

    allowed_fields = {
        "admission_number",
        "full_name",
        "grade",
        "date_of_birth",
        "gender",
        "address",
        "transport",
        "status",
    }
    updates = {
        key: value.strip() if isinstance(value, str) else value
        for key, value in changes.items()
        if key in allowed_fields and value is not None
    }
    updates["updated_at"] = _ist_now()
    assignment = ", ".join(f"{field} = ?" for field in updates)

    conn = get_db()
    try:
        if not conn.execute(
            "SELECT id FROM erp_students WHERE id = ?", (student_id,)
        ).fetchone():
            raise HTTPException(status_code=404, detail="Student not found")
        conn.execute(
            f"UPDATE erp_students SET {assignment} WHERE id = ?",
            [*updates.values(), student_id],
        )
        _record_audit(
            conn,
            user["user_id"],
            "update",
            student_id,
            {"fields": sorted(key for key in updates if key != "updated_at")},
        )
        conn.commit()
        return _get_student_detail(conn, student_id)
    except sqlite3.IntegrityError as exc:
        conn.rollback()
        raise HTTPException(
            status_code=409,
            detail="This admission number is already assigned",
        ) from exc
    finally:
        conn.close()
