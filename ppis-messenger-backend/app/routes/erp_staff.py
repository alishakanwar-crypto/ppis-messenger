"""Admin-only ERP staff and payroll management."""

import json
from decimal import Decimal, ROUND_HALF_UP
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field

from app.database import _ist_now, get_db
from app.routes.auth import require_admin
from app.routes.erp_fees import counter

router = APIRouter()
STAFF_STATUSES = {"active", "inactive"}
PAYROLL_STATUSES = {"draft", "finalized"}


def audit(conn, user_id, action, entity_type, entity_id, details=None):
    conn.execute(
        """INSERT INTO erp_audit_log
           (actor_user_id, action, entity_type, entity_id, details, created_at)
           VALUES (?, ?, ?, ?, ?, ?)""",
        (user_id, action, entity_type, entity_id, json.dumps(details or {}), _ist_now()),
    )


def _to_paise(rupees) -> int:
    try:
        value = Decimal(str(rupees))
    except Exception as exc:
        raise HTTPException(400, "Money must be a number") from exc
    if value < 0:
        raise HTTPException(400, "Money cannot be negative")
    return int((value * 100).quantize(Decimal("1"), rounding=ROUND_HALF_UP))


def _to_rupees(paise: int) -> float:
    return float((Decimal(paise) / 100).quantize(Decimal("0.01")))


def _status(value: str) -> str:
    value = value.strip().lower()
    if value not in STAFF_STATUSES:
        raise HTTPException(400, f"Invalid staff status: {value}")
    return value


def _month(value: str) -> str:
    try:
        parsed = datetime.strptime(value, "%Y-%m")
    except (TypeError, ValueError) as exc:
        raise HTTPException(400, "Month must be YYYY-MM") from exc
    if parsed.strftime("%Y-%m") != value:
        raise HTTPException(400, "Month must be YYYY-MM")
    return value


def _staff(conn, staff_id: int):
    row = conn.execute("SELECT * FROM erp_staff WHERE id = ?", (staff_id,)).fetchone()
    if not row:
        raise HTTPException(404, "Staff member not found")
    return row


def _run(conn, run_id: int):
    row = conn.execute("SELECT * FROM erp_payroll_runs WHERE id = ?", (run_id,)).fetchone()
    if not row:
        raise HTTPException(404, "Payroll run not found")
    return row


def _staff_payload(row):
    result = dict(row)
    result["monthly_ctc"] = _to_rupees(result.pop("monthly_ctc_paise"))
    return result


def _payslip_payload(row):
    result = dict(row)
    for field in ("gross", "deductions", "net"):
        result[field] = _to_rupees(result.pop(f"{field}_paise"))
    return result


class StaffCreate(BaseModel):
    full_name: str = Field(min_length=1)
    role: str = ""
    department: str = ""
    phone: str = ""
    email: str = ""
    date_of_joining: str = ""
    monthly_ctc: float = Field(default=0, ge=0)
    status: str = "active"


class StaffUpdate(BaseModel):
    full_name: Optional[str] = Field(default=None, min_length=1)
    role: Optional[str] = None
    department: Optional[str] = None
    phone: Optional[str] = None
    email: Optional[str] = None
    date_of_joining: Optional[str] = None
    monthly_ctc: Optional[float] = Field(default=None, ge=0)
    status: Optional[str] = None


class PayrollCreate(BaseModel):
    month: str


class PayslipUpdate(BaseModel):
    gross: float = Field(ge=0)
    deductions: float = Field(ge=0)
    remarks: str = ""


@router.get("/staff")
async def list_staff(
    status: str = "",
    department: str = "",
    search: str = "",
    page: int = Query(default=1, ge=1),
    limit: int = Query(default=50, ge=1, le=200),
    user=Depends(require_admin),
):
    conn = get_db()
    try:
        clauses, params = [], []
        if status.strip():
            clauses.append("status = ?")
            params.append(_status(status))
        if department.strip():
            clauses.append("department = ?")
            params.append(department.strip())
        if search.strip():
            term = f"%{search.strip()}%"
            clauses.append("(full_name LIKE ? OR employee_code LIKE ? OR phone LIKE ?)")
            params.extend([term, term, term])
        where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
        offset = (page - 1) * limit
        rows = conn.execute(
            f"SELECT * FROM erp_staff {where} ORDER BY full_name LIMIT ? OFFSET ?",
            [*params, limit, offset],
        ).fetchall()
        total = conn.execute(
            f"SELECT COUNT(*) AS count FROM erp_staff {where}", params
        ).fetchone()["count"]
        return {"items": [_staff_payload(row) for row in rows], "total": total, "page": page, "limit": limit}
    finally:
        conn.close()


