"""Admin-only ERP fees and payments."""
# ruff: noqa: E701, E702
import json
import sqlite3
from datetime import date, timedelta
from typing import Optional

from fastapi import APIRouter, Depends, Header, HTTPException, Query
from pydantic import BaseModel, Field

from app.database import _ist_now, get_db
from app.routes.auth import require_admin

router = APIRouter()


def audit(conn, user_id, action, entity_type, entity_id, details=None):
    conn.execute("INSERT INTO erp_audit_log(actor_user_id,action,entity_type,entity_id,details,created_at) VALUES (?,?,?,?,?,?)",
                 (user_id, action, entity_type, entity_id, json.dumps(details or {}), _ist_now()))


def counter(conn, scope):
    row = conn.execute("SELECT next_value FROM erp_document_counters WHERE scope=?", (scope,)).fetchone()
    if row is None:
        conn.execute("INSERT INTO erp_document_counters(scope,next_value) VALUES (?,2)", (scope,))
        return 1
    conn.execute("UPDATE erp_document_counters SET next_value=next_value+1 WHERE scope=?", (scope,))
    return row["next_value"]


def session_row(conn, session_id):
    row = conn.execute("SELECT * FROM erp_academic_sessions WHERE id=?", (session_id,)).fetchone()
    if not row:
        raise HTTPException(404, "Academic session not found")
    return row


class SessionIn(BaseModel):
    name: str
    start_date: str
    end_date: str


class HeadIn(BaseModel):
    code: str
    name: str
    is_refundable: bool = False
    is_active: bool = True


class StructureItem(BaseModel):
    fee_head_id: int
    amount_paise: int = Field(ge=0)
    is_optional: bool = False


class StructureIn(BaseModel):
    session_id: int
    grade: str
    frequency: str
    items: list[StructureItem]


class PlanIn(BaseModel):
    session_id: int
    structure_id: int
    transport_opted: bool = False


class ConcessionIn(BaseModel):
    student_id: int
    session_id: int
    fee_head_id: Optional[int] = None
    kind: str
    value: int = Field(ge=0)
    reason: str


class GenerateIn(BaseModel):
    session_id: int
    period_code: str
    grade: Optional[str] = None
    student_ids: Optional[list[int]] = None
    dry_run: bool = False


class CancelIn(BaseModel):
    reason: str = Field(min_length=1)


class PaymentAllocation(BaseModel):
    invoice_id: int
    amount_paise: int = Field(gt=0)


class PaymentIn(BaseModel):
    student_id: int
    session_id: int
    amount_paise: int = Field(gt=0)
    method: str
    paid_at: Optional[str] = None
    reference_last4: str = ""
    bank_label: str = ""
    allocations: list[PaymentAllocation] = []


class ReverseIn(BaseModel):
    reason: str = Field(min_length=1)


@router.get("/sessions")
async def sessions(user=Depends(require_admin)):
    conn = get_db()
    try:
        return {"sessions": [dict(x) for x in conn.execute("SELECT * FROM erp_academic_sessions ORDER BY start_date DESC")]}
    finally: conn.close()


@router.post("/sessions", status_code=201)
async def create_session(body: SessionIn, user=Depends(require_admin)):
    conn = get_db()
    try:
        try:
            cur = conn.execute("INSERT INTO erp_academic_sessions(name,start_date,end_date,created_at,updated_at) VALUES (?,?,?,?,?)",
                               (body.name, body.start_date, body.end_date, _ist_now(), _ist_now()))
        except sqlite3.IntegrityError:
            raise HTTPException(409, "Session already exists")
        audit(conn, user["user_id"], "create", "academic_session", cur.lastrowid, body.model_dump())
        conn.commit()
        return dict(conn.execute("SELECT * FROM erp_academic_sessions WHERE id=?", (cur.lastrowid,)).fetchone())
    finally: conn.close()


