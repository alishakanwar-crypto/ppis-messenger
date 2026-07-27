import tempfile
import unittest
from pathlib import Path

from fastapi.testclient import TestClient

from app import database
from app.main import app
from app.routes.auth import create_token


class ErpFeesSmokeTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.old_db, self.old_pi = database.DB_PATH, database.PI_SHEET_PATH
        database.DB_PATH = str(Path(self.tmp.name) / "fees.db")
        database.PI_SHEET_PATH = str(Path(self.tmp.name) / "missing.json")
        self.context = TestClient(app)
        self.client = self.context.__enter__()
        db = database.get_db()
        admin = db.execute("SELECT id, phone, role FROM users WHERE role='admin' LIMIT 1").fetchone()
        self.admin = {"Authorization": f"Bearer {create_token(admin['id'], admin['role'], admin['phone'])}"}
        db.close()

    def tearDown(self):
        self.context.__exit__(None, None, None)
        database.DB_PATH, database.PI_SHEET_PATH = self.old_db, self.old_pi
        self.tmp.cleanup()

    def test_admin_can_read_seeded_fee_catalog_and_parent_is_forbidden(self):
        self.assertEqual(self.client.get("/api/erp/sessions", headers=self.admin).status_code, 200)
        self.assertEqual(len(self.client.get("/api/erp/fee-heads", headers=self.admin).json()["fee_heads"]), 5)
        db = database.get_db()
        db.execute("INSERT INTO users(phone,name,role) VALUES ('9000000000','Test Parent','parent')")
        db.commit()
        parent = db.execute("SELECT id, phone, role FROM users WHERE role='parent' LIMIT 1").fetchone()
        db.close()
        parent_headers = {"Authorization": f"Bearer {create_token(parent['id'], parent['role'], parent['phone'])}"}
        self.assertEqual(self.client.get("/api/erp/sessions", headers=parent_headers).status_code, 403)

    def test_money_and_reference_validation(self):
        response = self.client.post("/api/erp/payments", headers={**self.admin, "Idempotency-Key": "money-test"}, json={
            "student_id": 1, "session_id": 1, "amount_paise": 0, "method": "cash",
        })
        self.assertEqual(response.status_code, 422)

    def test_batch_invoice_generation_uses_sequential_numbers_and_is_idempotent(self):
        db = database.get_db()
        now = database._ist_now()
        session = db.execute(
            "SELECT id FROM erp_academic_sessions WHERE is_current = 1"
        ).fetchone()
        fee_head = db.execute(
            "SELECT id FROM erp_fee_heads WHERE code = 'TUITION'"
        ).fetchone()
        student_ids = []
        for name in ("Batch Student One", "Batch Student Two"):
            student_ids.append(
                db.execute(
                    """INSERT INTO erp_students
                       (full_name, grade, status, source, created_at, updated_at)
                       VALUES (?, 'Grade 4A', 'active', 'test', ?, ?)""",
                    (name, now, now),
                ).lastrowid
            )
        db.commit()
        db.close()

        structure_response = self.client.post(
            "/api/erp/fee-structures",
            headers=self.admin,
            json={
                "session_id": session["id"],
                "grade": "Grade 4A",
                "frequency": "monthly",
                "items": [{"fee_head_id": fee_head["id"], "amount_paise": 12500}],
            },
        )
        self.assertEqual(structure_response.status_code, 201)
        structure = structure_response.json()
        publish_response = self.client.post(
            f"/api/erp/fee-structures/{structure['id']}/publish",
            headers=self.admin,
        )
        self.assertEqual(publish_response.status_code, 200)

        for student_id in student_ids:
            plan_response = self.client.post(
                f"/api/erp/students/{student_id}/fee-plan",
                headers=self.admin,
                json={
                    "session_id": session["id"],
                    "structure_id": structure["id"],
                },
            )
            self.assertEqual(plan_response.status_code, 200)

        generate_response = self.client.post(
            "/api/erp/invoices/generate",
            headers={**self.admin, "Idempotency-Key": "batch-invoice-test"},
            json={
                "session_id": session["id"],
                "period_code": "2026-04",
                "grade": "Grade 4A",
            },
        )
        self.assertEqual(generate_response.status_code, 200)
        generated = generate_response.json()
        self.assertEqual(len(generated["created"]), 2)
        invoice_numbers = [invoice["invoice_number"] for invoice in generated["created"]]
        self.assertEqual(invoice_numbers, ["PPIS/2026-27/000001", "PPIS/2026-27/000002"])
        for invoice in generated["created"]:
            self.assertIsInstance(invoice["gross_paise"], int)
            self.assertIsInstance(invoice["concession_paise"], int)
            self.assertIsInstance(invoice["net_paise"], int)
            self.assertEqual(invoice["status"], "issued")
            self.assertEqual(
                invoice["net_paise"],
                invoice["gross_paise"] - invoice["concession_paise"],
            )

        first_invoice = generated["created"][0]
        dues_before = self.client.get(
            f"/api/erp/fees/dues?session_id={session['id']}&grade=Grade%204A",
            headers=self.admin,
        )
        self.assertEqual(dues_before.status_code, 200)
        self.assertIn(first_invoice["id"], [invoice["id"] for invoice in dues_before.json()["dues"]])

        payment_response = self.client.post(
            "/api/erp/payments",
            headers={**self.admin, "Idempotency-Key": "batch-payment-test"},
            json={
                "student_id": student_ids[0],
                "session_id": session["id"],
                "amount_paise": first_invoice["net_paise"],
                "method": "cash",
            },
        )
        self.assertEqual(payment_response.status_code, 200)
        payment = payment_response.json()
        self.assertTrue(payment["receipt_number"])
        self.assertEqual(payment["amount_paise"], first_invoice["net_paise"])

        student_fees = self.client.get(
            f"/api/erp/students/{student_ids[0]}/fees?session_id={session['id']}",
            headers=self.admin,
        )
        self.assertEqual(student_fees.status_code, 200)
        paid_invoice = next(
            invoice for invoice in student_fees.json()["invoices"]
            if invoice["id"] == first_invoice["id"]
        )
        self.assertEqual(paid_invoice["status"], "paid")
        self.assertEqual(paid_invoice["paid_paise"], first_invoice["net_paise"])

        dues_after = self.client.get(
            f"/api/erp/fees/dues?session_id={session['id']}&grade=Grade%204A",
            headers=self.admin,
        )
        self.assertEqual(dues_after.status_code, 200)
        self.assertNotIn(first_invoice["id"], [invoice["id"] for invoice in dues_after.json()["dues"]])

        repeat_response = self.client.post(
            "/api/erp/invoices/generate",
            headers={**self.admin, "Idempotency-Key": "different-batch-key"},
            json={
                "session_id": session["id"],
                "period_code": "2026-04",
                "grade": "Grade 4A",
            },
        )
        self.assertEqual(repeat_response.status_code, 200)
        repeated = repeat_response.json()
        self.assertEqual(repeated["created"], [])
        self.assertEqual(repeated["skipped_existing"], 2)


if __name__ == "__main__":
    unittest.main()