@router.get("/staff/summary")
async def staff_summary(user=Depends(require_admin)):
    conn = get_db()
    try:
        statuses = conn.execute(
            "SELECT status, COUNT(*) AS count FROM erp_staff GROUP BY status ORDER BY status"
        ).fetchall()
        departments = conn.execute(
            "SELECT department, COUNT(*) AS count FROM erp_staff GROUP BY department ORDER BY department"
        ).fetchall()
        total = conn.execute(
            "SELECT COALESCE(SUM(monthly_ctc_paise), 0) AS total FROM erp_staff WHERE status = 'active'"
        ).fetchone()["total"]
        return {
            "by_status": [dict(row) for row in statuses],
            "by_department": [dict(row) for row in departments],
            "total_monthly_ctc": _to_rupees(total),
        }
    finally:
        conn.close()


@router.get("/staff/{staff_id}")
async def get_staff(staff_id: int, user=Depends(require_admin)):
    conn = get_db()
    try:
        return _staff_payload(_staff(conn, staff_id))
    finally:
        conn.close()


@router.post("/staff", status_code=201)
async def create_staff(body: StaffCreate, user=Depends(require_admin)):
    status = _status(body.status)
    conn = get_db()
    try:
        now = _ist_now()
        code = f"EMP-{counter(conn, 'staff_employee'):06d}"
        cur = conn.execute(
            """INSERT INTO erp_staff
               (employee_code, full_name, role, department, phone, email, date_of_joining,
                monthly_ctc_paise, status, created_at, updated_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                code, body.full_name.strip(), body.role, body.department, body.phone,
                body.email, body.date_of_joining, _to_paise(body.monthly_ctc), status, now, now,
            ),
        )
        audit(conn, user["user_id"], "create", "staff", cur.lastrowid, body.model_dump())
        conn.commit()
        return _staff_payload(_staff(conn, cur.lastrowid))
    finally:
        conn.close()


@router.put("/staff/{staff_id}")
async def update_staff(staff_id: int, body: StaffUpdate, user=Depends(require_admin)):
    conn = get_db()
    try:
        _staff(conn, staff_id)
        values = body.model_dump(exclude_unset=True)
        if not values:
            return _staff_payload(_staff(conn, staff_id))
        if "status" in values:
            values["status"] = _status(values["status"])
        if "monthly_ctc" in values:
            values["monthly_ctc_paise"] = _to_paise(values.pop("monthly_ctc"))
        if "full_name" in values:
            values["full_name"] = values["full_name"].strip()
        assignments = ", ".join(f"{key} = ?" for key in values)
        now = _ist_now()
        conn.execute(
            f"UPDATE erp_staff SET {assignments}, updated_at = ? WHERE id = ?",
            [*values.values(), now, staff_id],
        )
        audit(conn, user["user_id"], "update", "staff", staff_id, values)
        conn.commit()
        return _staff_payload(_staff(conn, staff_id))
    finally:
        conn.close()


@router.get("/payroll")
async def list_payroll(user=Depends(require_admin)):
    conn = get_db()
    try:
        rows = conn.execute(
            """SELECT r.*, COUNT(p.id) AS payslip_count,
                      COALESCE(SUM(p.net_paise), 0) AS total_net_paise
               FROM erp_payroll_runs r
               LEFT JOIN erp_payslips p ON p.run_id = r.id
               GROUP BY r.id ORDER BY r.month DESC"""
        ).fetchall()
        result = []
        for row in rows:
            item = dict(row)
            item["total_net"] = _to_rupees(item.pop("total_net_paise"))
            result.append(item)
        return {"runs": result}
    finally:
        conn.close()


@router.post("/payroll", status_code=201)
async def create_payroll(body: PayrollCreate, user=Depends(require_admin)):
    month = _month(body.month)
    conn = get_db()
    try:
        existing = conn.execute(
            "SELECT * FROM erp_payroll_runs WHERE month = ?", (month,)
        ).fetchone()
        if existing:
            return dict(existing)
        now = _ist_now()
        cur = conn.execute(
            """INSERT INTO erp_payroll_runs(month, status, created_at, updated_at)
               VALUES (?, 'draft', ?, ?)""",
            (month, now, now),
        )
        audit(conn, user["user_id"], "create", "payroll", cur.lastrowid, {"month": month})
        conn.commit()
        return dict(_run(conn, cur.lastrowid))
    finally:
        conn.close()


@router.post("/payroll/{run_id}/generate")
async def generate_payroll(run_id: int, user=Depends(require_admin)):
    conn = get_db()
    try:
        run = _run(conn, run_id)
        if run["status"] != "draft":
            raise HTTPException(400, "Finalized payroll cannot be generated")
        now = _ist_now()
        staff_rows = conn.execute(
            """SELECT s.* FROM erp_staff s
               WHERE s.status = 'active'
                 AND NOT EXISTS (
                   SELECT 1 FROM erp_payslips p
                   WHERE p.run_id = ? AND p.staff_id = s.id
                 )""",
            (run_id,),
        ).fetchall()
        for staff in staff_rows:
            conn.execute(
                """INSERT INTO erp_payslips
                   (run_id, staff_id, gross_paise, deductions_paise, net_paise,
                    created_at, updated_at)
                   VALUES (?, ?, ?, 0, ?, ?, ?)""",
                (run_id, staff["id"], staff["monthly_ctc_paise"], staff["monthly_ctc_paise"], now, now),
            )
        audit(conn, user["user_id"], "generate", "payroll", run_id, {"created": len(staff_rows)})
        conn.commit()
        return {"created": len(staff_rows)}
    finally:
        conn.close()


@router.get("/payroll/{run_id}")
async def get_payroll(run_id: int, user=Depends(require_admin)):
    conn = get_db()
    try:
        run = dict(_run(conn, run_id))
        rows = conn.execute(
            """SELECT p.*, s.full_name, s.employee_code, s.department, s.role
               FROM erp_payslips p JOIN erp_staff s ON s.id = p.staff_id
               WHERE p.run_id = ? ORDER BY s.full_name""",
            (run_id,),
        ).fetchall()
        payslips = [_payslip_payload(row) for row in rows]
        run["payslips"] = payslips
        run["payslip_count"] = len(payslips)
        run["total_gross"] = round(sum(item["gross"] for item in payslips), 2)
        run["total_deductions"] = round(sum(item["deductions"] for item in payslips), 2)
        run["total_net"] = round(sum(item["net"] for item in payslips), 2)
        return run
    finally:
        conn.close()


@router.put("/payroll/payslips/{payslip_id}")
async def update_payslip(
    payslip_id: int,
    body: PayslipUpdate,
    user=Depends(require_admin),
):
    conn = get_db()
    try:
        row = conn.execute(
            """SELECT p.*, r.status AS run_status
               FROM erp_payslips p JOIN erp_payroll_runs r ON r.id = p.run_id
               WHERE p.id = ?""",
            (payslip_id,),
        ).fetchone()
        if not row:
            raise HTTPException(404, "Payslip not found")
        if row["run_status"] != "draft":
            raise HTTPException(400, "Finalized payroll cannot be edited")
        gross = _to_paise(body.gross)
        deductions = _to_paise(body.deductions)
        net = gross - deductions
        if net < 0:
            raise HTTPException(400, "Deductions cannot exceed gross")
        now = _ist_now()
        conn.execute(
            """UPDATE erp_payslips SET gross_paise = ?, deductions_paise = ?,
               net_paise = ?, remarks = ?, updated_at = ? WHERE id = ?""",
            (gross, deductions, net, body.remarks, now, payslip_id),
        )
        audit(conn, user["user_id"], "update", "payroll", row["run_id"], {"payslip_id": payslip_id})
        conn.commit()
        updated = conn.execute(
            """SELECT p.*, s.full_name, s.employee_code, s.department, s.role
               FROM erp_payslips p JOIN erp_staff s ON s.id = p.staff_id
               WHERE p.id = ?""",
            (payslip_id,),
        ).fetchone()
        return _payslip_payload(updated)
    finally:
        conn.close()


@router.post("/payroll/{run_id}/finalize")
async def finalize_payroll(run_id: int, user=Depends(require_admin)):
    conn = get_db()
    try:
        run = _run(conn, run_id)
        if run["status"] != "draft":
            raise HTTPException(400, "Payroll is already finalized")
        now = _ist_now()
        conn.execute(
            "UPDATE erp_payroll_runs SET status = 'finalized', finalized_at = ?, updated_at = ? WHERE id = ?",
            (now, now, run_id),
        )
        audit(conn, user["user_id"], "finalize", "payroll", run_id)
        conn.commit()
        return dict(_run(conn, run_id))
    finally:
        conn.close()