@router.post("/sessions/{session_id}/set-current")
async def set_current(session_id: int, user=Depends(require_admin)):
    conn = get_db()
    try:
        session_row(conn, session_id)
        conn.execute("UPDATE erp_academic_sessions SET is_current=0,updated_at=?", (_ist_now(),))
        conn.execute("UPDATE erp_academic_sessions SET is_current=1,updated_at=? WHERE id=?", (_ist_now(), session_id))
        audit(conn, user["user_id"], "set_current", "academic_session", session_id)
        conn.commit()
        return {"ok": True}
    finally: conn.close()


@router.get("/fee-heads")
async def heads(user=Depends(require_admin)):
    conn = get_db()
    try: return {"fee_heads": [dict(x) for x in conn.execute("SELECT * FROM erp_fee_heads ORDER BY name")]}
    finally: conn.close()


@router.post("/fee-heads", status_code=201)
async def create_head(body: HeadIn, user=Depends(require_admin)):
    conn = get_db()
    try:
        try:
            cur = conn.execute("INSERT INTO erp_fee_heads(code,name,is_refundable,is_active) VALUES(?,?,?,?)",
                               (body.code.strip().upper(), body.name.strip(), int(body.is_refundable), int(body.is_active)))
        except sqlite3.IntegrityError: raise HTTPException(409, "Fee head code already exists")
        audit(conn,user["user_id"],"create","fee_head",cur.lastrowid,body.model_dump()); conn.commit()
        return dict(conn.execute("SELECT * FROM erp_fee_heads WHERE id=?", (cur.lastrowid,)).fetchone())
    finally: conn.close()


@router.put("/fee-heads/{head_id}")
async def update_head(head_id: int, body: HeadIn, user=Depends(require_admin)):
    conn = get_db()
    try:
        if not conn.execute("SELECT id FROM erp_fee_heads WHERE id=?", (head_id,)).fetchone(): raise HTTPException(404,"Fee head not found")
        conn.execute("UPDATE erp_fee_heads SET code=?,name=?,is_refundable=?,is_active=? WHERE id=?", (body.code.upper(),body.name,int(body.is_refundable),int(body.is_active),head_id))
        audit(conn,user["user_id"],"update","fee_head",head_id,body.model_dump()); conn.commit()
        return dict(conn.execute("SELECT * FROM erp_fee_heads WHERE id=?", (head_id,)).fetchone())
    finally: conn.close()


def structure_json(conn, sid):
    row = conn.execute("SELECT * FROM erp_fee_structures WHERE id=?", (sid,)).fetchone()
    if not row: raise HTTPException(404, "Fee structure not found")
    result = dict(row); result["items"] = [dict(x) for x in conn.execute("SELECT i.*,h.code,h.name FROM erp_fee_structure_items i JOIN erp_fee_heads h ON h.id=i.fee_head_id WHERE structure_id=?", (sid,))]
    return result


@router.get("/fee-structures")
async def structures(session_id: Optional[int] = None, grade: str = "", user=Depends(require_admin)):
    conn = get_db()
    try:
        clauses, params = [], []
        if session_id: clauses.append("session_id=?"); params.append(session_id)
        if grade: clauses.append("grade=?"); params.append(grade)
        rows = conn.execute("SELECT id FROM erp_fee_structures"+((" WHERE "+" AND ".join(clauses)) if clauses else ""),params).fetchall()
        return {"fee_structures": [structure_json(conn,x["id"]) for x in rows]}
    finally: conn.close()


@router.post("/fee-structures", status_code=201)
async def create_structure(body: StructureIn, user=Depends(require_admin)):
    if body.frequency not in {"monthly","quarterly","annual","one_time"}: raise HTTPException(400,"Invalid frequency")
    conn = get_db()
    try:
        session_row(conn,body.session_id)
        try:
            cur=conn.execute("INSERT INTO erp_fee_structures(session_id,grade,frequency,created_at,updated_at) VALUES(?,?,?,?,?)",(body.session_id,body.grade,_norm(body.frequency),_ist_now(),_ist_now()))
            for item in body.items: conn.execute("INSERT INTO erp_fee_structure_items(structure_id,fee_head_id,amount_paise,is_optional) VALUES(?,?,?,?)",(cur.lastrowid,item.fee_head_id,item.amount_paise,int(item.is_optional)))
        except sqlite3.IntegrityError: conn.rollback(); raise HTTPException(409,"Structure already exists or item is invalid")
        audit(conn,user["user_id"],"create","fee_structure",cur.lastrowid,body.model_dump()); conn.commit(); return structure_json(conn,cur.lastrowid)
    finally: conn.close()


