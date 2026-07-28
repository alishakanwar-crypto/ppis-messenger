import tempfile
import unittest
from pathlib import Path

from fastapi.testclient import TestClient

from app import database
from app.main import app
from app.routes.auth import create_token


class ErpExamsTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.old_db, self.old_pi = database.DB_PATH, database.PI_SHEET_PATH
        database.DB_PATH = str(Path(self.tmp.name) / "exams.db")
        database.PI_SHEET_PATH = str(Path(self.tmp.name) / "missing.json")
        self.context = TestClient(app)
        self.client = self.context.__enter__()
        db = database.get_db()
        admin = db.execute(
            "SELECT id, phone, role FROM users WHERE role = 'admin' LIMIT 1"
        ).fetchone()
        now = database._ist_now()
        self.student_id = db.execute(
            """INSERT INTO erp_students
               (full_name, grade, status, source, created_at, updated_at)
               VALUES ('Exam Student', 'Grade 4A', 'active', 'test', ?, ?)""",
            (now, now),
        ).lastrowid
        db.commit()
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

    def _exam(self):
        response = self.client.post(
            "/api/erp/exams",
            headers=self.admin,
            json={"name": "Term 1", "session_id": 1, "grade": "Grade 4A"},
        )
        self.assertEqual(response.status_code, 201)
        exam = response.json()
        subject = self.client.post(
            f"/api/erp/exams/{exam['id']}/subjects",
            headers=self.admin,
            json={"subject": "Mathematics", "max_marks": 100, "pass_marks": 40},
        )
        self.assertEqual(subject.status_code, 201)
        return exam, subject.json()

    def test_create_subjects_and_parent_forbidden(self):
        exam, subject = self._exam()
        detail = self.client.get(f"/api/erp/exams/{exam['id']}", headers=self.admin)
        self.assertEqual(detail.status_code, 200)
        self.assertEqual(detail.json()["subjects"][0]["id"], subject["id"])
        forbidden = self.client.get("/api/erp/exams", headers=self._parent_headers())
        self.assertEqual(forbidden.status_code, 403)

    def test_marks_are_idempotent_and_validate_maximum(self):
        exam, subject = self._exam()
        invalid = self.client.post(
            f"/api/erp/exams/{exam['id']}/marks",
            headers=self.admin,
            json={"entries": [{"student_id": self.student_id, "subject_id": subject["id"], "marks_obtained": 101}]},
        )
        self.assertEqual(invalid.status_code, 400)
        payload = {"entries": [{"student_id": self.student_id, "subject_id": subject["id"], "marks_obtained": 80}]}
        self.assertEqual(
            self.client.post(f"/api/erp/exams/{exam['id']}/marks", headers=self.admin, json=payload).status_code,
            200,
        )
        self.assertEqual(
            self.client.post(f"/api/erp/exams/{exam['id']}/marks", headers=self.admin, json=payload).status_code,
            200,
        )
        db = database.get_db()
        self.assertEqual(
            db.execute("SELECT COUNT(*) AS count FROM erp_exam_marks").fetchone()["count"],
            1,
        )
        db.close()

    def test_absent_report_card_and_results_ranking(self):
        exam, subject = self._exam()
        db = database.get_db()
        second_id = db.execute(
            """INSERT INTO erp_students
               (full_name, grade, status, source, created_at, updated_at)
               VALUES ('Second Student', 'Grade 4A', 'active', 'test', ?, ?)""",
            (database._ist_now(), database._ist_now()),
        ).lastrowid
        db.commit()
        db.close()
        response = self.client.post(
            f"/api/erp/exams/{exam['id']}/marks",
            headers=self.admin,
            json={
                "entries": [
                    {"student_id": self.student_id, "subject_id": subject["id"], "is_absent": True},
                    {"student_id": second_id, "subject_id": subject["id"], "marks_obtained": 90},
                ]
            },
        )
        self.assertEqual(response.status_code, 200)
        card = self.client.get(
            f"/api/erp/exams/{exam['id']}/report-card/{self.student_id}",
            headers=self.admin,
        )
        self.assertEqual(card.status_code, 200)
        self.assertEqual(card.json()["total_obtained"], 0)
        self.assertEqual(card.json()["percentage"], 0)
        self.assertEqual(card.json()["subjects"][0]["is_absent"], 1)
        results = self.client.get(f"/api/erp/exams/{exam['id']}/results", headers=self.admin)
        self.assertEqual(results.status_code, 200)
        self.assertEqual(results.json()["results"][0]["student_id"], second_id)
        self.assertEqual(results.json()["results"][0]["rank"], 1)


if __name__ == "__main__":
    unittest.main()
