"""Admin-only ERP inventory management."""

import json
import sqlite3
from decimal import Decimal, ROUND_HALF_UP
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field

from app.database import _ist_now, get_db
from app.routes.auth import require_admin
from app.routes.erp_fees import counter

router = APIRouter()
STATUSES = {"active", "inactive"}
TXN_TYPES = {"in", "out", "adjust"}


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
    if value not in STATUSES:
        raise HTTPException(400, f"Invalid inventory status: {value}")
    return value


def _item(conn, item_id: int):
    row = conn.execute(
        "SELECT i.*, c.name AS category_name FROM erp_inventory_items i "
        "LEFT JOIN erp_inventory_categories c ON c.id = i.category_id WHERE i.id = ?",
        (item_id,),
    ).fetchone()
    if not row:
        raise HTTPException(404, "Inventory item not found")
    return row


def _category(conn, category_id: int):
    row = conn.execute(
        "SELECT * FROM erp_inventory_categories WHERE id = ?", (category_id,)
    ).fetchone()
    if not row:
        raise HTTPException(404, "Inventory category not found")
    return row


def _item_payload(row):
    result = dict(row)
    result["unit_cost"] = _to_rupees(result.pop("unit_cost_paise"))
    return result


def _transaction_payload(row):
    return dict(row)


class CategoryCreate(BaseModel):
    name: str = Field(min_length=1)


class ItemCreate(BaseModel):
    category_id: Optional[int] = None
    name: str = Field(min_length=1)
    unit: str = "unit"
    reorder_level: int = Field(default=0, ge=0)
    unit_cost: float = Field(default=0, ge=0)
    location: str = ""
    status: str = "active"


class ItemUpdate(BaseModel):
    category_id: Optional[int] = None
    name: Optional[str] = Field(default=None, min_length=1)
    unit: Optional[str] = None
    reorder_level: Optional[int] = Field(default=None, ge=0)
    unit_cost: Optional[float] = Field(default=None, ge=0)
    location: Optional[str] = None
    status: Optional[str] = None


class TransactionCreate(BaseModel):
    txn_type: str
    quantity: Optional[int] = Field(default=None, ge=1)
    new_quantity: Optional[int] = Field(default=None, ge=0)
    note: str = ""


@router.get("/inventory/categories")
async def list_categories(user=Depends(require_admin)):
    conn = get_db()
    try:
        rows = conn.execute(
            """SELECT c.*, COUNT(i.id) AS item_count
               FROM erp_inventory_categories c
               LEFT JOIN erp_inventory_items i ON i.category_id = c.id
               GROUP BY c.id ORDER BY lower(c.name)"""
        ).fetchall()
        return {"categories": [dict(row) for row in rows]}
    finally:
        conn.close()


@router.post("/inventory/categories", status_code=201)
async def create_category(body: CategoryCreate, user=Depends(require_admin)):
    name = body.name.strip()
    conn = get_db()
    try:
        if conn.execute(
            "SELECT id FROM erp_inventory_categories WHERE lower(name) = lower(?)",
            (name,),
        ).fetchone():
            raise HTTPException(409, "Inventory category already exists")
        now = _ist_now()
        try:
            cur = conn.execute(
                "INSERT INTO erp_inventory_categories(name, created_at, updated_at) VALUES (?, ?, ?)",
                (name, now, now),
            )
        except sqlite3.IntegrityError as exc:
            raise HTTPException(409, "Inventory category already exists") from exc
        audit(conn, user["user_id"], "create", "inventory_category", cur.lastrowid, {"name": name})
        conn.commit()
        return dict(conn.execute(
            "SELECT * FROM erp_inventory_categories WHERE id = ?", (cur.lastrowid,)
        ).fetchone())
    finally:
        conn.close()


@router.get("/inventory/items")
async def list_items(
    category_id: Optional[int] = None,
    status: str = "",
    search: str = "",
    low_stock: bool = False,
    page: int = Query(default=1, ge=1),
    limit: int = Query(default=50, ge=1, le=200),
    user=Depends(require_admin),
):
    conn = get_db()
    try:
        clauses, params = [], []
        if category_id is not None:
            clauses.append("i.category_id = ?")
            params.append(category_id)
        if status.strip():
            clauses.append("i.status = ?")
            params.append(_status(status))
        if search.strip():
            term = f"%{search.strip()}%"
            clauses.append("(i.name LIKE ? OR i.sku LIKE ?)")
            params.extend([term, term])
        if low_stock:
            clauses.append("i.quantity <= i.reorder_level")
        where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
        offset = (page - 1) * limit
        rows = conn.execute(
            f"""SELECT i.*, c.name AS category_name
                FROM erp_inventory_items i
                LEFT JOIN erp_inventory_categories c ON c.id = i.category_id
                {where} ORDER BY i.name LIMIT ? OFFSET ?""",
            [*params, limit, offset],
        ).fetchall()
        total = conn.execute(
            f"SELECT COUNT(*) AS count FROM erp_inventory_items i {where}", params
        ).fetchone()["count"]
        return {
            "items": [_item_payload(row) for row in rows],
            "total": total,
            "page": page,
            "limit": limit,
        }
    finally:
        conn.close()


