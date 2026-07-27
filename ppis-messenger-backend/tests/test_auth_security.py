import asyncio
import hashlib
import tempfile
import unittest
from pathlib import Path

from fastapi import HTTPException

from app import database
from app.routes import auth


class AuthSecurityTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.original_db_path = database.DB_PATH
        self.original_pi_path = database.PI_SHEET_PATH
        self.original_bootstrap_phone = auth.ADMIN_BOOTSTRAP_PHONE
        self.original_bootstrap_pin = auth.ADMIN_BOOTSTRAP_PIN
        self.original_demo_otp = auth.DEMO_OTP_ENABLED
        self.original_max_failures = auth.LOGIN_MAX_FAILURES
        database.DB_PATH = str(Path(self.directory.name) / "auth.db")
        database.PI_SHEET_PATH = str(Path(self.directory.name) / "missing.json")
        auth._failed_pin_attempts.clear()
        database.init_db()
        database.seed_school_data()

    def tearDown(self):
        database.DB_PATH = self.original_db_path
        database.PI_SHEET_PATH = self.original_pi_path
        auth.ADMIN_BOOTSTRAP_PHONE = self.original_bootstrap_phone
        auth.ADMIN_BOOTSTRAP_PIN = self.original_bootstrap_pin
        auth.DEMO_OTP_ENABLED = self.original_demo_otp
        auth.LOGIN_MAX_FAILURES = self.original_max_failures
        auth._failed_pin_attempts.clear()
        self.directory.cleanup()

    def test_scrypt_passcodes_and_legacy_hashes_are_supported(self):
        pin_hash = auth._hash_pin("secure-passcode")
        self.assertTrue(pin_hash.startswith("scrypt$"))
        self.assertTrue(auth._verify_pin("secure-passcode", pin_hash))
        self.assertFalse(auth._verify_pin("wrong-passcode", pin_hash))

        legacy_hash = hashlib.sha256(b"1234").hexdigest()
        self.assertTrue(auth._verify_pin("1234", legacy_hash))

    def test_demo_otp_is_disabled_by_default(self):
        auth.DEMO_OTP_ENABLED = False
        with self.assertRaises(HTTPException) as context:
            asyncio.run(auth.request_otp(auth.PhoneRequest(phone="9000000000")))
        self.assertEqual(context.exception.status_code, 404)

    def test_bootstrap_admin_passcode_and_throttle_failed_logins(self):
        conn = database.get_db()
        admin = conn.execute(
            "SELECT phone FROM users WHERE role = 'admin' ORDER BY id LIMIT 1"
        ).fetchone()
        conn.close()

        auth.ADMIN_BOOTSTRAP_PHONE = admin["phone"]
        auth.ADMIN_BOOTSTRAP_PIN = "secure-passcode"
        auth.bootstrap_admin_pin()

        result = asyncio.run(
            auth.login_pin(
                auth.LoginPinRequest(phone=admin["phone"], pin="secure-passcode")
            )
        )
        self.assertEqual(result["user"]["role"], "admin")

        auth.LOGIN_MAX_FAILURES = 2
        for _ in range(2):
            with self.assertRaises(HTTPException) as context:
                asyncio.run(
                    auth.login_pin(
                        auth.LoginPinRequest(phone=admin["phone"], pin="wrong-passcode")
                    )
                )
            self.assertEqual(context.exception.status_code, 400)

        with self.assertRaises(HTTPException) as context:
            asyncio.run(
                auth.login_pin(
                    auth.LoginPinRequest(phone=admin["phone"], pin="secure-passcode")
                )
            )
        self.assertEqual(context.exception.status_code, 429)


if __name__ == "__main__":
    unittest.main()
