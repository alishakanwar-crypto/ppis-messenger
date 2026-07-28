"""Admin-only ERP admissions management."""

import json
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field

from app.database import _ist_now, _upsert_erp_guardian, get_db
from app.routes.auth import require_admin

from app.routes.erp_fees import counter

router = APIRouter()

ADMISSION_STATUSES = {
    "enquiry",
    "applied",
    "shortlisted",
    "offered",
    "admitted",
    "rejected",
    "withdrawn",
}


def audit(conn, user_id, action, entity_id, details=None):
    conn.execute(
        """INSERT INTO erp_audit_log
           (actor_user_id, action, entity_type, entity_id, details, created_at)
           VALUES (?, ?, 'admission', ?, ?, ?)""",
        (user_id, action, entity_id, json.dumps(details or {}), _ist_now()),
    )


def _validate_status(status: str) -> str:
    normalized = status.strip().lower()
    if normalized not in ADMISSION_STATUSES:
        raise HTTPException(400, f"Invalid admission status: {status}")
    return normalized


def _get_enquiry(conn, enquiry_id: int):
    row = conn.execute(
        "SELECT * FROM erp_admission_enquiries WHERE id = ?", (enquiry_id,)
    ).fetchone()
    if not row:
        raise HTTPException(404, "Admission enquiry not found")
    return row


def _session(conn, session_id: Optional[int]):
    if session_id is None:
        return
    if not conn.execute(
        "SELECT id FROM erp_academic_sessions WHERE id = ?", (session_id,)
    ).fetchone():
        raise HTTPException(404, "Academic session not found")


class AdmissionCreate(BaseModel):
    applicant_name: str = Field(min_length=1)
    grade_applying: str = ""
    date_of_birth: str = ""
    gender: str = ""
    parent_name: str = ""
    parent_phone: str = ""
    parent_email: str = ""
    address: str = ""
    previous_school: str = ""
    source: str = ""
    notes: str = ""
    session_id: Optional[int] = None


class AdmissionUpdate(BaseModel):
    applicant_name: Optional[str] = Field(default=None, min_length=1)
    grade_applying: Optional[str] = None
    date_of_birth: Optional[str] = None
    gender: Optional[str] = None
    parent_name: Optional[str] = None
    parent_phone: Optional[str] = None
    parent_email: Optional[str] = None
    address: Optional[str] = None
    previous_school: Optional[str] = None
    source: Optional[str] = None
    notes: Optional[str] = None
    session_id: Optional[int] = None


class AdmissionStatusIn(BaseModel):
    status: str
    note: str = ""


@router.get("/admissions")
async def list_admissions(
    status: str = "",
    grade: str = "",
    search: str = "",
    page: int = Query(default=1, ge=1),
    limit: int = Query(default=50, ge=1, le=200),
    user=Depends(require_admin),
):
    conditions = []
    params = []
    if status.strip():
        conditions.append("a.status = ?")
        params.append(_validate_status(status))
    if grade.strip():
        conditions.append("a.grade_applying = ?")
        params.append(grade.strip())
    if search.strip():
        term = f"%{search.strip()}%"
        conditions.append(
            "(a.applicant_name LIKE ? OR a.application_number LIKE ? OR a.parent_phone LIKE ?)"
        )
        params.extend([term, term, term])
    where = f"WHERE {' AND '.join(conditions)}" if conditions else ""
    offset = (page - 1) * limit
    conn = get_db()
    try:
        items = conn.execute(
            f"""SELECT a.*, s.full_name AS student_full_name
                FROM erp_admission_enquiries a
                LEFT JOIN erp_students s ON s.id = a.student_id
                {where}
                ORDER BY a.created_at DESC, a.id DESC
                LIMIT ? OFFSET ?""",
            [*params, limit, offset],
        ).fetchall()
        total = conn.execute(
            f"SELECT COUNT(*) AS count FROM erp_admission_enquiries a {where}",
            params,
        ).fetchone()["count"]
        return {
            "items": [dict(row) for row in items],
            "total": total,
            "page": page,
            "limit": limit,
        }
    finally:
        conn.close()


@router.get("/admissions/summary")
async def admissions_summary(user=Depends(require_admin)):
    conn = get_db()
    try:
        status_rows = conn.execute(
            """SELECT status, COUNT(*) AS count
               FROM erp_admission_enquiries
               GROUP BY status ORDER BY status"""
        ).fetchall()
        grade_rows = conn.execute(
            """SELECT grade_applying AS grade, COUNT(*) AS count
               FROM erp_admission_enquiries
               GROUP BY grade_applying ORDER BY grade_applying"""
        ).fetchall()
        return {
            "by_status": [dict(row) for row in status_rows],
            "by_grade": [dict(row) for row in grade_rows],
        }
    finally:
        conn.close()


