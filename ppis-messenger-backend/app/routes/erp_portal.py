"""Self-scoped read-only parent/teacher portal and teacher administration."""

import json
import sqlite3
from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field

from app.database import _ist_now, _normalize_phone, get_db
from app.routes.auth import require_admin, require_portal_user

router = APIRouter()


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


def _parent_student_ids(conn, user) -> set[int]:
    phone = _normalize_phone(user.get("phone", ""))
    rows = conn.execute(
        """SELECT DISTINCT sg.student_id
           FROM erp_guardians g
           JOIN erp_student_guardians sg ON sg.guardian_id = g.id
           WHERE g.phone = ?""",
        (phone,),
    ).fetchall()
    return {row["student_id"] for row in rows}


def _assert_parent_owns(conn, user, student_id: int):
    if student_id not in _parent_student_ids(conn, user):
        raise HTTPException(403, "You do not own this student")


def _teacher_grades(conn, user) -> set[str]:
    rows = conn.execute(
        "SELECT grade FROM erp_teacher_grades WHERE user_id = ?",
        (user["user_id"],),
    ).fetchall()
    return {row["grade"] for row in rows}


def _assert_teacher_grade(conn, user, grade: str):
    if grade not in _teacher_grades(conn, user):
        raise HTTPException(403, "You are not assigned to this grade")


def _student(conn, student_id: int):
    row = conn.execute(
        "SELECT id, full_name, grade, admission_number, date_of_birth, gender, address "
        "FROM erp_students WHERE id = ?",
        (student_id,),
    ).fetchone()
    if not row:
        raise HTTPException(404, "Student not found")
    return row


def _attendance(conn, student_id: int, from_date: str, to_date: str):
    from_date = _date(from_date)
    to_date = _date(to_date)
    if from_date > to_date:
        raise HTTPException(400, "from must be before to")
    try:
        rows = conn.execute(
            """SELECT * FROM erp_attendance
               WHERE student_id = ? AND date BETWEEN ? AND ?
               ORDER BY date""",
            (student_id, from_date, to_date),
        ).fetchall()
    except sqlite3.OperationalError:
        rows = []
    records = [dict(row) for row in rows]
    present = sum(row["status"] in ("present", "late", "half_day") for row in records)
    return {
        "records": records,
        "total": len(records),
        "present": present,
        "percentage": round(present * 100 / len(records), 2) if records else 0,
    }


def _report_card(conn, exam_id: int, student_id: int):
    exam = conn.execute("SELECT * FROM erp_exams WHERE id = ?", (exam_id,)).fetchone()
    if not exam:
        raise HTTPException(404, "Exam not found")
    student = _student(conn, student_id)
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
    marked_max = sum(
        row["max_marks"]
        for row in subjects
        if row["marks_obtained"] is not None and not row["is_absent"]
    )
    percentage = round(obtained * 100 / marked_max, 2) if marked_max else 0
    grade = (
        "A1" if percentage >= 91 else "A2" if percentage >= 81 else
        "B1" if percentage >= 71 else "B2" if percentage >= 61 else
        "C1" if percentage >= 51 else "C2" if percentage >= 41 else
        "D" if percentage >= 33 else "E"
    )
    return {
        "exam": dict(exam),
        "student": dict(student),
        "subjects": [
            {
                **dict(row),
                "passed": bool(
                    row["marks_obtained"] is not None
                    and not row["is_absent"]
                    and row["marks_obtained"] >= row["pass_marks"]
                ),
            }
            for row in subjects
        ],
        "total_obtained": obtained,
        "total_max": marked_max,
        "percentage": percentage,
        "grade_letter": grade,
    }


class TeacherIn(BaseModel):
    phone: str = Field(min_length=1)
    name: str = ""
    grades: list[str] = []


@router.get("/portal/teachers")
async def list_teachers(user=Depends(require_admin)):
    conn = get_db()
    try:
        rows = conn.execute(
            "SELECT id, phone, name, role FROM users WHERE role = 'teacher' ORDER BY name, phone"
        ).fetchall()
        result = []
        for row in rows:
            item = dict(row)
            item["grades"] = [
                x["grade"] for x in conn.execute(
                    "SELECT grade FROM erp_teacher_grades WHERE user_id = ? ORDER BY grade",
                    (row["id"],),
                ).fetchall()
            ]
            result.append(item)
        return {"teachers": result}
    finally:
        conn.close()


@router.post("/portal/teachers")
async def upsert_teacher(body: TeacherIn, user=Depends(require_admin)):
    phone = _normalize_phone(body.phone)
    grades = sorted({grade.strip() for grade in body.grades if grade.strip()})
    conn = get_db()
    try:
        conn.execute(
            """INSERT INTO users(phone, name, role)
               VALUES (?, ?, 'teacher')
               ON CONFLICT(phone) DO UPDATE SET name = excluded.name, role = 'teacher'""",
            (phone, body.name.strip()),
        )
        teacher = conn.execute("SELECT id, phone, name, role FROM users WHERE phone = ?", (phone,)).fetchone()
        conn.execute("DELETE FROM erp_teacher_grades WHERE user_id = ?", (teacher["id"],))
        conn.executemany(
            "INSERT INTO erp_teacher_grades(user_id, grade) VALUES (?, ?)",
            [(teacher["id"], grade) for grade in grades],
        )
        audit(conn, user["user_id"], "upsert", "teacher", teacher["id"], {"grades": grades})
        conn.commit()
        return {**dict(teacher), "grades": grades}
    finally:
        conn.close()


