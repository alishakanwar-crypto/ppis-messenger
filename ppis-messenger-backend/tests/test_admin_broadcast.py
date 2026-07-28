import asyncio
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient

from app import database
from app.main import app
from app.routes import admin
from app.routes.auth import create_token
from app.services import whatsapp


class AdminBroadcastTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.original_db_path = database.DB_PATH
        self.original_pi_path = database.PI_SHEET_PATH
        self.original_sender = admin.send_announcement
        database.DB_PATH = str(Path(self.directory.name) / "broadcast.db")
        database.PI_SHEET_PATH = str(Path(self.directory.name) / "missing.json")
        database.init_db()
        database.seed_school_data()

        conn = database.get_db()
        conn.executemany(
            "INSERT INTO users (phone, name, role) VALUES (?, ?, 'parent')",
            [
                ("9000000001", "Parent One"),
                ("", "Parent Without Phone"),
                ("9000000002", "Parent Two"),
            ],
        )
        conn.commit()
        admin_user = conn.execute(
            "SELECT id, phone, role FROM users WHERE role = 'admin' LIMIT 1"
        ).fetchone()
        conn.close()

        self.client_context = TestClient(app)
        self.client = self.client_context.__enter__()
        token = create_token(
            admin_user["id"], admin_user["role"], admin_user["phone"]
        )
        self.headers = {"Authorization": f"Bearer {token}"}

    def tearDown(self):
        admin.send_announcement = self.original_sender
        self.client_context.__exit__(None, None, None)
        database.DB_PATH = self.original_db_path
        database.PI_SHEET_PATH = self.original_pi_path
        self.directory.cleanup()

    def test_broadcast_sends_whatsapp_to_parents_with_phones(self):
        calls = []

        async def fake_send(phone, message):
            calls.append((phone, message))
            return True

        admin.send_announcement = fake_send
        response = self.client.post(
            "/api/admin/broadcast",
            headers=self.headers,
            json={
                "title": "Holiday",
                "content": "School is closed tomorrow.",
                "target_grades": [],
            },
        )

        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertTrue(data["success"])
        self.assertEqual(data["sent_count"], 3)
        self.assertEqual(data["recipients_count"], 3)
        self.assertEqual(data["whatsapp_sent"], 2)
        self.assertEqual(data["whatsapp_failed"], 0)
        self.assertEqual(
            {phone for phone, _message in calls},
            {"9000000001", "9000000002"},
        )
        self.assertTrue(all(message == "Holiday: School is closed tomorrow." for _phone, message in calls))

    def test_broadcast_counts_failed_whatsapp_delivery_without_failing(self):
        async def fake_send(phone, message):
            return phone == "9000000001"

        admin.send_announcement = fake_send
        response = self.client.post(
            "/api/admin/broadcast",
            headers=self.headers,
            json={
                "title": "Reminder",
                "content": "Please check the school app.",
                "target_grades": [],
            },
        )

        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertTrue(data["success"])
        self.assertEqual(data["whatsapp_sent"], 1)
        self.assertEqual(data["whatsapp_failed"], 1)

    def test_announcement_sanitizes_template_variable_whitespace(self):
        captured = {}

        class FakeResponse:
            status_code = 200

            @staticmethod
            def json():
                return {"messages": [{"id": "message-id"}]}

        class FakeClient:
            async def __aenter__(self):
                return self

            async def __aexit__(self, exc_type, exc_value, traceback):
                return False

            async def post(self, url, headers, json, timeout):
                captured["url"] = url
                captured["headers"] = headers
                captured["payload"] = json
                captured["timeout"] = timeout
                return FakeResponse()

        with patch.dict(
            os.environ,
            {"WHATSAPP_CLOUD_TOKEN": "test-token", "WHATSAPP_PHONE_ID": "123"},
        ):
            with patch.object(whatsapp.httpx, "AsyncClient", return_value=FakeClient()):
                result = asyncio.run(
                    whatsapp.send_announcement(
                        "9000000001",
                        "  Holiday:\n\tSchool is closed.   Please plan ahead.  ",
                    )
                )

        self.assertTrue(result)
        self.assertEqual(captured["payload"]["to"], "919000000001")
        template = captured["payload"]["template"]
        self.assertEqual(template["name"], "ppis_school_announcement")
        body = template["components"][0]["parameters"][0]["text"]
        self.assertEqual(body, "Holiday: School is closed. Please plan ahead.")
        self.assertNotIn("\n", body)
        self.assertNotIn("\t", body)


if __name__ == "__main__":
    unittest.main()
