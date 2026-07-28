import tempfile
import unittest
from pathlib import Path

from fastapi.testclient import TestClient

from app import database
from app.main import app
from app.routes.auth import create_token


class ErpTransportTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.old_db, self.old_pi = database.DB_PATH, database.PI_SHEET_PATH
        database.DB_PATH = str(Path(self.tmp.name) / "transport.db")
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
               VALUES ('Transport Student', 'Grade 4A', 'active', 'test', ?, ?)""",
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

    def _route_with_stop(self):
        route = self.client.post(
            "/api/erp/transport/routes",
            headers=self.admin,
            json={"name": "North Route", "capacity": 40},
        )
        self.assertEqual(route.status_code, 201)
        stop = self.client.post(
            f"/api/erp/transport/routes/{route.json()['id']}/stops",
            headers=self.admin,
            json={"name": "Main Gate", "stop_order": 1, "monthly_fee": 1250.125},
        )
        self.assertEqual(stop.status_code, 201)
        self.assertEqual(stop.json()["monthly_fee"], 1250.13)
        return route.json(), stop.json()

    def test_route_stop_assignment_lifecycle(self):
        route, stop = self._route_with_stop()
        assignment = self.client.post(
            "/api/erp/transport/assignments",
            headers=self.admin,
            json={"student_id": self.student_id, "route_id": route["id"], "stop_id": stop["id"]},
        )
        self.assertEqual(assignment.status_code, 201)
        duplicate = self.client.post(
            "/api/erp/transport/assignments",
            headers=self.admin,
            json={"student_id": self.student_id, "route_id": route["id"], "stop_id": stop["id"]},
        )
        self.assertEqual(duplicate.status_code, 400)
        blocked_delete = self.client.delete(
            f"/api/erp/transport/stops/{stop['id']}", headers=self.admin
        )
        self.assertEqual(blocked_delete.status_code, 400)
        ended = self.client.post(
            f"/api/erp/transport/assignments/{assignment.json()['id']}/end",
            headers=self.admin,
        )
        self.assertEqual(ended.status_code, 200)
        reassigned = self.client.post(
            "/api/erp/transport/assignments",
            headers=self.admin,
            json={"student_id": self.student_id, "route_id": route["id"], "stop_id": stop["id"]},
        )
        self.assertEqual(reassigned.status_code, 201)

    def test_stop_route_validation_and_parent_forbidden(self):
        route, stop = self._route_with_stop()
        other_route = self.client.post(
            "/api/erp/transport/routes",
            headers=self.admin,
            json={"name": "South Route"},
        ).json()
        invalid = self.client.post(
            "/api/erp/transport/assignments",
            headers=self.admin,
            json={"student_id": self.student_id, "route_id": other_route["id"], "stop_id": stop["id"]},
        )
        self.assertEqual(invalid.status_code, 400)
        forbidden = self.client.get(
            "/api/erp/transport/routes", headers=self._parent_headers()
        )
        self.assertEqual(forbidden.status_code, 403)


if __name__ == "__main__":
    unittest.main()
