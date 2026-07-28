import tempfile
import unittest
from pathlib import Path

from fastapi.testclient import TestClient

from app import database
from app.main import app
from app.routes.auth import create_token


class ErpAdmissionsTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.old_db, self.old_pi = database.DB_PATH, database.PI_SHEET_PATH
        database.DB_PATH = str(Path(self.tmp.name) / "admissions.db")
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

    def _create(self):
        return self.client.post(
            "/api/erp/admissions",
            headers=self.admin,
            json={
                "applicant_name": "New Applicant",
                "grade_applying": "Grade 4A",
                "date_of_birth": "2017-05-20",
                "gender": "Female",
                "parent_name": "Applicant Parent",
                "parent_phone": "9812345678",
                "parent_email": "parent@example.com",
                "address": "School Road",
                "source": "website",
                "session_id": 1,
            },
        )

    def test_create_gets_application_number_and_list_filter_works(self):
        response = self._create()
        self.assertEqual(response.status_code, 201)
        enquiry = response.json()
        self.assertRegex(enquiry["application_number"], r"^ADM-\d{4}-\d+$")
        listing = self.client.get(
            "/api/erp/admissions?grade=Grade%204A&search=9812345678",
            headers=self.admin,
        )
        self.assertEqual(listing.status_code, 200)
        self.assertEqual(listing.json()["total"], 1)
        self.assertEqual(listing.json()["items"][0]["id"], enquiry["id"])

    def test_status_change_validates(self):
        enquiry = self._create().json()
        invalid = self.client.post(
            f"/api/erp/admissions/{enquiry['id']}/status",
            headers=self.admin,
            json={"status": "not-a-status"},
        )
        self.assertEqual(invalid.status_code, 400)
        valid = self.client.post(
            f"/api/erp/admissions/{enquiry['id']}/status",
            headers=self.admin,
            json={"status": "shortlisted", "note": "Reviewed"},
        )
        self.assertEqual(valid.status_code, 200)
        self.assertEqual(valid.json()["status"], "shortlisted")
        self.assertIn("Reviewed", valid.json()["notes"])

    def test_convert_creates_student_and_guardian_idempotently(self):
        enquiry = self._create().json()
        converted = self.client.post(
            f"/api/erp/admissions/{enquiry['id']}/convert",
            headers=self.admin,
        )
        self.assertEqual(converted.status_code, 200)
        student_id = converted.json()["student_id"]
        db = database.get_db()
        student_count = db.execute(
            "SELECT COUNT(*) AS count FROM erp_students WHERE id = ?", (student_id,)
        ).fetchone()["count"]
        guardian_count = db.execute(
            """SELECT COUNT(*) AS count FROM erp_student_guardians
               WHERE student_id = ?""",
            (student_id,),
        ).fetchone()["count"]
        db.close()
        self.assertEqual(student_count, 1)
        self.assertEqual(guardian_count, 1)

        repeated = self.client.post(
            f"/api/erp/admissions/{enquiry['id']}/convert",
            headers=self.admin,
        )
        self.assertEqual(repeated.status_code, 200)
        self.assertEqual(repeated.json()["student_id"], student_id)
        db = database.get_db()
        self.assertEqual(
            db.execute("SELECT COUNT(*) AS count FROM erp_students").fetchone()["count"],
            1,
        )
        db.close()

    def test_parent_is_forbidden(self):
        response = self.client.get(
            "/api/erp/admissions",
            headers=self._parent_headers(),
        )
        self.assertEqual(response.status_code, 403)


if __name__ == "__main__":
    unittest.main()
