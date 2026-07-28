import tempfile
import unittest
from pathlib import Path

from fastapi.testclient import TestClient

from app import database
from app.main import app
from app.routes.auth import create_token


class ErpStaffTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.old_db, self.old_pi = database.DB_PATH, database.PI_SHEET_PATH
        database.DB_PATH = str(Path(self.tmp.name) / "staff.db")
        database.PI_SHEET_PATH = str(Path(self.tmp.name) / "missing.json")
        self.context = TestClient(app)
        self.client = self.context.__enter__()
        db = database.get_db()
        admin = db.execute(
            "SELECT id, phone, role FROM users WHERE role = 'admin' LIMIT 1"
        ).fetchone()
        self.admin = {
            "Authorization": f"Bearer {create_token(admin['id'], admin['role'], admin['phone'])}"
        }
        db.close()

    def tearDown(self):
        self.context.__exit__(None, None, None)
        database.DB_PATH, database.PI_SHEET_PATH = self.old_db, self.old_pi
        self.tmp.cleanup()

    def _parent_headers(self):
        db = database.get_db()
        db.execute(
            "INSERT INTO users(phone, name, role) VALUES ('9000000000', 'Test Parent', 'parent')"
        )
        db.commit()
        parent = db.execute(
            "SELECT id, phone, role FROM users WHERE phone = '9000000000'"
        ).fetchone()
        db.close()
        return {
            "Authorization": f"Bearer {create_token(parent['id'], parent['role'], parent['phone'])}"
        }

    def _create_staff(self, name, ctc=25000):
        response = self.client.post(
            "/api/erp/staff",
            headers=self.admin,
            json={
                "full_name": name,
                "role": "Teacher",
                "department": "Primary",
                "phone": "9812345678",
                "monthly_ctc": ctc,
            },
        )
        self.assertEqual(response.status_code, 201)
        return response.json()

    def test_staff_code_ctc_and_search(self):
        staff = self._create_staff("Alice Teacher", 25000.125)
        self.assertRegex(staff["employee_code"], r"^EMP-\d+$")
        self.assertEqual(staff["monthly_ctc"], 25000.13)
        listing = self.client.get(
            "/api/erp/staff?search=Alice&department=Primary",
            headers=self.admin,
        )
        self.assertEqual(listing.status_code, 200)
        self.assertEqual(listing.json()["items"][0]["id"], staff["id"])

    def test_payroll_idempotent_generation_edit_and_finalize(self):
        first = self._create_staff("Active Teacher", 30000)
        self._create_staff("Second Teacher", 32000)
        inactive = self.client.post(
            "/api/erp/staff",
            headers=self.admin,
            json={"full_name": "Inactive Teacher", "monthly_ctc": 10000, "status": "inactive"},
        )
        self.assertEqual(inactive.status_code, 201)
        run = self.client.post(
            "/api/erp/payroll", headers=self.admin, json={"month": "2026-08"}
        ).json()
        same_run = self.client.post(
            "/api/erp/payroll", headers=self.admin, json={"month": "2026-08"}
        ).json()
        self.assertEqual(run["id"], same_run["id"])
        generated = self.client.post(
            f"/api/erp/payroll/{run['id']}/generate", headers=self.admin
        )
        self.assertEqual(generated.json()["created"], 2)
        detail = self.client.get(f"/api/erp/payroll/{run['id']}", headers=self.admin).json()
        self.assertEqual(len(detail["payslips"]), 2)
        payslip = next(item for item in detail["payslips"] if item["staff_id"] == first["id"])
        edited = self.client.put(
            f"/api/erp/payroll/payslips/{payslip['id']}",
            headers=self.admin,
            json={"gross": 30000, "deductions": 2500, "remarks": "PF"},
        )
        self.assertEqual(edited.status_code, 200)
        self.assertEqual(edited.json()["net"], 27500)
        self.assertEqual(
            self.client.post(
                f"/api/erp/payroll/{run['id']}/generate", headers=self.admin
            ).json()["created"],
            0,
        )
        finalized = self.client.post(
            f"/api/erp/payroll/{run['id']}/finalize", headers=self.admin
        )
        self.assertEqual(finalized.status_code, 200)
        blocked = self.client.put(
            f"/api/erp/payroll/payslips/{payslip['id']}",
            headers=self.admin,
            json={"gross": 1, "deductions": 0},
        )
        self.assertEqual(blocked.status_code, 400)

    def test_parent_forbidden(self):
        response = self.client.get("/api/erp/staff", headers=self._parent_headers())
        self.assertEqual(response.status_code, 403)


if __name__ == "__main__":
    unittest.main()
