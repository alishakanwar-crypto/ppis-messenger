"""Admin-only ERP transport routes, stops, and assignments."""

import json
from decimal import Decimal, ROUND_HALF_UP
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from app.database import _ist_now, get_db
from app.routes.auth import require_admin

router = APIRouter()
ROUTE_STATUSES = {"active", "inactive"}
ASSIGNMENT_STATUSES = {"active", "inactive"}


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


def _route_status(value: str) -> str:
    value = value.strip().lower()
    if value not in ROUTE_STATUSES:
        raise HTTPException(400, f"Invalid route status: {value}")
    return value


def _assignment_status(value: str) -> str:
    value = value.strip().lower()
    if value not in ASSIGNMENT_STATUSES:
        raise HTTPException(400, f"Invalid assignment status: {value}")
    return value


def _route(conn, route_id: int):
    row = conn.execute(
        "SELECT * FROM erp_transport_routes WHERE id = ?", (route_id,)
    ).fetchone()
    if not row:
        raise HTTPException(404, "Transport route not found")
    return row


def _stop(conn, stop_id: int):
    row = conn.execute(
        "SELECT * FROM erp_transport_stops WHERE id = ?", (stop_id,)
    ).fetchone()
    if not row:
        raise HTTPException(404, "Transport stop not found")
    return row


def _route_payload(row):
    result = dict(row)
    return result


def _stop_payload(row):
    result = dict(row)
    result["monthly_fee"] = _to_rupees(result.pop("monthly_fee_paise"))
    return result


class RouteCreate(BaseModel):
    name: str = Field(min_length=1)
    vehicle_number: str = ""
    driver_name: str = ""
    driver_phone: str = ""
    capacity: int = Field(default=0, ge=0)
    status: str = "active"


class RouteUpdate(BaseModel):
    name: Optional[str] = Field(default=None, min_length=1)
    vehicle_number: Optional[str] = None
    driver_name: Optional[str] = None
    driver_phone: Optional[str] = None
    capacity: Optional[int] = Field(default=None, ge=0)
    status: Optional[str] = None


class StopCreate(BaseModel):
    name: str = Field(min_length=1)
    stop_order: int = 0
    pickup_time: str = ""
    drop_time: str = ""
    monthly_fee: float = Field(default=0, ge=0)


class StopUpdate(BaseModel):
    name: Optional[str] = Field(default=None, min_length=1)
    stop_order: Optional[int] = None
    pickup_time: Optional[str] = None
    drop_time: Optional[str] = None
    monthly_fee: Optional[float] = Field(default=None, ge=0)


class AssignmentCreate(BaseModel):
    student_id: int
    route_id: int
    stop_id: Optional[int] = None
    start_date: str = ""


@router.get("/transport/routes")
async def list_routes(status: str = "", user=Depends(require_admin)):
    conn = get_db()
    try:
        clauses, params = [], []
        if status.strip():
            clauses.append("r.status = ?")
            params.append(_route_status(status))
        where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
        rows = conn.execute(
            f"""SELECT r.*, COUNT(DISTINCT s.id) AS stop_count,
                       COUNT(DISTINCT CASE WHEN a.status = 'active' THEN a.student_id END)
                         AS assigned_student_count
                FROM erp_transport_routes r
                LEFT JOIN erp_transport_stops s ON s.route_id = r.id
                LEFT JOIN erp_transport_assignments a ON a.route_id = r.id
                {where}
                GROUP BY r.id ORDER BY r.name""",
            params,
        ).fetchall()
        return {"routes": [_route_payload(row) for row in rows]}
    finally:
        conn.close()


