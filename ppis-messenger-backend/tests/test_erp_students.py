import json
import tempfile
import unittest
from pathlib import Path

from fastapi.testclient import TestClient

from app import database
from app.main import app
from app.routes.auth import create_token


class ErpStudentTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        root = Path(self.directory.name)
        self.original_db_path = database.DB_PATH
        self.original_pi_path = database.PI_SHEET_PATH
        database.DB_PATH = str(root / "erp.db")
        database.PI_SHEET_PATH = str(root / "pi_sheet_data.json")
        Path(database.PI_SHEET_PATH).write_text(
            json.dumps(
                [
                    {
                        "student": "Aarav Test",
                        "grade": "Grade 5B",
                        "father": "Parent One",
                        "father_mobile": "9000000001",
                        "mother": "Parent Two",
                        "mother_mobile": "9000000002",
                        "address": "Delhi",
                        "transport": "Route 4",
                    },
                    {
                        "student": "Diya Test",
                        "grade": "3C",
                        "mother": "Parent Three",
                        "mother_mobile": "9000000003",
                        "address": "Delhi",
                        "transport": "No",
                    },
                ]
            ),
            encoding="utf-8",
        )
        self.client_context = TestClient(app)
        self.client = self.client_context.__enter__()

        conn = database.get_db()
        admin = conn.execute(
            "SELECT id, phone, role FROM users WHERE role = 'admin' ORDER BY id LIMIT 1"
        ).fetchone()
        conn.close()
        token = create_token(admin["id"], admin["role"], admin["phone"])
        self.headers = {"Authorization": f"Bearer {token}"}

    def tearDown(self):
        self.client_context.__exit__(None, None, None)
        database.DB_PATH = self.original_db_path
        database.PI_SHEET_PATH = self.original_pi_path
        self.directory.cleanup()

    def test_pi_roster_is_seeded_into_erp_overview_and_directory(self):
        overview = self.client.get("/api/erp/overview", headers=self.headers)
        self.assertEqual(overview.status_code, 200)
        self.assertEqual(overview.json()["active_students"], 2)
        self.assertEqual(overview.json()["total_guardians"], 3)
        self.assertEqual(overview.json()["transport_students"], 1)

        students = self.client.get(
            "/api/erp/students?grade=Grade%205B", headers=self.headers
        )
        self.assertEqual(students.status_code, 200)
        self.assertEqual(students.json()["total"], 1)
        self.assertEqual(students.json()["students"][0]["full_name"], "Aarav Test")

    def test_admin_can_create_and_update_student_with_guardian(self):
        created = self.client.post(
            "/api/erp/students",
            headers=self.headers,
            json={
                "admission_number": "PPIS-TEST-1",
                "full_name": "Kabir Test",
                "grade": "Grade 2A",
                "transport": "Route 2",
                "guardians": [
                    {
                        "full_name": "Parent Four",
                        "phone": "9000000004",
                        "relationship": "mother",
                        "is_primary": True,
                    }
                ],
            },
        )
        self.assertEqual(created.status_code, 201)
        student = created.json()
        self.assertEqual(student["guardians"][0]["phone"], "9000000004")
        self.assertTrue(student["guardians"][0]["is_primary"])
        self.assertTrue(student["created_at"].endswith("+05:30"))

        updated = self.client.put(
            f"/api/erp/students/{student['id']}",
            headers=self.headers,
            json={"status": "inactive", "grade": "Grade 2B"},
        )
        self.assertEqual(updated.status_code, 200)
        self.assertEqual(updated.json()["status"], "inactive")
        self.assertEqual(updated.json()["grade"], "Grade 2B")

        conn = database.get_db()
        actions = conn.execute(
            "SELECT action FROM erp_audit_log WHERE entity_id = ? ORDER BY id",
            (student["id"],),
        ).fetchall()
        conn.close()
        self.assertEqual([row["action"] for row in actions], ["create", "update"])

    def test_parent_token_cannot_access_erp(self):
        conn = database.get_db()
        parent = conn.execute(
            "SELECT id, phone, role FROM users WHERE role = 'parent' ORDER BY id LIMIT 1"
        ).fetchone()
        conn.close()
        token = create_token(parent["id"], parent["role"], parent["phone"])
        response = self.client.get(
            "/api/erp/overview",
            headers={"Authorization": f"Bearer {token}"},
        )
        self.assertEqual(response.status_code, 403)


if __name__ == "__main__":
    unittest.main()