def _norm(value): return value


@router.put("/fee-structures/{structure_id}")
async def update_structure(structure_id: int, body: StructureIn, user=Depends(require_admin)):
    conn=get_db()
    try:
        row=conn.execute("SELECT status FROM erp_fee_structures WHERE id=?",(structure_id,)).fetchone()
        if not row: raise HTTPException(404,"Fee structure not found")
        if row["status"] != "draft": raise HTTPException(409,"Published structures are immutable")
        conn.execute("UPDATE erp_fee_structures SET session_id=?,grade=?,frequency=?,updated_at=? WHERE id=?",(body.session_id,body.grade,body.frequency,_ist_now(),structure_id))
        conn.execute("DELETE FROM erp_fee_structure_items WHERE structure_id=?",(structure_id,))
        for item in body.items: conn.execute("INSERT INTO erp_fee_structure_items(structure_id,fee_head_id,amount_paise,is_optional) VALUES(?,?,?,?)",(structure_id,item.fee_head_id,item.amount_paise,int(item.is_optional)))
        audit(conn,user["user_id"],"update","fee_structure",structure_id,body.model_dump()); conn.commit(); return structure_json(conn,structure_id)
    finally: conn.close()


@router.post("/fee-structures/{structure_id}/publish")
async def publish_structure(structure_id:int,user=Depends(require_admin)):
    conn=get_db()
    try:
        row=conn.execute("SELECT status FROM erp_fee_structures WHERE id=?",(structure_id,)).fetchone()
        if not row: raise HTTPException(404,"Fee structure not found")
        if row["status"] != "draft": raise HTTPException(409,"Structure is not draft")
        conn.execute("UPDATE erp_fee_structures SET status='published',published_at=?,updated_at=? WHERE id=?",( _ist_now(),_ist_now(),structure_id))
        audit(conn,user["user_id"],"publish","fee_structure",structure_id); conn.commit(); return structure_json(conn,structure_id)
    finally: conn.close()


@router.post("/students/{student_id}/fee-plan")
async def plan(student_id:int,body:PlanIn,user=Depends(require_admin)):
    conn=get_db()
    try:
        if not conn.execute("SELECT id FROM erp_students WHERE id=?",(student_id,)).fetchone(): raise HTTPException(404,"Student not found")
        conn.execute("INSERT INTO erp_student_fee_plans(student_id,session_id,structure_id,transport_opted) VALUES(?,?,?,?) ON CONFLICT(student_id,session_id) DO UPDATE SET structure_id=excluded.structure_id,transport_opted=excluded.transport_opted",(student_id,body.session_id,body.structure_id,int(body.transport_opted)))
        row=conn.execute("SELECT * FROM erp_student_fee_plans WHERE student_id=? AND session_id=?",(student_id,body.session_id)).fetchone()
        audit(conn,user["user_id"],"upsert","fee_plan",row["id"],body.model_dump()); conn.commit(); return dict(row)
    finally: conn.close()


@router.post("/concessions",status_code=201)
async def concession(body:ConcessionIn,user=Depends(require_admin)):
    if body.kind not in {"percent","amount"} or (body.kind=="percent" and body.value>10000): raise HTTPException(400,"Invalid concession")
    conn=get_db()
    try:
        cur=conn.execute("INSERT INTO erp_concessions(student_id,session_id,fee_head_id,kind,value,reason,approved_by_user_id,created_at,updated_at) VALUES(?,?,?,?,?,?,?,?,?)",(body.student_id,body.session_id,body.fee_head_id,body.kind,body.value,body.reason,user["user_id"],_ist_now(),_ist_now()))
        audit(conn,user["user_id"],"create","concession",cur.lastrowid,body.model_dump()); conn.commit(); return dict(conn.execute("SELECT * FROM erp_concessions WHERE id=?",(cur.lastrowid,)).fetchone())
    finally: conn.close()


