"""Admin-only ERP exams and report cards."""

import json
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from app.database import _ist_now, get_db
from app.routes.auth import require_admin

router = APIRouter()
EXAM_STATUSES = {"scheduled", "ongoing", "completed", "published"}


def audit(conn, user_id, action, entity_id, details=None):
    conn.execute(
        """INSERT INTO erp_audit_log
           (actor_user_id, action, entity_type, entity_id, details, created_at)
           VALUES (?, ?, 'exam', ?, ?, ?)""",
        (user_id, action, entity_id, json.dumps(details or {}), _ist_now()),
    )


def _status(value: str) -> str:
    normalized = value.strip().lower()
    if normalized not in EXAM_STATUSES:
        raise HTTPException(400, f"Invalid exam status: {value}")
    return normalized


def _exam(conn, exam_id: int):
    row = conn.execute("SELECT * FROM erp_exams WHERE id = ?", (exam_id,)).fetchone()
    if not row:
        raise HTTPException(404, "Exam not found")
    return row


def _session(conn, session_id: Optional[int]):
    if session_id is not None and not conn.execute(
        "SELECT id FROM erp_academic_sessions WHERE id = ?", (session_id,)
    ).fetchone():
        raise HTTPException(404, "Academic session not found")


class ExamCreate(BaseModel):
    name: str = Field(min_length=1)
    session_id: Optional[int] = None
    term: str = ""
    grade: str = ""
    max_marks: float = Field(default=100, gt=0)
    exam_date: str = ""
    status: str = "scheduled"


class ExamUpdate(BaseModel):
    name: Optional[str] = Field(default=None, min_length=1)
    session_id: Optional[int] = None
    term: Optional[str] = None
    grade: Optional[str] = None
    max_marks: Optional[float] = Field(default=None, gt=0)
    exam_date: Optional[str] = None
    status: Optional[str] = None


class SubjectCreate(BaseModel):
    subject: str = Field(min_length=1)
    max_marks: float = Field(default=100, gt=0)
    pass_marks: float = Field(default=33, ge=0)


class MarkEntry(BaseModel):
    student_id: int
    subject_id: int
    marks_obtained: Optional[float] = None
    is_absent: bool = False
    remarks: str = ""


class MarksIn(BaseModel):
    entries: list[MarkEntry] = Field(default_factory=list)


def _grade_letter(percentage: float) -> str:
    if percentage >= 90:
        return "A1"
    if percentage >= 80:
        return "A2"
    if percentage >= 70:
        return "B1"
    if percentage >= 60:
        return "B2"
    if percentage >= 50:
        return "C1"
    if percentage >= 40:
        return "C2"
    if percentage >= 33:
        return "D"
    return "E"


@router.get("/exams")
async def list_exams(
    session_id: Optional[int] = None,
    grade: str = "",
    status: str = "",
    user=Depends(require_admin),
):
    if status:
        status = _status(status)
    conn = get_db()
    try:
        clauses = []
        params = []
        if session_id is not None:
            _session(conn, session_id)
            clauses.append("e.session_id = ?")
            params.append(session_id)
        if grade.strip():
            clauses.append("e.grade = ?")
            params.append(grade.strip())
        if status:
            clauses.append("e.status = ?")
            params.append(status)
        where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
        rows = conn.execute(
            f"""SELECT e.*, COUNT(s.id) AS subject_count
                FROM erp_exams e
                LEFT JOIN erp_exam_subjects s ON s.exam_id = e.id
                {where}
                GROUP BY e.id ORDER BY e.created_at DESC, e.id DESC""",
            params,
        ).fetchall()
        return {"exams": [dict(row) for row in rows]}
    finally:
        conn.close()