@router.delete("/portal/teachers/{user_id}/grades/{grade}")
async def unassign_teacher_grade(user_id: int, grade: str, user=Depends(require_admin)):
    conn = get_db()
    try:
        cur = conn.execute(
            "DELETE FROM erp_teacher_grades WHERE user_id = ? AND grade = ?",
            (user_id, grade),
        )
        if not cur.rowcount:
            raise HTTPException(404, "Teacher grade assignment not found")
        audit(conn, user["user_id"], "unassign", "teacher", user_id, {"grade": grade})
        conn.commit()
        return {"ok": True}
    finally:
        conn.close()


@router.get("/portal/me")
async def portal_me(user=Depends(require_portal_user)):
    conn = get_db()
    try:
        current = conn.execute("SELECT id, name, role FROM users WHERE id = ?", (user["user_id"],)).fetchone()
        result = {"role": user["role"], "name": current["name"] if current else "", "children": [], "grades": []}
        if user["role"] == "parent":
            ids = _parent_student_ids(conn, user)
            result["children"] = [
                dict(row) for row in conn.execute(
                    f"""SELECT id, full_name, grade, admission_number FROM erp_students
                        WHERE id IN ({','.join('?' * len(ids))}) ORDER BY full_name""",
                    tuple(ids),
                ).fetchall()
            ] if ids else []
        else:
            result["grades"] = sorted(_teacher_grades(conn, user))
        return result
    finally:
        conn.close()


@router.get("/portal/children")
async def portal_children(user=Depends(require_portal_user)):
    if user["role"] != "parent":
        raise HTTPException(403, "Parent access required")
    conn = get_db()
    try:
        ids = _parent_student_ids(conn, user)
        return {"children": [
            dict(row) for row in conn.execute(
                f"SELECT id, full_name, grade, admission_number FROM erp_students "
                f"WHERE id IN ({','.join('?' * len(ids))}) ORDER BY full_name",
                tuple(ids),
            ).fetchall()
        ] if ids else []}
    finally:
        conn.close()


@router.get("/portal/children/{student_id}/attendance")
async def child_attendance(student_id: int, from_date: str = Query(alias="from"), to_date: str = Query(alias="to"), user=Depends(require_portal_user)):
    conn = get_db()
    try:
        if user["role"] != "parent":
            raise HTTPException(403, "Parent access required")
        _assert_parent_owns(conn, user, student_id)
        return _attendance(conn, student_id, from_date, to_date)
    finally:
        conn.close()


@router.get("/portal/children/{student_id}/fees")
async def child_fees(student_id: int, user=Depends(require_portal_user)):
    conn = get_db()
    try:
        if user["role"] != "parent":
            raise HTTPException(403, "Parent access required")
        _assert_parent_owns(conn, user, student_id)
        rows = conn.execute(
            """SELECT i.*, COALESCE(SUM(CASE WHEN p.status = 'confirmed'
                       THEN a.amount_paise ELSE 0 END), 0) AS collected_paise
               FROM erp_invoices i
               LEFT JOIN erp_payment_allocations a ON a.invoice_id = i.id
               LEFT JOIN erp_payments p ON p.id = a.payment_id
               WHERE i.student_id = ? GROUP BY i.id ORDER BY i.due_date, i.id""",
            (student_id,),
        ).fetchall()
        invoices = []
        outstanding = 0
        for row in rows:
            item = dict(row)
            item["outstanding_paise"] = row["net_paise"] - row["collected_paise"]
            outstanding += item["outstanding_paise"]
            invoices.append(item)
        return {"invoices": invoices, "outstanding_paise": outstanding}
    finally:
        conn.close()


@router.get("/portal/children/{student_id}/report-cards")
async def child_report_cards(student_id: int, user=Depends(require_portal_user)):
    conn = get_db()
    try:
        if user["role"] != "parent":
            raise HTTPException(403, "Parent access required")
        _assert_parent_owns(conn, user, student_id)
        student = _student(conn, student_id)
        rows = conn.execute(
            "SELECT * FROM erp_exams WHERE status = 'published' AND (grade = '' OR grade = ?) ORDER BY exam_date DESC, id DESC",
            (student["grade"],),
        ).fetchall()
        return {"exams": [dict(row) for row in rows]}
    finally:
        conn.close()