@router.post("/concessions/{concession_id}/revoke")
async def revoke(concession_id:int,user=Depends(require_admin)):
    conn=get_db()
    try:
        cur=conn.execute("UPDATE erp_concessions SET status='revoked',updated_at=? WHERE id=? AND status='active'",(_ist_now(),concession_id))
        if not cur.rowcount: raise HTTPException(404,"Active concession not found")
        audit(conn,user["user_id"],"revoke","concession",concession_id); conn.commit(); return {"ok":True}
    finally: conn.close()


def invoice_payload(conn, iid):
    row=conn.execute("SELECT i.*,s.full_name,s.grade FROM erp_invoices i JOIN erp_students s ON s.id=i.student_id WHERE i.id=?",(iid,)).fetchone()
    if not row: raise HTTPException(404,"Invoice not found")
    result=dict(row); result["lines"]=[dict(x) for x in conn.execute("SELECT * FROM erp_invoice_lines WHERE invoice_id=?",(iid,))]
    result["allocations"]=[dict(x) for x in conn.execute("SELECT a.*,p.receipt_number,p.status FROM erp_payment_allocations a JOIN erp_payments p ON p.id=a.payment_id WHERE a.invoice_id=?",(iid,))]
    return result


@router.post("/invoices/generate")
async def generate(body:GenerateIn,idempotency_key:str=Header(...,alias="Idempotency-Key"),user=Depends(require_admin)):
    conn=get_db()
    try:
        # Idempotency is represented by the first invoice key; repeated runs report existing.
        existing=conn.execute("SELECT id FROM erp_invoices WHERE idempotency_key=?",(idempotency_key,)).fetchall()
        if existing: return {"created":[],"skipped_existing":len(existing),"invoices":[invoice_payload(conn,x["id"]) for x in existing]}
        params=[body.session_id]; where="s.status='active' AND p.session_id=?"
        if body.grade: where+=" AND s.grade=?"; params.append(body.grade)
        if body.student_ids: where+=" AND s.id IN ("+",".join("?"*len(body.student_ids))+")"; params.extend(body.student_ids)
        rows=conn.execute("SELECT s.id,s.grade,p.structure_id FROM erp_students s JOIN erp_student_fee_plans p ON p.student_id=s.id WHERE "+where,params).fetchall()
        created=[]; skipped=0
        for student in rows:
            old=conn.execute("SELECT id FROM erp_invoices WHERE student_id=? AND session_id=? AND period_code=? AND status!='cancelled'",(student["id"],body.session_id,body.period_code)).fetchone()
            if old: skipped+=1; continue
            items=conn.execute("SELECT i.*,h.name FROM erp_fee_structure_items i JOIN erp_fee_heads h ON h.id=i.fee_head_id WHERE structure_id=?",(student["structure_id"],)).fetchall()
            gross=sum(x["amount_paise"] for x in items)
            concessions=conn.execute("SELECT * FROM erp_concessions WHERE student_id=? AND session_id=? AND status='active'",(student["id"],body.session_id)).fetchall()
            lines=[]; total_con=0
            for item in items:
                applicable=[c for c in concessions if c["fee_head_id"] is None or c["fee_head_id"]==item["fee_head_id"]]
                con=0
                for c in applicable: con += item["amount_paise"]*c["value"]//10000 if c["kind"]=="percent" else c["value"]
                con=min(item["amount_paise"],con); total_con+=con
                lines.append((item["fee_head_id"],item["name"],item["amount_paise"],con,applicable[0]["id"] if applicable else None))
            if total_con>gross: raise HTTPException(400,"Concession exceeds gross amount")
            if body.dry_run: created.append({"student_id":student["id"],"gross_paise":gross,"concession_paise":total_con,"net_paise":gross-total_con}); continue
            n=counter(conn,"invoice"); sname=session_row(conn,body.session_id)["name"]; number=f"PPIS/{sname}/{n:06d}"; now=_ist_now()
            due=(date.fromisoformat(now[:10])+timedelta(days=15)).isoformat()
            cur=conn.execute("INSERT INTO erp_invoices(invoice_number,student_id,session_id,period_code,issue_date,due_date,gross_paise,concession_paise,net_paise,idempotency_key,created_at,updated_at) VALUES(?,?,?,?,?,?,?,?,?,?,?,?)",(number,student["id"],body.session_id,body.period_code,now[:10],due,gross,total_con,gross-total_con,idempotency_key if not created else None,now,now))
            for line in lines: conn.execute("INSERT INTO erp_invoice_lines(invoice_id,fee_head_id,description,amount_paise,concession_paise,concession_id) VALUES(?,?,?,?,?,?)",(cur.lastrowid,*line))
            audit(conn,user["user_id"],"generate","invoice",cur.lastrowid,{"period_code":body.period_code}); created.append(invoice_payload(conn,cur.lastrowid))
        conn.commit(); return {"created":created,"skipped_existing":skipped,"invoices":created}
    finally: conn.close()