@router.post("/exams", status_code=201)
async def create_exam(body: ExamCreate, user=Depends(require_admin)):
    status = _status(body.status)
    conn = get_db()
    try:
        _session(conn, body.session_id)
        now = _ist_now()
        cur = conn.execute(
            """INSERT INTO erp_exams
               (session_id, name, term, grade, max_marks, exam_date, status, created_at, updated_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                body.session_id,
                body.name.strip(),
                body.term,
                body.grade,
                body.max_marks,
                body.exam_date,
                status,
                now,
                now,
            ),
        )
        audit(conn, user["user_id"], "create", cur.lastrowid, body.model_dump())
        conn.commit()
        return dict(_exam(conn, cur.lastrowid))
    finally:
        conn.close()


@router.get("/exams/{exam_id}")
async def get_exam(exam_id: int, user=Depends(require_admin)):
    conn = get_db()
    try:
        exam = dict(_exam(conn, exam_id))
        exam["subjects"] = [
            dict(row)
            for row in conn.execute(
                "SELECT * FROM erp_exam_subjects WHERE exam_id = ? ORDER BY id",
                (exam_id,),
            ).fetchall()
        ]
        return exam
    finally:
        conn.close()


@router.put("/exams/{exam_id}")
async def update_exam(
    exam_id: int,
    body: ExamUpdate,
    user=Depends(require_admin),
):
    conn = get_db()
    try:
        _exam(conn, exam_id)
        values = body.model_dump(exclude_unset=True)
        if not values:
            return dict(_exam(conn, exam_id))
        if "status" in values:
            values["status"] = _status(values["status"])
        if "session_id" in values:
            _session(conn, values["session_id"])
        if "name" in values:
            values["name"] = values["name"].strip()
        assignments = ", ".join(f"{key} = ?" for key in values)
        now = _ist_now()
        conn.execute(
            f"UPDATE erp_exams SET {assignments}, updated_at = ? WHERE id = ?",
            [*values.values(), now, exam_id],
        )
        audit(conn, user["user_id"], "update", exam_id, values)
        conn.commit()
        return dict(_exam(conn, exam_id))
    finally:
        conn.close()


@router.post("/exams/{exam_id}/subjects", status_code=201)
async def add_subject(exam_id: int, body: SubjectCreate, user=Depends(require_admin)):
    conn = get_db()
    try:
        _exam(conn, exam_id)
        now = _ist_now()
        cur = conn.execute(
            """INSERT INTO erp_exam_subjects
               (exam_id, subject, max_marks, pass_marks, created_at)
               VALUES (?, ?, ?, ?, ?)""",
            (exam_id, body.subject.strip(), body.max_marks, body.pass_marks, now),
        )
        audit(conn, user["user_id"], "add_subject", exam_id, body.model_dump())
        conn.commit()
        return dict(
            conn.execute(
                "SELECT * FROM erp_exam_subjects WHERE id = ?", (cur.lastrowid,)
            ).fetchone()
        )
    finally:
        conn.close()


@router.delete("/exams/{exam_id}/subjects/{subject_id}")
async def delete_subject(
    exam_id: int,
    subject_id: int,
    user=Depends(require_admin),
):
    conn = get_db()
    try:
        _exam(conn, exam_id)
        subject = conn.execute(
            "SELECT * FROM erp_exam_subjects WHERE id = ? AND exam_id = ?",
            (subject_id, exam_id),
        ).fetchone()
        if not subject:
            raise HTTPException(404, "Exam subject not found")
        if conn.execute(
            "SELECT 1 FROM erp_exam_marks WHERE subject_id = ? LIMIT 1",
            (subject_id,),
        ).fetchone():
            raise HTTPException(400, "Cannot remove a subject with marks entered")
        conn.execute("DELETE FROM erp_exam_subjects WHERE id = ?", (subject_id,))
        audit(conn, user["user_id"], "delete_subject", exam_id, {"subject_id": subject_id})
        conn.commit()
        return {"ok": True}
    finally:
        conn.close()


@router.get("/exams/{exam_id}/marks")
async def get_exam_marks(
    exam_id: int,
    grade: str = "",
    user=Depends(require_admin),
):
    conn = get_db()
    try:
        exam = _exam(conn, exam_id)
        subjects = [
            dict(row)
            for row in conn.execute(
                "SELECT * FROM erp_exam_subjects WHERE exam_id = ? ORDER BY id",
                (exam_id,),
            ).fetchall()
        ]
        selected_grade = grade.strip() or exam["grade"]
        clauses = ["s.status = 'active'"]
        params = []
        if selected_grade:
            clauses.append("s.grade = ?")
            params.append(selected_grade)
        students = conn.execute(
            f"""SELECT s.id AS student_id, s.full_name, s.grade, s.admission_number
                FROM erp_students s
                WHERE {' AND '.join(clauses)}
                ORDER BY s.grade, s.full_name""",
            params,
        ).fetchall()
        student_rows = []
        for student in students:
            marks = conn.execute(
                """SELECT subject_id, marks_obtained, is_absent, remarks
                   FROM erp_exam_marks WHERE exam_id = ? AND student_id = ?""",
                (exam_id, student["student_id"]),
            ).fetchall()
            marks_map = {str(row["subject_id"]): dict(row) for row in marks}
            student_rows.append({**dict(student), "marks": marks_map})
        return {"exam": dict(exam), "subjects": subjects, "students": student_rows}
    finally:
        conn.close()


@router.post("/exams/{exam_id}/marks")
async def save_exam_marks(
    exam_id: int,
    body: MarksIn,
    user=Depends(require_admin),
):
    conn = get_db()
    try:
        _exam(conn, exam_id)
        now = _ist_now()
        for entry in body.entries:
            subject = conn.execute(
                "SELECT * FROM erp_exam_subjects WHERE id = ? AND exam_id = ?",
                (entry.subject_id, exam_id),
            ).fetchone()
            if not subject:
                raise HTTPException(400, "Subject does not belong to this exam")
            if not conn.execute(
                "SELECT id FROM erp_students WHERE id = ?", (entry.student_id,)
            ).fetchone():
                raise HTTPException(404, "Student not found")
            if entry.marks_obtained is not None and (
                entry.marks_obtained < 0
                or entry.marks_obtained > subject["max_marks"]
            ):
                raise HTTPException(400, "Marks exceed the subject maximum")
            marks = None if entry.is_absent else entry.marks_obtained
            conn.execute(
                """INSERT INTO erp_exam_marks
                   (exam_id, subject_id, student_id, marks_obtained, is_absent,
                    remarks, updated_by, created_at, updated_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                   ON CONFLICT(subject_id, student_id) DO UPDATE SET
                     exam_id = excluded.exam_id,
                     marks_obtained = excluded.marks_obtained,
                     is_absent = excluded.is_absent,
                     remarks = excluded.remarks,
                     updated_by = excluded.updated_by,
                     updated_at = excluded.updated_at""",
                (
                    exam_id,
                    entry.subject_id,
                    entry.student_id,
                    marks,
                    int(entry.is_absent),
                    entry.remarks,
                    user["user_id"],
                    now,
                    now,
                ),
            )
        audit(
            conn,
            user["user_id"],
            "mark",
            exam_id,
            {"entries": len(body.entries)},
        )
        conn.commit()
        return {"ok": True, "saved": len(body.entries)}
    finally:
        conn.close()


@router.get("/exams/{exam_id}/report-card/{student_id}")
async def get_report_card(
    exam_id: int,
    student_id: int,
    user=Depends(require_admin),
):
    conn = get_db()
    try:
        exam = _exam(conn, exam_id)
        student = conn.execute(
            "SELECT * FROM erp_students WHERE id = ?", (student_id,)
        ).fetchone()
        if not student:
            raise HTTPException(404, "Student not found")
        subjects = conn.execute(
            """SELECT s.*, m.marks_obtained, m.is_absent, m.remarks
               FROM erp_exam_subjects s
               LEFT JOIN erp_exam_marks m
                 ON m.subject_id = s.id AND m.student_id = ? AND m.exam_id = ?
               WHERE s.exam_id = ? ORDER BY s.id""",
            (student_id, exam_id, exam_id),
        ).fetchall()
        obtained = sum(
            row["marks_obtained"]
            for row in subjects
            if row["marks_obtained"] is not None and not row["is_absent"]
        )
        max_total = sum(
            row["max_marks"]
            for row in subjects
            if row["marks_obtained"] is not None and not row["is_absent"]
        )
        percentage = round((obtained / max_total) * 100, 2) if max_total else 0
        subject_rows = []
        for row in subjects:
            mark = row["marks_obtained"]
            subject_rows.append(
                {
                    **dict(row),
                    "passed": bool(
                        mark is not None
                        and not row["is_absent"]
                        and mark >= row["pass_marks"]
                    ),
                }
            )
        return {
            "exam": dict(exam),
            "student": dict(student),
            "subjects": subject_rows,
            "total_obtained": obtained,
            "total_max": max_total,
            "percentage": percentage,
            "grade_letter": _grade_letter(percentage),
        }
    finally:
        conn.close()


@router.get("/exams/{exam_id}/results")
async def get_exam_results(
    exam_id: int,
    grade: str = "",
    user=Depends(require_admin),
):
    conn = get_db()
    try:
        exam = _exam(conn, exam_id)
        selected_grade = grade.strip() or exam["grade"]
        clauses = ["s.status = 'active'"]
        params = []
        if selected_grade:
            clauses.append("s.grade = ?")
            params.append(selected_grade)
        students = conn.execute(
            f"""SELECT s.id AS student_id, s.full_name, s.grade, s.admission_number
                FROM erp_students s
                WHERE {' AND '.join(clauses)}
                ORDER BY s.grade, s.full_name""",
            params,
        ).fetchall()
        results = []
        for student in students:
            totals = conn.execute(
                """SELECT
                     COALESCE(SUM(CASE WHEN m.marks_obtained IS NOT NULL
                                      AND m.is_absent = 0 THEN m.marks_obtained ELSE 0 END), 0)
                       AS obtained,
                     COALESCE(SUM(CASE WHEN m.marks_obtained IS NOT NULL
                                      AND m.is_absent = 0 THEN s.max_marks ELSE 0 END), 0)
                       AS marked_max
                   FROM erp_exam_subjects s
                   LEFT JOIN erp_exam_marks m
                     ON m.subject_id = s.id AND m.exam_id = ? AND m.student_id = ?
                   WHERE s.exam_id = ?""",
                (exam_id, student["student_id"], exam_id),
            ).fetchone()
            obtained = totals["obtained"]
            denominator = totals["marked_max"]
            results.append(
                {
                    **dict(student),
                    "total_obtained": obtained,
                    "total_max": denominator,
                    "percentage": round((obtained / denominator) * 100, 2)
                    if denominator
                    else 0,
                }
            )
        results.sort(key=lambda row: row["percentage"], reverse=True)
        previous = None
        for index, row in enumerate(results, 1):
            if previous is None or row["percentage"] != previous:
                rank = index
                previous = row["percentage"]
            row["rank"] = rank
        return {"exam": dict(exam), "results": results}
    finally:
        conn.close()
