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

    def test_login_status_reports_allow_list_and_pin_state(self):
        new_admin = asyncio.run(
            auth.login_status(auth.LoginStatusRequest(phone="9599488105"))
        )
        self.assertEqual(new_admin, {"authorized": True, "has_pin": False})

        conn = database.get_db()
        conn.execute(
            "UPDATE users SET pin_hash = ? WHERE phone = ?",
            (auth._hash_pin("secure-passcode"), "8076455224"),
        )
        conn.commit()
        conn.close()

        configured_admin = asyncio.run(
            auth.login_status(auth.LoginStatusRequest(phone="8076455224"))
        )
        self.assertEqual(configured_admin, {"authorized": True, "has_pin": True})

        unauthorized = asyncio.run(
            auth.login_status(auth.LoginStatusRequest(phone="9000000000"))
        )
        self.assertEqual(unauthorized, {"authorized": False, "has_pin": False})

    def test_setup_pin_creates_admin_and_logs_in(self):
        result = asyncio.run(
            auth.setup_pin(
                auth.LoginPinRequest(phone="9599488105", pin="secure-passcode")
            )
        )
        self.assertTrue(result["success"])
        self.assertTrue(result["token"])
        self.assertEqual(result["user"]["phone"], "9599488105")
        self.assertEqual(result["user"]["role"], "admin")
        self.assertTrue(result["user"]["has_pin"])

        conn = database.get_db()
        user = conn.execute(
            "SELECT role, pin_hash FROM users WHERE phone = ?", ("9599488105",)
        ).fetchone()
        conn.close()
        self.assertEqual(user["role"], "admin")
        self.assertTrue(user["pin_hash"])

    def test_setup_pin_rejects_unauthorized_phone(self):
        with self.assertRaises(HTTPException) as context:
            asyncio.run(
                auth.setup_pin(
                    auth.LoginPinRequest(phone="9000000000", pin="secure-passcode")
                )
            )
        self.assertEqual(context.exception.status_code, 403)
        self.assertEqual(
            context.exception.detail,
            "This number is not authorized to access the ERP",
        )

    def test_setup_pin_rejects_existing_pin(self):
        asyncio.run(
            auth.setup_pin(
                auth.LoginPinRequest(phone="9599488105", pin="secure-passcode")
            )
        )
        with self.assertRaises(HTTPException) as context:
            asyncio.run(
                auth.setup_pin(
                    auth.LoginPinRequest(phone="9599488105", pin="another-passcode")
                )
            )
        self.assertEqual(context.exception.status_code, 400)
        self.assertEqual(
            context.exception.detail,
            "Passcode already set. Please log in.",
        )

    def test_setup_pin_rejects_short_pin(self):
        with self.assertRaises(HTTPException) as context:
            asyncio.run(
                auth.setup_pin(
                    auth.LoginPinRequest(phone="9599488105", pin="short")
                )
            )
        self.assertEqual(context.exception.status_code, 400)
        self.assertEqual(
            context.exception.detail,
            f"Passcode must be at least {auth.PIN_MIN_LENGTH} characters",
        )

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
