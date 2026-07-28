import tempfile
import unittest
from pathlib import Path

from fastapi.testclient import TestClient

from app import database
from app.main import app
from app.routes.auth import create_token


class ErpPortalTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.old_db, self.old_pi = database.DB_PATH, database.PI_SHEET_PATH
        database.DB_PATH = str(Path(self.tmp.name) / "portal.db")
        database.PI_SHEET_PATH = str(Path(self.tmp.name) / "missing.json")
        self.context = TestClient(app)
        self.client = self.context.__enter__()
        conn = database.get_db()
        admin = conn.execute("SELECT id, phone, role FROM users WHERE role = 'admin' LIMIT 1").fetchone()
        now = database._ist_now()
        self.child_a = conn.execute(
            "INSERT INTO erp_students(full_name, grade, status, created_at, updated_at) VALUES ('Child A', 'Grade X', 'active', ?, ?)",
            (now, now),
        ).lastrowid
        self.child_b = conn.execute(
            "INSERT INTO erp_students(full_name, grade, status, created_at, updated_at) VALUES ('Child B', 'Grade Y', 'active', ?, ?)",
            (now, now),
        ).lastrowid
        guardian = conn.execute(
            "INSERT INTO erp_guardians(full_name, phone, created_at, updated_at) VALUES ('Parent A', '9000000001', ?, ?)",
            (now, now),
        ).lastrowid
        conn.execute("INSERT INTO erp_student_guardians(student_id, guardian_id, relationship, is_primary) VALUES (?, ?, 'parent', 1)", (self.child_a, guardian))
        parent_user = conn.execute("INSERT INTO users(phone, name, role) VALUES ('9000000001', 'Parent A', 'parent')")
        teacher = conn.execute("INSERT INTO users(phone, name, role) VALUES ('9000000002', 'Teacher A', 'teacher')").lastrowid
        conn.commit()
        self.admin = {"Authorization": f"Bearer {create_token(admin['id'], admin['role'], admin['phone'])}"}
        self.parent = {"Authorization": f"Bearer {create_token(parent_user.lastrowid, 'parent', '9000000001')}"}
        self.teacher = {"Authorization": f"Bearer {create_token(teacher, 'teacher', '9000000002')}"}
        self.teacher_id = teacher
        conn.close()

    def tearDown(self):
        self.context.__exit__(None, None, None)
        database.DB_PATH, database.PI_SHEET_PATH = self.old_db, self.old_pi
        self.tmp.cleanup()

    def test_parent_is_self_scoped(self):
        children = self.client.get("/api/erp/portal/children", headers=self.parent)
        self.assertEqual(children.status_code, 200)
        self.assertEqual([x["id"] for x in children.json()["children"]], [self.child_a])
        self.assertEqual(self.client.get(f"/api/erp/portal/children/{self.child_a}/homework", headers=self.parent).status_code, 200)
        self.assertEqual(self.client.get(f"/api/erp/portal/children/{self.child_b}/homework", headers=self.parent).status_code, 403)

    def test_teacher_grade_scope_and_admin_management(self):
        assigned = self.client.post(
            "/api/erp/portal/teachers",
            headers=self.admin,
            json={"phone": "9000000002", "name": "Teacher A", "grades": ["Grade X"]},
        )
        self.assertEqual(assigned.status_code, 200)
        self.assertEqual(self.client.get("/api/erp/portal/teacher/grades/Grade%20X/students", headers=self.teacher).status_code, 200)
        self.assertEqual(self.client.get("/api/erp/portal/teacher/grades/Grade%20Y/students", headers=self.teacher).status_code, 403)
        self.assertEqual(self.client.get("/api/erp/portal/teachers", headers=self.parent).status_code, 403)

    def test_report_cards_only_published_and_auth_required(self):
        conn = database.get_db()
        now = database._ist_now()
        draft = conn.execute(
            "INSERT INTO erp_exams(name, grade, status, created_at, updated_at) VALUES ('Draft', 'Grade X', 'scheduled', ?, ?)",
            (now, now),
        ).lastrowid
        published = conn.execute(
            "INSERT INTO erp_exams(name, grade, status, created_at, updated_at) VALUES ('Published', 'Grade X', 'published', ?, ?)",
            (now, now),
        ).lastrowid
        conn.commit()
        conn.close()
        result = self.client.get(f"/api/erp/portal/children/{self.child_a}/report-cards", headers=self.parent)
        self.assertEqual(result.status_code, 200)
        self.assertEqual([x["id"] for x in result.json()["exams"]], [published])
        self.assertIn(self.client.get("/api/erp/portal/me").status_code, (401, 403))
        self.assertNotEqual(draft, published)


if __name__ == "__main__":
    unittest.main()