@router.post("/transport/routes", status_code=201)
async def create_route(body: RouteCreate, user=Depends(require_admin)):
    status = _route_status(body.status)
    conn = get_db()
    try:
        now = _ist_now()
        cur = conn.execute(
            """INSERT INTO erp_transport_routes
               (name, vehicle_number, driver_name, driver_phone, capacity, status, created_at, updated_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                body.name.strip(), body.vehicle_number, body.driver_name, body.driver_phone,
                body.capacity, status, now, now,
            ),
        )
        audit(conn, user["user_id"], "create", "transport_route", cur.lastrowid, body.model_dump())
        conn.commit()
        return _route_payload(_route(conn, cur.lastrowid))
    finally:
        conn.close()


@router.get("/transport/routes/{route_id}")
async def get_route(route_id: int, user=Depends(require_admin)):
    conn = get_db()
    try:
        route = _route_payload(_route(conn, route_id))
        route["stops"] = [
            _stop_payload(row)
            for row in conn.execute(
                "SELECT * FROM erp_transport_stops WHERE route_id = ? ORDER BY stop_order, id",
                (route_id,),
            ).fetchall()
        ]
        route["assigned_students"] = [
            dict(row)
            for row in conn.execute(
                """SELECT a.id AS assignment_id, a.start_date, a.status,
                          s.id AS student_id, s.full_name, s.grade,
                          st.name AS stop_name
                   FROM erp_transport_assignments a
                   JOIN erp_students s ON s.id = a.student_id
                   LEFT JOIN erp_transport_stops st ON st.id = a.stop_id
                   WHERE a.route_id = ? AND a.status = 'active'
                   ORDER BY s.full_name""",
                (route_id,),
            ).fetchall()
        ]
        return route
    finally:
        conn.close()


@router.put("/transport/routes/{route_id}")
async def update_route(route_id: int, body: RouteUpdate, user=Depends(require_admin)):
    conn = get_db()
    try:
        _route(conn, route_id)
        values = body.model_dump(exclude_unset=True)
        if not values:
            return _route_payload(_route(conn, route_id))
        if "status" in values:
            values["status"] = _route_status(values["status"])
        if "name" in values:
            values["name"] = values["name"].strip()
        assignments = ", ".join(f"{key} = ?" for key in values)
        now = _ist_now()
        conn.execute(
            f"UPDATE erp_transport_routes SET {assignments}, updated_at = ? WHERE id = ?",
            [*values.values(), now, route_id],
        )
        audit(conn, user["user_id"], "update", "transport_route", route_id, values)
        conn.commit()
        return _route_payload(_route(conn, route_id))
    finally:
        conn.close()


@router.post("/transport/routes/{route_id}/stops", status_code=201)
async def add_stop(route_id: int, body: StopCreate, user=Depends(require_admin)):
    _to_paise(body.monthly_fee)
    conn = get_db()
    try:
        _route(conn, route_id)
        now = _ist_now()
        cur = conn.execute(
            """INSERT INTO erp_transport_stops
               (route_id, name, stop_order, pickup_time, drop_time, monthly_fee_paise, created_at, updated_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                route_id, body.name.strip(), body.stop_order, body.pickup_time, body.drop_time,
                _to_paise(body.monthly_fee), now, now,
            ),
        )
        audit(conn, user["user_id"], "create", "transport_stop", cur.lastrowid, body.model_dump())
        conn.commit()
        return _stop_payload(_stop(conn, cur.lastrowid))
    finally:
        conn.close()


@router.put("/transport/stops/{stop_id}")
async def update_stop(stop_id: int, body: StopUpdate, user=Depends(require_admin)):
    conn = get_db()
    try:
        _stop(conn, stop_id)
        values = body.model_dump(exclude_unset=True)
        if not values:
            return _stop_payload(_stop(conn, stop_id))
        if "monthly_fee" in values:
            values["monthly_fee_paise"] = _to_paise(values.pop("monthly_fee"))
        if "name" in values:
            values["name"] = values["name"].strip()
        assignments = ", ".join(f"{key} = ?" for key in values)
        now = _ist_now()
        conn.execute(
            f"UPDATE erp_transport_stops SET {assignments}, updated_at = ? WHERE id = ?",
            [*values.values(), now, stop_id],
        )
        audit(conn, user["user_id"], "update", "transport_stop", stop_id, values)
        conn.commit()
        return _stop_payload(_stop(conn, stop_id))
    finally:
        conn.close()


@router.delete("/transport/stops/{stop_id}")
async def delete_stop(stop_id: int, user=Depends(require_admin)):
    conn = get_db()
    try:
        _stop(conn, stop_id)
        if conn.execute(
            """SELECT 1 FROM erp_transport_assignments
               WHERE stop_id = ? AND status = 'active' LIMIT 1""",
            (stop_id,),
        ).fetchone():
            raise HTTPException(400, "Cannot delete a stop with active assignments")
        conn.execute("DELETE FROM erp_transport_stops WHERE id = ?", (stop_id,))
        audit(conn, user["user_id"], "delete", "transport_stop", stop_id)
        conn.commit()
        return {"ok": True}
    finally:
        conn.close()


