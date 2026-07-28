import tempfile
import unittest
from pathlib import Path

from fastapi.testclient import TestClient

from app import database
from app.main import app
from app.routes.auth import create_token


class ErpInventoryTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.old_db, self.old_pi = database.DB_PATH, database.PI_SHEET_PATH
        database.DB_PATH = str(Path(self.tmp.name) / "inventory.db")
        database.PI_SHEET_PATH = str(Path(self.tmp.name) / "missing.json")
        self.context = TestClient(app)
        self.client = self.context.__enter__()
        db = database.get_db()
        admin = db.execute("SELECT id, phone, role FROM users WHERE role = 'admin' LIMIT 1").fetchone()
        self.admin = {"Authorization": f"Bearer {create_token(admin['id'], admin['role'], admin['phone'])}"}
        db.close()

    def tearDown(self):
        self.context.__exit__(None, None, None)
        database.DB_PATH, database.PI_SHEET_PATH = self.old_db, self.old_pi
        self.tmp.cleanup()

    def _parent_headers(self):
        db = database.get_db()
        db.execute("INSERT INTO users(phone, name, role) VALUES ('9000000000', 'Test Parent', 'parent')")
        db.commit()
        parent = db.execute("SELECT id, phone, role FROM users WHERE phone = '9000000000'").fetchone()
        db.close()
        return {"Authorization": f"Bearer {create_token(parent['id'], parent['role'], parent['phone'])}"}

    def _item(self):
        category = self.client.post("/api/erp/inventory/categories", headers=self.admin, json={"name": "Stationery"})
        self.assertEqual(category.status_code, 201)
        item = self.client.post(
            "/api/erp/inventory/items",
            headers=self.admin,
            json={"name": "Notebook", "category_id": category.json()["id"], "unit_cost": 12.345, "reorder_level": 3},
        )
        self.assertEqual(item.status_code, 201)
        self.assertRegex(item.json()["sku"], r"^ITM-\d+$")
        self.assertEqual(item.json()["unit_cost"], 12.35)
        return item.json()

    def test_category_item_and_stock_lifecycle(self):
        self._item()
        duplicate = self.client.post("/api/erp/inventory/categories", headers=self.admin, json={"name": "stationery"})
        self.assertIn(duplicate.status_code, (400, 409))
        item = self.client.get("/api/erp/inventory/items?low_stock=true", headers=self.admin).json()["items"][0]
        in_txn = self.client.post(
            f"/api/erp/inventory/items/{item['id']}/transaction",
            headers=self.admin, json={"txn_type": "in", "quantity": 10},
        )
        self.assertEqual(in_txn.json()["quantity"], 10)
        out = self.client.post(
            f"/api/erp/inventory/items/{item['id']}/transaction",
            headers=self.admin, json={"txn_type": "out", "quantity": 4},
        )
        self.assertEqual(out.json()["quantity"], 6)
        beyond = self.client.post(
            f"/api/erp/inventory/items/{item['id']}/transaction",
            headers=self.admin, json={"txn_type": "out", "quantity": 7},
        )
        self.assertEqual(beyond.status_code, 400)
        adjust = self.client.post(
            f"/api/erp/inventory/items/{item['id']}/transaction",
            headers=self.admin, json={"txn_type": "adjust", "new_quantity": 2},
        )
        self.assertEqual(adjust.json()["quantity"], 2)
        self.assertEqual(adjust.json()["transaction"]["quantity"], -4)
        invalid = self.client.post(
            f"/api/erp/inventory/items/{item['id']}/transaction",
            headers=self.admin, json={"txn_type": "bad", "quantity": 1},
        )
        self.assertEqual(invalid.status_code, 400)

    def test_parent_forbidden(self):
        response = self.client.get("/api/erp/inventory/categories", headers=self._parent_headers())
        self.assertEqual(response.status_code, 403)


if __name__ == "__main__":
    unittest.main()
