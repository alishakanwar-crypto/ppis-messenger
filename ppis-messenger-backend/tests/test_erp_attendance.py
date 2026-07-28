import tempfile
import unittest
from pathlib import Path

from fastapi.testclient import TestClient

from app import database
from app.main import app
from app.routes.auth import create_token


class ErpAttendanceTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.old_db, self.old_pi = database.DB_PATH, database.PI_SHEET_PATH
        database.DB_PATH = str(Path(self.tmp.name) / "attendance.db")
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
        now = database._ist_now()
        self.student_ids = [
            db.execute(
                """INSERT INTO erp_students
                   (full_name, grade, status, source, created_at, updated_at)
                   VALUES (?, 'Grade 4A', 'active', 'test', ?, ?)""",
                (name, now, now),
            ).lastrowid
            for name in ("Attendance Student One", "Attendance Student Two")
        ]
        db.commit()
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

    def test_admin_marks_and_reads_roster(self):
        response = self.client.post(
            "/api/erp/attendance/mark",
            headers=self.admin,
            json={
                "session_id": 1,
                "date": "2026-07-28",
                "entries": [
                    {"student_id": self.student_ids[0], "status": "present"},
                    {"student_id": self.student_ids[1], "status": "absent"},
                ],
            },
        )
        self.assertEqual(response.status_code, 200)
        roster = self.client.get(
            "/api/erp/attendance?grade=Grade%204A&date=2026-07-28&session_id=1",
            headers=self.admin,
        )
        self.assertEqual(roster.status_code, 200)
        self.assertEqual(roster.json()["summary"]["present"], 1)
        self.assertEqual(roster.json()["summary"]["absent"], 1)

    def test_parent_is_forbidden(self):
        response = self.client.get(
            "/api/erp/attendance?date=2026-07-28",
            headers=self._parent_headers(),
        )
        self.assertEqual(response.status_code, 403)

    def test_remarking_same_day_is_idempotent(self):
        payload = {
            "session_id": 1,
            "date": "2026-07-28",
            "entries": [{"student_id": self.student_ids[0], "status": "present"}],
        }
        self.assertEqual(
            self.client.post("/api/erp/attendance/mark", headers=self.admin, json=payload).status_code,
            200,
        )
        payload["entries"][0]["status"] = "late"
        self.assertEqual(
            self.client.post("/api/erp/attendance/mark", headers=self.admin, json=payload).status_code,
            200,
        )
        db = database.get_db()
        row = db.execute(
            "SELECT COUNT(*) AS count, status FROM erp_attendance WHERE student_id = ? AND date = ?",
            (self.student_ids[0], "2026-07-28"),
        ).fetchone()
        db.close()
        self.assertEqual(row["count"], 1)
        self.assertEqual(row["status"], "late")

    def test_leave_approval_writes_leave_attendance(self):
        leave = self.client.post(
            "/api/erp/leave",
            headers=self.admin,
            json={
                "student_id": self.student_ids[0],
                "session_id": 1,
                "from_date": "2026-07-28",
                "to_date": "2026-07-29",
                "leave_type": "sick",
                "reason": "Medical leave",
            },
        )
        self.assertEqual(leave.status_code, 201)
        decision = self.client.post(
            f"/api/erp/leave/{leave.json()['id']}/decision",
            headers=self.admin,
            json={"decision": "approved"},
        )
        self.assertEqual(decision.status_code, 200)
        db = database.get_db()
        rows = db.execute(
            "SELECT date, status FROM erp_attendance WHERE student_id = ? ORDER BY date",
            (self.student_ids[0],),
        ).fetchall()
        db.close()
        self.assertEqual([(row["date"], row["status"]) for row in rows], [
            ("2026-07-28", "leave"),
            ("2026-07-29", "leave"),
        ])

    def test_summary_counts_are_correct(self):
        response = self.client.post(
            "/api/erp/attendance/mark",
            headers=self.admin,
            json={
                "session_id": 1,
                "date": "2026-07-28",
                "entries": [
                    {"student_id": self.student_ids[0], "status": "present"},
                    {"student_id": self.student_ids[1], "status": "absent"},
                ],
            },
        )
        self.assertEqual(response.status_code, 200)
        summary = self.client.get(
            "/api/erp/attendance/summary?from=2026-07-28&to=2026-07-28&grade=Grade%204A&session_id=1",
            headers=self.admin,
        )
        self.assertEqual(summary.status_code, 200)
        self.assertEqual(summary.json()["days"][0]["counts"]["present"], 1)
        students = {row["student_id"]: row for row in summary.json()["students"]}
        self.assertEqual(students[self.student_ids[0]]["percentage"], 100)
        self.assertEqual(students[self.student_ids[1]]["percentage"], 0)

    def test_invalid_status_returns_400(self):
        response = self.client.post(
            "/api/erp/attendance/mark",
            headers=self.admin,
            json={
                "session_id": 1,
                "date": "2026-07-28",
                "entries": [{"student_id": self.student_ids[0], "status": "unknown"}],
            },
        )
        self.assertEqual(response.status_code, 400)


if __name__ == "__main__":
    unittest.main()