@router.get("/invoices")
async def list_invoices(session_id:Optional[int]=None,grade:str="",status:str="",student_id:Optional[int]=None,overdue:bool=False,page:int=1,limit:int=50,user=Depends(require_admin)):
    conn=get_db()
    try:
        clauses=["1=1"]; p=[]
        for key,val in (("i.session_id",session_id),("i.status",status),("i.student_id",student_id),("s.grade",grade)):
            if val: clauses.append(key+"=?"); p.append(val)
        if overdue: clauses.append("i.due_date < ? AND i.status IN ('issued','partially_paid')"); p.append(_ist_now()[:10])
        rows=conn.execute("SELECT i.*,s.full_name,s.grade FROM erp_invoices i JOIN erp_students s ON s.id=i.student_id WHERE "+" AND ".join(clauses)+" ORDER BY i.due_date,i.id LIMIT ? OFFSET ?",(*p,limit,(page-1)*limit)).fetchall()
        return {"invoices":[dict(x) for x in rows],"page":page,"limit":limit}
    finally: conn.close()


@router.get("/invoices/{invoice_id}")
async def get_invoice(invoice_id:int,user=Depends(require_admin)):
    conn=get_db()
    try: return invoice_payload(conn,invoice_id)
    finally: conn.close()


@router.post("/invoices/{invoice_id}/issue")
async def issue(invoice_id:int,user=Depends(require_admin)):
    conn=get_db()
    try:
        row=conn.execute("SELECT status FROM erp_invoices WHERE id=?",(invoice_id,)).fetchone()
        if not row: raise HTTPException(404,"Invoice not found")
        if row["status"]!="draft": raise HTTPException(409,"Invoice cannot be issued")
        conn.execute("UPDATE erp_invoices SET status='issued',updated_at=? WHERE id=?",(_ist_now(),invoice_id)); audit(conn,user["user_id"],"issue","invoice",invoice_id); conn.commit(); return invoice_payload(conn,invoice_id)
    finally: conn.close()


@router.post("/invoices/{invoice_id}/cancel")
async def cancel(invoice_id:int,body:CancelIn,user=Depends(require_admin)):
    conn=get_db()
    try:
        row=conn.execute("SELECT status FROM erp_invoices WHERE id=?",(invoice_id,)).fetchone()
        if not row: raise HTTPException(404,"Invoice not found")
        if conn.execute("SELECT 1 FROM erp_payment_allocations a JOIN erp_payments p ON p.id=a.payment_id WHERE a.invoice_id=? AND p.status='confirmed'",(invoice_id,)).fetchone(): raise HTTPException(409,"Invoice has confirmed payments")
        conn.execute("UPDATE erp_invoices SET status='cancelled',cancel_reason=?,updated_at=? WHERE id=?", (body.reason,_ist_now(),invoice_id)); audit(conn,user["user_id"],"cancel","invoice",invoice_id,{"reason":body.reason}); conn.commit(); return invoice_payload(conn,invoice_id)
    finally: conn.close()


def recompute(conn, invoice_id):
    row=conn.execute("SELECT net_paise FROM erp_invoices WHERE id=?",(invoice_id,)).fetchone()
    paid=conn.execute("SELECT COALESCE(SUM(a.amount_paise),0) n FROM erp_payment_allocations a JOIN erp_payments p ON p.id=a.payment_id WHERE a.invoice_id=? AND p.status='confirmed'",(invoice_id,)).fetchone()["n"]
    status="paid" if paid>=row["net_paise"] else ("partially_paid" if paid else "issued")
    conn.execute("UPDATE erp_invoices SET paid_paise=?,status=?,updated_at=? WHERE id=?",(paid,status,_ist_now(),invoice_id))