@router.get("/portal/children/{student_id}/report-cards/{exam_id}")
async def child_report_card(student_id: int, exam_id: int, user=Depends(require_portal_user)):
    conn = get_db()
    try:
        if user["role"] != "parent":
            raise HTTPException(403, "Parent access required")
        _assert_parent_owns(conn, user, student_id)
        if not conn.execute("SELECT 1 FROM erp_exams WHERE id = ? AND status = 'published'", (exam_id,)).fetchone():
            raise HTTPException(404, "Published report card not found")
        return _report_card(conn, exam_id, student_id)
    finally:
        conn.close()


@router.get("/portal/children/{student_id}/homework")
async def child_homework(student_id: int, user=Depends(require_portal_user)):
    conn = get_db()
    try:
        if user["role"] != "parent":
            raise HTTPException(403, "Parent access required")
        _assert_parent_owns(conn, user, student_id)
        grade = _student(conn, student_id)["grade"]
        try:
            rows = conn.execute(
                "SELECT * FROM erp_homework WHERE grade = ? ORDER BY assigned_date DESC, id DESC", (grade,)
            ).fetchall()
        except sqlite3.OperationalError:
            rows = []
        return {"homework": [dict(row) for row in rows]}
    finally:
        conn.close()


@router.get("/portal/children/{student_id}/timetable")
async def child_timetable(student_id: int, user=Depends(require_portal_user)):
    conn = get_db()
    try:
        if user["role"] != "parent":
            raise HTTPException(403, "Parent access required")
        _assert_parent_owns(conn, user, student_id)
        grade = _student(conn, student_id)["grade"]
        try:
            rows = conn.execute(
                "SELECT * FROM erp_timetable_slots WHERE grade = ? ORDER BY day_of_week, period", (grade,)
            ).fetchall()
        except sqlite3.OperationalError:
            rows = []
        return {"slots": [dict(row) for row in rows]}
    finally:
        conn.close()


@router.get("/portal/teacher/grades")
async def teacher_grades(user=Depends(require_portal_user)):
    if user["role"] != "teacher":
        raise HTTPException(403, "Teacher access required")
    conn = get_db()
    try:
        return {"grades": sorted(_teacher_grades(conn, user))}
    finally:
        conn.close()


@router.get("/portal/teacher/grades/{grade}/students")
async def grade_students(grade: str, user=Depends(require_portal_user)):
    conn = get_db()
    try:
        if user["role"] != "teacher":
            raise HTTPException(403, "Teacher access required")
        _assert_teacher_grade(conn, user, grade)
        return {"students": [dict(row) for row in conn.execute(
            "SELECT id, full_name, grade, admission_number FROM erp_students WHERE grade = ? AND status = 'active' ORDER BY full_name",
            (grade,),
        ).fetchall()]}
    finally:
        conn.close()


@router.get("/portal/teacher/grades/{grade}/attendance/summary")
async def grade_attendance_summary(grade: str, from_date: str = Query(alias="from"), to_date: str = Query(alias="to"), user=Depends(require_portal_user)):
    conn = get_db()
    try:
        if user["role"] != "teacher":
            raise HTTPException(403, "Teacher access required")
        _assert_teacher_grade(conn, user, grade)
        from_date, to_date = _date(from_date), _date(to_date)
        if from_date > to_date:
            raise HTTPException(400, "from must be before to")
        try:
            rows = conn.execute(
                """SELECT a.date, a.status, COUNT(*) AS count
                   FROM erp_attendance a JOIN erp_students s ON s.id = a.student_id
                   WHERE s.grade = ? AND s.status = 'active' AND a.date BETWEEN ? AND ?
                   GROUP BY a.date, a.status ORDER BY a.date""",
                (grade, from_date, to_date),
            ).fetchall()
        except sqlite3.OperationalError:
            rows = []
        by_day = {}
        for row in rows:
            by_day.setdefault(row["date"], {})[row["status"]] = row["count"]
        return {"days": [{"date": key, **value} for key, value in by_day.items()]}
    finally:
        conn.close()


@router.get("/portal/teacher/grades/{grade}/homework")
async def grade_homework(grade: str, user=Depends(require_portal_user)):
    conn = get_db()
    try:
        if user["role"] != "teacher":
            raise HTTPException(403, "Teacher access required")
        _assert_teacher_grade(conn, user, grade)
        try:
            rows = conn.execute(
                "SELECT * FROM erp_homework WHERE grade = ? ORDER BY assigned_date DESC, id DESC", (grade,)
            ).fetchall()
        except sqlite3.OperationalError:
            rows = []
        return {"homework": [dict(row) for row in rows]}
    finally:
        conn.close()


@router.get("/portal/teacher/grades/{grade}/timetable")
async def grade_timetable(grade: str, user=Depends(require_portal_user)):
    conn = get_db()
    try:
        if user["role"] != "teacher":
            raise HTTPException(403, "Teacher access required")
        _assert_teacher_grade(conn, user, grade)
        try:
            rows = conn.execute(
                "SELECT * FROM erp_timetable_slots WHERE grade = ? ORDER BY day_of_week, period", (grade,)
            ).fetchall()
        except sqlite3.OperationalError:
            rows = []
        return {"slots": [dict(row) for row in rows]}
    finally:
        conn.close()