@router.get("/inventory/items/{item_id}")
async def get_item(item_id: int, user=Depends(require_admin)):
    conn = get_db()
    try:
        result = _item_payload(_item(conn, item_id))
        result["transactions"] = [
            _transaction_payload(row)
            for row in conn.execute(
                """SELECT t.*, u.name AS created_by_name
                   FROM erp_inventory_transactions t
                   LEFT JOIN users u ON u.id = t.created_by
                   WHERE t.item_id = ? ORDER BY t.id DESC LIMIT 50""",
                (item_id,),
            ).fetchall()
        ]
        return result
    finally:
        conn.close()


@router.post("/inventory/items", status_code=201)
async def create_item(body: ItemCreate, user=Depends(require_admin)):
    status = _status(body.status)
    conn = get_db()
    try:
        if body.category_id is not None:
            _category(conn, body.category_id)
        now = _ist_now()
        sku = f"ITM-{counter(conn, 'inventory_item'):06d}"
        cur = conn.execute(
            """INSERT INTO erp_inventory_items
               (category_id, sku, name, unit, quantity, reorder_level, unit_cost_paise,
                location, status, created_at, updated_at)
               VALUES (?, ?, ?, ?, 0, ?, ?, ?, ?, ?, ?)""",
            (
                body.category_id, sku, body.name.strip(), body.unit, body.reorder_level,
                _to_paise(body.unit_cost), body.location, status, now, now,
            ),
        )
        audit(conn, user["user_id"], "create", "inventory_item", cur.lastrowid, body.model_dump())
        conn.commit()
        return _item_payload(_item(conn, cur.lastrowid))
    finally:
        conn.close()


@router.put("/inventory/items/{item_id}")
async def update_item(item_id: int, body: ItemUpdate, user=Depends(require_admin)):
    conn = get_db()
    try:
        _item(conn, item_id)
        values = body.model_dump(exclude_unset=True)
        if not values:
            return _item_payload(_item(conn, item_id))
        if "category_id" in values and values["category_id"] is not None:
            _category(conn, values["category_id"])
        if "status" in values:
            values["status"] = _status(values["status"])
        if "unit_cost" in values:
            values["unit_cost_paise"] = _to_paise(values.pop("unit_cost"))
        if "name" in values:
            values["name"] = values["name"].strip()
        assignments = ", ".join(f"{key} = ?" for key in values)
        now = _ist_now()
        conn.execute(
            f"UPDATE erp_inventory_items SET {assignments}, updated_at = ? WHERE id = ?",
            [*values.values(), now, item_id],
        )
        audit(conn, user["user_id"], "update", "inventory_item", item_id, values)
        conn.commit()
        return _item_payload(_item(conn, item_id))
    finally:
        conn.close()


@router.post("/inventory/items/{item_id}/transaction")
async def create_transaction(item_id: int, body: TransactionCreate, user=Depends(require_admin)):
    txn_type = body.txn_type.strip().lower()
    if txn_type not in TXN_TYPES:
        raise HTTPException(400, f"Invalid transaction type: {txn_type}")
    conn = get_db()
    try:
        item = _item(conn, item_id)
        current = item["quantity"]
        if txn_type == "adjust":
            if body.new_quantity is None:
                raise HTTPException(400, "new_quantity is required for adjust")
            delta = body.new_quantity - current
            new_quantity = body.new_quantity
        else:
            if body.quantity is None:
                raise HTTPException(400, "quantity is required for in/out")
            delta = body.quantity if txn_type == "in" else -body.quantity
            new_quantity = current + delta
            if new_quantity < 0:
                raise HTTPException(400, "Stock cannot become negative")
        now = _ist_now()
        cur = conn.execute(
            """INSERT INTO erp_inventory_transactions
               (item_id, txn_type, quantity, note, created_by, created_at)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (item_id, txn_type, delta, body.note, user["user_id"], now),
        )
        conn.execute(
            "UPDATE erp_inventory_items SET quantity = ?, updated_at = ? WHERE id = ?",
            (new_quantity, now, item_id),
        )
        audit(
            conn, user["user_id"], "create", "inventory_txn", cur.lastrowid,
            {"item_id": item_id, "txn_type": txn_type, "quantity": delta},
        )
        conn.commit()
        result = _item_payload(_item(conn, item_id))
        result["transaction"] = dict(conn.execute(
            "SELECT * FROM erp_inventory_transactions WHERE id = ?", (cur.lastrowid,)
        ).fetchone())
        return result
    finally:
        conn.close()


@router.get("/inventory/summary")
async def inventory_summary(user=Depends(require_admin)):
    conn = get_db()
    try:
        totals = conn.execute(
            """SELECT COUNT(*) AS items,
                      COALESCE(SUM(quantity * unit_cost_paise), 0) AS stock_value_paise,
                      COALESCE(SUM(quantity <= reorder_level), 0) AS low_stock
               FROM erp_inventory_items"""
        ).fetchone()
        categories = conn.execute(
            """SELECT COALESCE(c.name, 'Uncategorized') AS category,
                      COUNT(i.id) AS item_count,
                      COALESCE(SUM(i.quantity), 0) AS quantity
               FROM erp_inventory_items i
               LEFT JOIN erp_inventory_categories c ON c.id = i.category_id
               GROUP BY c.id ORDER BY category"""
        ).fetchall()
        return {
            "total_items": totals["items"],
            "total_stock_value": _to_rupees(totals["stock_value_paise"]),
            "low_stock_count": totals["low_stock"],
            "by_category": [dict(row) for row in categories],
        }
    finally:
        conn.close()