@router.post("/payments")
async def payment(body:PaymentIn,idempotency_key:str=Header(...,alias="Idempotency-Key"),user=Depends(require_admin)):
    conn=get_db()
    try:
        old=conn.execute("SELECT id FROM erp_payments WHERE idempotency_key=?",(idempotency_key,)).fetchone()
        if old: return payment_payload(conn,old["id"])
        if len(body.reference_last4)>4: raise HTTPException(400,"Reference must be last four characters")
        if body.allocations: allocations=[(x.invoice_id,x.amount_paise) for x in body.allocations]
        else:
            rows=conn.execute("SELECT id,net_paise,paid_paise FROM erp_invoices WHERE student_id=? AND session_id=? AND status IN ('issued','partially_paid') AND paid_paise<net_paise ORDER BY due_date,id",(body.student_id,body.session_id)).fetchall()
            remaining=body.amount_paise; allocations=[]
            for r in rows:
                a=min(remaining,r["net_paise"]-r["paid_paise"])
                if a: allocations.append((r["id"],a)); remaining-=a
                if not remaining: break
        if sum(x[1] for x in allocations)!=body.amount_paise: raise HTTPException(400,"Payment must be fully allocated")
        for iid,amount in allocations:
            row=conn.execute("SELECT * FROM erp_invoices WHERE id=? AND student_id=?",(iid,body.student_id)).fetchone()
            if not row or row["status"]=="cancelled": raise HTTPException(409,"Invoice is unknown or cancelled")
            if row["paid_paise"]+amount>row["net_paise"]: raise HTTPException(400,"Allocation exceeds invoice due")
        n=counter(conn,"receipt"); sname=session_row(conn,body.session_id)["name"]; now=_ist_now()
        cur=conn.execute("INSERT INTO erp_payments(receipt_number,student_id,session_id,amount_paise,method,reference_last4,bank_label,paid_at,collected_by_user_id,idempotency_key,created_at,updated_at) VALUES(?,?,?,?,?,?,?,?,?,?,?,?)",(f"RCPT/{sname}/{n:06d}",body.student_id,body.session_id,body.amount_paise,body.method,body.reference_last4[-4:],body.bank_label,(body.paid_at or now),user["user_id"],idempotency_key,now,now))
        for iid,amount in allocations: conn.execute("INSERT INTO erp_payment_allocations(payment_id,invoice_id,amount_paise,created_at) VALUES(?,?,?,?)",(cur.lastrowid,iid,amount,now)); recompute(conn,iid)
        audit(conn,user["user_id"],"create","payment",cur.lastrowid,{"amount_paise":body.amount_paise}); conn.commit(); return payment_payload(conn,cur.lastrowid)
    finally: conn.close()


def payment_payload(conn,pid):
    row=conn.execute("SELECT * FROM erp_payments WHERE id=?",(pid,)).fetchone()
    if not row: raise HTTPException(404,"Payment not found")
    result=dict(row); result["allocations"]=[dict(x) for x in conn.execute("SELECT * FROM erp_payment_allocations WHERE payment_id=?",(pid,))]; return result


@router.get("/payments")
async def payments(session_id:Optional[int]=None,student_id:Optional[int]=None,user=Depends(require_admin)):
    conn=get_db()
    try:
        clauses=[];p=[]
        if session_id:clauses.append("session_id=?");p.append(session_id)
        if student_id:clauses.append("student_id=?");p.append(student_id)
        rows=conn.execute("SELECT * FROM erp_payments"+((" WHERE "+" AND ".join(clauses)) if clauses else "")+" ORDER BY paid_at DESC",p).fetchall(); return {"payments":[dict(x) for x in rows]}
    finally: conn.close()


@router.get("/payments/{payment_id}/receipt")
async def receipt(payment_id:int,user=Depends(require_admin)):
    conn=get_db()
    try: return payment_payload(conn,payment_id)
    finally: conn.close()