@router.get("/admissions/{enquiry_id}")
async def get_admission(enquiry_id: int, user=Depends(require_admin)):
    conn = get_db()
    try:
        return dict(_get_enquiry(conn, enquiry_id))
    finally:
        conn.close()


@router.post("/admissions", status_code=201)
async def create_admission(body: AdmissionCreate, user=Depends(require_admin)):
    conn = get_db()
    try:
        _session(conn, body.session_id)
        now = _ist_now()
        year = datetime.fromisoformat(now).year
        application_number = f"ADM-{year}-{counter(conn, f'admission_{year}'):04d}"
        cur = conn.execute(
            """INSERT INTO erp_admission_enquiries
               (application_number, applicant_name, grade_applying, date_of_birth, gender,
                parent_name, parent_phone, parent_email, address, previous_school, source,
                notes, session_id, created_at, updated_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                application_number,
                body.applicant_name.strip(),
                body.grade_applying.strip(),
                body.date_of_birth,
                body.gender,
                body.parent_name,
                body.parent_phone,
                body.parent_email,
                body.address,
                body.previous_school,
                body.source,
                body.notes,
                body.session_id,
                now,
                now,
            ),
        )
        audit(conn, user["user_id"], "create", cur.lastrowid, body.model_dump())
        conn.commit()
        return dict(_get_enquiry(conn, cur.lastrowid))
    finally:
        conn.close()


@router.put("/admissions/{enquiry_id}")
async def update_admission(
    enquiry_id: int,
    body: AdmissionUpdate,
    user=Depends(require_admin),
):
    conn = get_db()
    try:
        _get_enquiry(conn, enquiry_id)
        values = body.model_dump(exclude_unset=True)
        if not values:
            return dict(_get_enquiry(conn, enquiry_id))
        _session(conn, values.get("session_id"))
        if "applicant_name" in values:
            values["applicant_name"] = values["applicant_name"].strip()
        assignments = ", ".join(f"{key} = ?" for key in values)
        now = _ist_now()
        conn.execute(
            f"UPDATE erp_admission_enquiries SET {assignments}, updated_at = ? WHERE id = ?",
            [*values.values(), now, enquiry_id],
        )
        audit(conn, user["user_id"], "update", enquiry_id, values)
        conn.commit()
        return dict(_get_enquiry(conn, enquiry_id))
    finally:
        conn.close()


@router.post("/admissions/{enquiry_id}/status")
async def set_admission_status(
    enquiry_id: int,
    body: AdmissionStatusIn,
    user=Depends(require_admin),
):
    status = _validate_status(body.status)
    conn = get_db()
    try:
        _get_enquiry(conn, enquiry_id)
        now = _ist_now()
        if body.note.strip():
            conn.execute(
                """UPDATE erp_admission_enquiries
                   SET status = ?, notes = CASE WHEN notes = '' THEN ? ELSE notes || char(10) || ? END,
                       updated_at = ?
                   WHERE id = ?""",
                (status, body.note.strip(), body.note.strip(), now, enquiry_id),
            )
        else:
            conn.execute(
                "UPDATE erp_admission_enquiries SET status = ?, updated_at = ? WHERE id = ?",
                (status, now, enquiry_id),
            )
        audit(
            conn,
            user["user_id"],
            "status",
            enquiry_id,
            {"status": status, "note": body.note},
        )
        conn.commit()
        return dict(_get_enquiry(conn, enquiry_id))
    finally:
        conn.close()


@router.post("/admissions/{enquiry_id}/convert")
async def convert_admission(enquiry_id: int, user=Depends(require_admin)):
    conn = get_db()
    try:
        enquiry = _get_enquiry(conn, enquiry_id)
        if enquiry["student_id"]:
            return {"student_id": enquiry["student_id"]}
        now = _ist_now()
        student_id = conn.execute(
            """INSERT INTO erp_students
               (full_name, grade, date_of_birth, gender, address, status, source,
                created_at, updated_at)
               VALUES (?, ?, ?, ?, ?, 'active', 'admission', ?, ?)""",
            (
                enquiry["applicant_name"],
                enquiry["grade_applying"],
                enquiry["date_of_birth"],
                enquiry["gender"],
                enquiry["address"],
                now,
                now,
            ),
        ).lastrowid
        _upsert_erp_guardian(
            conn,
            student_id,
            enquiry["parent_name"],
            enquiry["parent_phone"],
            "parent",
            True,
            now,
        )
        conn.execute(
            """UPDATE erp_admission_enquiries
               SET status = 'admitted', student_id = ?, updated_at = ?
               WHERE id = ?""",
            (student_id, now, enquiry_id),
        )
        audit(
            conn,
            user["user_id"],
            "convert",
            enquiry_id,
            {"student_id": student_id},
        )
        conn.commit()
        return {"student_id": student_id}
    finally:
        conn.close()
