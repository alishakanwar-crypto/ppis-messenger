import json
import tempfile
import unittest
from pathlib import Path

from app import database


class ErpRosterResyncTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        root = Path(self.tmp.name)
        self.old_db = database.DB_PATH
        self.old_pi = database.PI_SHEET_PATH
        database.DB_PATH = str(root / "resync.db")
        database.PI_SHEET_PATH = str(root / "roster.json")
        database.init_db()
        conn = database.get_db()
        now = database._ist_now()
        conn.execute(
            """INSERT INTO erp_students
               (admission_number,full_name,grade,transport,status,source,created_at,updated_at)
               VALUES ('','Alice Example','Grade 1A','No','active','pi_sheet',?,?)""",
            (now, now),
        )
        guardian = conn.execute(
            "INSERT INTO erp_guardians(full_name,phone,created_at,updated_at) VALUES (?,?,?,?)",
            ("ALICE FATHER", "9000000001", now, now),
        ).lastrowid
        conn.execute(
            "INSERT INTO erp_student_guardians(student_id,guardian_id,relationship,is_primary) VALUES (1,?,?,1)",
            (guardian, "father"),
        )
        conn.execute(
            """INSERT INTO erp_students
               (admission_number,full_name,grade,transport,status,source,created_at,updated_at)
               VALUES ('OLD-2','Bob Example','Grade 2A','Route 1','active','pi_sheet',?,?)""",
            (now, now),
        )
        conn.execute(
            """INSERT INTO erp_students
               (admission_number,full_name,grade,transport,status,source,created_at,updated_at)
               VALUES ('KEEP-3','Carol Example','Grade 3A','No','active','pi_sheet',?,?)""",
            (now, now),
        )
        conn.commit()
        conn.close()

        Path(database.PI_SHEET_PATH).write_text(
            json.dumps(
                [
                    {
                        "student": "Alice Example", "admission_number": "A-1",
                        "grade": "Grade 2A", "gender": "Female", "dob": "01.01.2018",
                        "father": "Alice Father", "father_mobile": "9000000001",
                        "transport": "Route 2", "address": "New Delhi",
                    },
                    {
                        "student": "Carol Example", "admission_number": "KEEP-3",
                        "grade": "Grade 3A", "transport": "No",
                    },
                    {
                        "student": "New Example", "admission_number": "NEW-4",
                        "grade": "Grade 4A", "transport": "Self",
                        "father": "New Father", "father_mobile": "919000000004",
                        "mother": "New Mother", "mother_mobile": "91 9000000005",
                    },
                ]
            ),
            encoding="utf-8",
        )

    def tearDown(self):
        database.DB_PATH = self.old_db
        database.PI_SHEET_PATH = self.old_pi
        self.tmp.cleanup()

    def test_dry_run_does_not_write_and_reports_changes(self):
        result = database.resync_erp_students_from_pi_sheet(dry_run=True)
        self.assertEqual(result["matched_updated"], 1)
        self.assertEqual(result["grade_promotions"], 1)
        self.assertEqual(result["new_inserts"], 1)
        self.assertEqual(result["not_in_current_sheet"], 1)
        self.assertEqual(result["match_methods"]["name_parent_phone"], 1)
        conn = database.get_db()
        self.assertEqual(conn.execute("SELECT COUNT(*) FROM erp_students").fetchone()[0], 3)
        self.assertEqual(conn.execute("SELECT COUNT(*) FROM erp_audit_log").fetchone()[0], 0)
        conn.close()

    def test_apply_updates_inserts_without_withdrawal_and_is_idempotent(self):
        database.resync_erp_students_from_pi_sheet(dry_run=False)
        conn = database.get_db()
        alice = conn.execute(
            "SELECT * FROM erp_students WHERE full_name='Alice Example'"
        ).fetchone()
        self.assertEqual(alice["admission_number"], "A-1")
        self.assertEqual(alice["grade"], "Grade 2A")
        self.assertEqual(alice["status"], "active")
        self.assertEqual(
            conn.execute("SELECT status FROM erp_students WHERE full_name='Bob Example'").fetchone()["status"],
            "active",
        )
        self.assertIsNotNone(
            conn.execute("SELECT id FROM erp_students WHERE full_name='New Example'").fetchone()
        )
        guardians = conn.execute(
            """SELECT g.full_name, g.phone, sg.relationship
               FROM erp_student_guardians sg
               JOIN erp_guardians g ON g.id = sg.guardian_id
               JOIN erp_students s ON s.id = sg.student_id
               WHERE s.full_name = 'New Example'
               ORDER BY sg.relationship"""
        ).fetchall()
        self.assertEqual(
            [(row["full_name"], row["phone"], row["relationship"]) for row in guardians],
            [
                ("New Father", "9000000004", "father"),
                ("New Mother", "9000000005", "mother"),
            ],
        )
        audits = conn.execute("SELECT COUNT(*) FROM erp_audit_log").fetchone()[0]
        conn.close()
        second = database.resync_erp_students_from_pi_sheet(dry_run=True)
        self.assertEqual(second["matched_updated"], 0)
        self.assertEqual(second["new_inserts"], 0)
        self.assertEqual(second["not_in_current_sheet"], 1)
        conn = database.get_db()
        self.assertEqual(conn.execute("SELECT COUNT(*) FROM erp_audit_log").fetchone()[0], audits)
        conn.close()


if __name__ == "__main__":
    unittest.main()
