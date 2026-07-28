import tempfile
import unittest
from pathlib import Path

from fastapi.testclient import TestClient

from app import database
from app.main import app
from app.routes.auth import create_token


class ErpTimetableTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.old_db, self.old_pi = database.DB_PATH, database.PI_SHEET_PATH
        database.DB_PATH = str(Path(self.tmp.name) / "timetable.db")
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

    def test_slot_upsert_and_invalid_day(self):
        payload = {
            "session_id": 1,
            "grade": "Grade 4A",
            "day_of_week": 1,
            "period": 1,
            "subject": "Math",
            "teacher": "Teacher One",
        }
        created = self.client.post(
            "/api/erp/timetable/slots", headers=self.admin, json=payload
        )
        self.assertEqual(created.status_code, 200)
        updated = self.client.post(
            "/api/erp/timetable/slots",
            headers=self.admin,
            json={**payload, "subject": "Science"},
        )
        self.assertEqual(updated.status_code, 200)
        self.assertEqual(updated.json()["subject"], "Science")
        listing = self.client.get(
            "/api/erp/timetable?session_id=1&grade=Grade%204A",
            headers=self.admin,
        )
        self.assertEqual(len(listing.json()["slots"]), 1)
        for day in (0, 8):
            invalid = self.client.post(
                "/api/erp/timetable/slots",
                headers=self.admin,
                json={**payload, "day_of_week": day},
            )
            self.assertEqual(invalid.status_code, 400)

    def test_bulk_save_writes_all_slots(self):
        response = self.client.post(
            "/api/erp/timetable/bulk",
            headers=self.admin,
            json={
                "session_id": 1,
                "grade": "Grade 5A",
                "slots": [
                    {"day_of_week": 1, "period": 1, "subject": "Math"},
                    {"day_of_week": 2, "period": 2, "subject": "English"},
                    {"day_of_week": 3, "period": 3, "subject": "Science"},
                ],
            },
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["saved"], 3)
        listing = self.client.get(
            "/api/erp/timetable?session_id=1&grade=Grade%205A",
            headers=self.admin,
        )
        self.assertEqual(len(listing.json()["slots"]), 3)

    def test_homework_validation_creation_and_listing(self):
        missing_title = self.client.post(
            "/api/erp/homework",
            headers=self.admin,
            json={"grade": "Grade 4A", "assigned_date": "2026-08-01"},
        )
        self.assertEqual(missing_title.status_code, 422)
        invalid_dates = self.client.post(
            "/api/erp/homework",
            headers=self.admin,
            json={
                "grade": "Grade 4A",
                "title": "Worksheet",
                "assigned_date": "2026-08-02",
                "due_date": "2026-08-01",
            },
        )
        self.assertEqual(invalid_dates.status_code, 400)
        created = self.client.post(
            "/api/erp/homework",
            headers=self.admin,
            json={
                "session_id": 1,
                "grade": "Grade 4A",
                "subject": "Math",
                "title": "Worksheet",
                "assigned_date": "2026-08-01",
                "due_date": "2026-08-03",
            },
        )
        self.assertEqual(created.status_code, 201)
        homework_id = created.json()["id"]
        listing = self.client.get(
            "/api/erp/homework?session_id=1&grade=Grade%204A", headers=self.admin
        )
        self.assertEqual(listing.status_code, 200)
        self.assertEqual(listing.json()["homework"][0]["id"], homework_id)
        invalid_status = self.client.put(
            f"/api/erp/homework/{homework_id}",
            headers=self.admin,
            json={"status": "invalid"},
        )
        self.assertEqual(invalid_status.status_code, 400)

    def test_parent_forbidden(self):
        response = self.client.get("/api/erp/timetable", headers=self._parent_headers())
        self.assertEqual(response.status_code, 403)


if __name__ == "__main__":
    unittest.main()
