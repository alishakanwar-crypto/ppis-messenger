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


if __name__ == "__main__":
    unittest.main()