@router.post("/payments/{payment_id}/reverse")
async def reverse(payment_id:int,body:ReverseIn,user=Depends(require_admin)):
    conn=get_db()
    try:
        row=conn.execute("SELECT status FROM erp_payments WHERE id=?",(payment_id,)).fetchone()
        if not row: raise HTTPException(404,"Payment not found")
        if row["status"]=="reversed": return payment_payload(conn,payment_id)
        conn.execute("UPDATE erp_payments SET status='reversed',reversal_reason=?,updated_at=? WHERE id=?",(body.reason,_ist_now(),payment_id))
        for x in conn.execute("SELECT invoice_id FROM erp_payment_allocations WHERE payment_id=?",(payment_id,)): recompute(conn,x["invoice_id"])
        audit(conn,user["user_id"],"reverse","payment",payment_id,{"reason":body.reason}); conn.commit(); return payment_payload(conn,payment_id)
    finally: conn.close()


@router.get("/students/{student_id}/fees")
async def student_fees(student_id:int,session_id:Optional[int]=None,user=Depends(require_admin)):
    conn=get_db()
    try:
        p=[student_id]; clause="student_id=?"
        if session_id: clause+=" AND session_id=?";p.append(session_id)
        plan=conn.execute("SELECT * FROM erp_student_fee_plans WHERE "+clause,p).fetchall()
        invoices=conn.execute("SELECT * FROM erp_invoices WHERE "+clause,p).fetchall(); payments=conn.execute("SELECT * FROM erp_payments WHERE "+clause,p).fetchall()
        return {"plan":[dict(x) for x in plan],"invoices":[dict(x) for x in invoices],"receipts":[dict(x) for x in payments],"dues":sum(x["net_paise"]-x["paid_paise"] for x in invoices if x["status"]!="cancelled")}
    finally: conn.close()


@router.get("/fees/summary")
async def summary(session_id:int,user=Depends(require_admin)):
    conn=get_db()
    try:
        row=conn.execute("SELECT COALESCE(SUM(gross_paise),0) billed,COALESCE(SUM(concession_paise),0) concession,COALESCE(SUM(paid_paise),0) collected FROM erp_invoices WHERE session_id=? AND status!='cancelled'",(session_id,)).fetchone()
        grades=[dict(x) for x in conn.execute("SELECT s.grade,COALESCE(SUM(i.gross_paise),0) billed,COALESCE(SUM(i.concession_paise),0) concession,COALESCE(SUM(i.paid_paise),0) collected FROM erp_invoices i JOIN erp_students s ON s.id=i.student_id WHERE i.session_id=? AND i.status!='cancelled' GROUP BY s.grade",(session_id,))]
        result=dict(row);result["outstanding"]=result["billed"]-result["concession"]-result["collected"];result["by_grade"]=grades;return result
    finally: conn.close()


@router.get("/fees/dues")
async def dues(session_id:int,grade:str="",min_days_overdue:int=0,user=Depends(require_admin)):
    conn=get_db()
    try:
        extra=" AND s.grade=?" if grade else ""; p=[session_id,*([grade] if grade else [])]
        return {"dues":[dict(x) for x in conn.execute("SELECT i.*,s.full_name,s.grade FROM erp_invoices i JOIN erp_students s ON s.id=i.student_id WHERE i.session_id=? AND i.status IN ('issued','partially_paid') AND i.net_paise>i.paid_paise"+extra,p)]}
    finally: conn.close()


@router.get("/fees/collections")
async def collections(from_:str=Query("",alias="from"),to:str="",method:str="",user=Depends(require_admin)):
    conn=get_db()
    try:
        clauses=["status='confirmed'"];p=[]
        if from_:clauses.append("paid_at>=?");p.append(from_)
        if to:clauses.append("paid_at<=?");p.append(to)
        if method:clauses.append("method=?");p.append(method)
        return {"collections":[dict(x) for x in conn.execute("SELECT * FROM erp_payments WHERE "+" AND ".join(clauses)+" ORDER BY paid_at",p)]}
    finally: conn.close()