@router.get("/transport/assignments")
async def list_assignments(
    route_id: Optional[int] = None,
    status: str = "",
    search: str = "",
    user=Depends(require_admin),
):
    conn = get_db()
    try:
        clauses, params = [], []
        if route_id is not None:
            clauses.append("a.route_id = ?")
            params.append(route_id)
        if status.strip():
            clauses.append("a.status = ?")
            params.append(_assignment_status(status))
        if search.strip():
            term = f"%{search.strip()}%"
            clauses.append("(s.full_name LIKE ? OR s.admission_number LIKE ? OR r.name LIKE ?)")
            params.extend([term, term, term])
        where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
        rows = conn.execute(
            f"""SELECT a.*, s.full_name, s.grade, s.admission_number,
                       r.name AS route_name, st.name AS stop_name,
                       st.monthly_fee_paise
                FROM erp_transport_assignments a
                JOIN erp_students s ON s.id = a.student_id
                JOIN erp_transport_routes r ON r.id = a.route_id
                LEFT JOIN erp_transport_stops st ON st.id = a.stop_id
                {where} ORDER BY a.status, s.full_name""",
            params,
        ).fetchall()
        result = []
        for row in rows:
            item = dict(row)
            item["monthly_fee"] = _to_rupees(item.pop("monthly_fee_paise") or 0)
            result.append(item)
        return {"assignments": result}
    finally:
        conn.close()


@router.post("/transport/assignments", status_code=201)
async def create_assignment(body: AssignmentCreate, user=Depends(require_admin)):
    conn = get_db()
    try:
        student = conn.execute(
            "SELECT id FROM erp_students WHERE id = ?", (body.student_id,)
        ).fetchone()
        if not student:
            raise HTTPException(404, "Student not found")
        _route(conn, body.route_id)
        if body.stop_id is not None and not conn.execute(
            "SELECT id FROM erp_transport_stops WHERE id = ? AND route_id = ?",
            (body.stop_id, body.route_id),
        ).fetchone():
            raise HTTPException(400, "Stop does not belong to this route")
        if conn.execute(
            """SELECT id FROM erp_transport_assignments
               WHERE student_id = ? AND status = 'active'""",
            (body.student_id,),
        ).fetchone():
            raise HTTPException(400, "Student already has an active transport assignment")
        now = _ist_now()
        cur = conn.execute(
            """INSERT INTO erp_transport_assignments
               (student_id, route_id, stop_id, start_date, status, created_at, updated_at)
               VALUES (?, ?, ?, ?, 'active', ?, ?)""",
            (body.student_id, body.route_id, body.stop_id, body.start_date, now, now),
        )
        audit(conn, user["user_id"], "create", "transport_assignment", cur.lastrowid, body.model_dump())
        conn.commit()
        return dict(conn.execute(
            "SELECT * FROM erp_transport_assignments WHERE id = ?", (cur.lastrowid,)
        ).fetchone())
    finally:
        conn.close()


@router.post("/transport/assignments/{assignment_id}/end")
async def end_assignment(assignment_id: int, user=Depends(require_admin)):
    conn = get_db()
    try:
        row = conn.execute(
            "SELECT * FROM erp_transport_assignments WHERE id = ?", (assignment_id,)
        ).fetchone()
        if not row:
            raise HTTPException(404, "Transport assignment not found")
        now = _ist_now()
        conn.execute(
            "UPDATE erp_transport_assignments SET status = 'inactive', updated_at = ? WHERE id = ?",
            (now, assignment_id),
        )
        audit(conn, user["user_id"], "end", "transport_assignment", assignment_id)
        conn.commit()
        return dict(conn.execute(
            "SELECT * FROM erp_transport_assignments WHERE id = ?", (assignment_id,)
        ).fetchone())
    finally:
        conn.close()


@router.get("/transport/summary")
async def transport_summary(user=Depends(require_admin)):
    conn = get_db()
    try:
        routes = conn.execute(
            "SELECT COUNT(*) AS count FROM erp_transport_routes WHERE status = 'active'"
        ).fetchone()["count"]
        capacity = conn.execute(
            "SELECT COALESCE(SUM(capacity), 0) AS total FROM erp_transport_routes WHERE status = 'active'"
        ).fetchone()["total"]
        assigned = conn.execute(
            "SELECT COUNT(*) AS count FROM erp_transport_assignments WHERE status = 'active'"
        ).fetchone()["count"]
        fee = conn.execute(
            """SELECT COALESCE(SUM(st.monthly_fee_paise), 0) AS total
               FROM erp_transport_assignments a
               JOIN erp_transport_stops st ON st.id = a.stop_id
               WHERE a.status = 'active'"""
        ).fetchone()["total"]
        return {
            "active_routes": routes,
            "total_capacity": capacity,
            "total_assigned_students": assigned,
            "total_monthly_transport_fee": _to_rupees(fee),
        }
    finally:
        conn.close()
