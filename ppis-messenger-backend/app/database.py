"""SQLite database for PPIS Messenger."""

import hashlib
import json
import logging
import os
import re
import sqlite3
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import openpyxl

logger = logging.getLogger(__name__)
IST = ZoneInfo("Asia/Kolkata")

DB_PATH = os.environ.get("DB_PATH", "/data/app.db")
# Fallback for local dev
if not os.path.isdir(os.path.dirname(DB_PATH)):
    DB_PATH = os.path.join(os.path.dirname(__file__), "..", "messenger.db")

PI_SHEET_PATH = os.environ.get(
    "PI_SHEET_PATH",
    os.path.join(os.path.dirname(__file__), "..", "pi_sheet_data.json"),
)

EXCEL_PATH = os.environ.get(
    "EXCEL_PATH",
    os.path.join(os.path.dirname(__file__), "..", "pi_academic_session.xlsx"),
)

TEACHER_DATA = [
    {"name": "Gargi Arora", "grade": "Grade 1A", "email": "gargi.arora@ppischool.in", "phone": "9289234659"},
    {"name": "Gargi Arora", "grade": "Grade 1B", "email": "gargi.arora@ppischool.in", "phone": "9289234659"},
    {"name": "Prabhjot Kaur", "grade": "Grade 1C", "email": "prabhjot.kaur@ppischool.in", "phone": "9289234663"},
    {"name": "Gargi Arora", "grade": "Grade 2A", "email": "gargi.arora@ppischool.in", "phone": "9289234659"},
    {"name": "Gargi Arora", "grade": "Grade 2B", "email": "gargi.arora@ppischool.in", "phone": "9289234659"},
    {"name": "Harnoor Kaur", "grade": "Grade 3A", "email": "harnoor.kaur@ppischool.in", "phone": "9289234659"},
    {"name": "Seema Bakshi", "grade": "Grade 3B", "email": "seema.bakshi@ppischool.in", "phone": "9650416484"},
    {"name": "Harnoor Kaur", "grade": "Grade 3C", "email": "harnoor.kaur@ppischool.in", "phone": "9289234659"},
    {"name": "Prabhjot Kaur", "grade": "Grade 4A", "email": "prabhjot.kaur@ppischool.in", "phone": "9289234663"},
    {"name": "Prabhjot Kaur", "grade": "Grade 4B", "email": "prabhjot.kaur@ppischool.in", "phone": "9289234663"},
    {"name": "Poshika Narula", "grade": "Grade 5A", "email": "poshika.narula@ppischool.in", "phone": "9810285455"},
    {"name": "Poshika Narula", "grade": "Grade 5B", "email": "poshika.narula@ppischool.in", "phone": "9810285455"},
    {"name": "Rashmi", "grade": "Grade 6A", "email": "rashmi@ppischool.in", "phone": "9560190606"},
    {"name": "Rashmi", "grade": "Grade 6B", "email": "rashmi@ppischool.in", "phone": "9560190606"},
    {"name": "Shyam Manohar", "grade": "Grade 7A", "email": "shyam.manohar@ppischool.in", "phone": "9560892325"},
    {"name": "Shyam Manohar", "grade": "Grade 7B", "email": "shyam.manohar@ppischool.in", "phone": "9560892325"},
    {"name": "Tarun Dhall", "grade": "Grade 8A", "email": "tarun.dhall@ppischool.in", "phone": "8586001734"},
    {"name": "Rashmi", "grade": "Grade 8B", "email": "rashmi@ppischool.in", "phone": "9560190606"},
    {"name": "Rashmi", "grade": "Grade 8C", "email": "rashmi@ppischool.in", "phone": "9560190606"},
    {"name": "Reva Rajput", "grade": "Grade 9A", "email": "reva.rajput@ppischool.in", "phone": "9911456710"},
    {"name": "Reva Rajput", "grade": "Grade 9B", "email": "reva.rajput@ppischool.in", "phone": "9911456710"},
    {"name": "Reva Rajput", "grade": "Grade 9C", "email": "reva.rajput@ppischool.in", "phone": "9911456710"},
    {"name": "Jasleen Kaur", "grade": "Grade 10A", "email": "jasleen.kaur@ppischool.in", "phone": "8586001734"},
    {"name": "Jasleen Kaur", "grade": "Grade 10B", "email": "jasleen.kaur@ppischool.in", "phone": "8586001734"},
    {"name": "Aradhana Gambhir", "grade": "Grade 11 Science", "email": "aradhana.gambhir@ppischool.in", "phone": ""},
    {"name": "Christy Joseph", "grade": "Grade 11 Commerce", "email": "christy.joseph@ppischool.in", "phone": "9953131342"},
    {"name": "Sucheta Sinha", "grade": "Grade 12 Commerce", "email": "sucheta.sinha@ppischool.in", "phone": "9910933523"},
    {"name": "Sucheta Sinha", "grade": "Grade 12 Humanities", "email": "sucheta.sinha@ppischool.in", "phone": "9910933523"},
    {"name": "Priyanka Budhiraja / Geet", "grade": "Nursery 1", "email": "priyanka.budhiraja@ppischool.in", "phone": "9818704015"},
    {"name": "Priyanka Budhiraja / Geet", "grade": "Nursery 2", "email": "priyanka.budhiraja@ppischool.in", "phone": "9818704015"},
    {"name": "Priyanka Budhiraja / Geet", "grade": "Nursery 3", "email": "priyanka.budhiraja@ppischool.in", "phone": "9818704015"},
    {"name": "Meenu Saini", "grade": "Prep 1", "email": "meenu.saini@ppischool.in", "phone": "9899976578"},
    {"name": "Meenu Saini", "grade": "Prep 2", "email": "meenu.saini@ppischool.in", "phone": "9899976578"},
    {"name": "Meenu Saini", "grade": "Prep 3", "email": "meenu.saini@ppischool.in", "phone": "9899976578"},
    {"name": "Priyanka Budhiraja / Geet", "grade": "Popsicles", "email": "priyanka.budhiraja@ppischool.in", "phone": "9818704015"},
]

ADMIN_NUMBERS = ["9971166562", "9910034550", "9599488106", "8076455224"]


def get_db() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


def init_db():
    """Create tables."""
    conn = get_db()
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            phone TEXT UNIQUE NOT NULL,
            name TEXT NOT NULL DEFAULT '',
            role TEXT NOT NULL DEFAULT 'parent',
            pin_hash TEXT DEFAULT '',
            grade TEXT DEFAULT '',
            children TEXT DEFAULT '[]',
            avatar_url TEXT DEFAULT '',
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            last_seen DATETIME DEFAULT CURRENT_TIMESTAMP,
            is_active INTEGER DEFAULT 1
        );

        CREATE TABLE IF NOT EXISTS student_photos (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            student_name TEXT NOT NULL,
            grade TEXT NOT NULL,
            photo_data TEXT NOT NULL,
            uploaded_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(student_name, grade)
        );

        CREATE TABLE IF NOT EXISTS erp_students (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            admission_number TEXT NOT NULL DEFAULT '',
            full_name TEXT NOT NULL,
            grade TEXT NOT NULL,
            date_of_birth TEXT NOT NULL DEFAULT '',
            gender TEXT NOT NULL DEFAULT '',
            address TEXT NOT NULL DEFAULT '',
            transport TEXT NOT NULL DEFAULT '',
            status TEXT NOT NULL DEFAULT 'active',
            source TEXT NOT NULL DEFAULT 'manual',
            source_key TEXT NOT NULL DEFAULT '',
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS erp_guardians (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            full_name TEXT NOT NULL DEFAULT '',
            phone TEXT NOT NULL DEFAULT '',
            email TEXT NOT NULL DEFAULT '',
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        );

        CREATE UNIQUE INDEX IF NOT EXISTS idx_erp_guardians_identity
            ON erp_guardians(phone, full_name) WHERE phone != '';

        CREATE TABLE IF NOT EXISTS erp_student_guardians (
            student_id INTEGER NOT NULL REFERENCES erp_students(id) ON DELETE CASCADE,
            guardian_id INTEGER NOT NULL REFERENCES erp_guardians(id) ON DELETE CASCADE,
            relationship TEXT NOT NULL DEFAULT 'guardian',
            is_primary INTEGER NOT NULL DEFAULT 0,
            PRIMARY KEY (student_id, guardian_id)
        );

        CREATE TABLE IF NOT EXISTS erp_audit_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            actor_user_id INTEGER REFERENCES users(id),
            action TEXT NOT NULL,
            entity_type TEXT NOT NULL,
            entity_id INTEGER,
            details TEXT NOT NULL DEFAULT '{}',
            created_at TEXT NOT NULL
        );

        CREATE UNIQUE INDEX IF NOT EXISTS idx_erp_students_admission
            ON erp_students(admission_number) WHERE admission_number != '';
        CREATE UNIQUE INDEX IF NOT EXISTS idx_erp_students_source_key
            ON erp_students(source_key) WHERE source_key != '';
        CREATE INDEX IF NOT EXISTS idx_erp_students_grade
            ON erp_students(grade);
        CREATE INDEX IF NOT EXISTS idx_erp_students_status
            ON erp_students(status);
        CREATE INDEX IF NOT EXISTS idx_erp_audit_created
            ON erp_audit_log(created_at);

        CREATE TABLE IF NOT EXISTS groups_ (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            grade TEXT DEFAULT '',
            type TEXT NOT NULL DEFAULT 'class',
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS group_members (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            group_id INTEGER NOT NULL REFERENCES groups_(id),
            user_id INTEGER NOT NULL REFERENCES users(id),
            role TEXT DEFAULT 'member',
            UNIQUE(group_id, user_id)
        );

        CREATE TABLE IF NOT EXISTS messages (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            sender_id INTEGER NOT NULL REFERENCES users(id),
            group_id INTEGER REFERENCES groups_(id),
            recipient_id INTEGER REFERENCES users(id),
            content TEXT NOT NULL DEFAULT '',
            message_type TEXT DEFAULT 'text',
            media_url TEXT DEFAULT '',
            media_filename TEXT DEFAULT '',
            reply_to_id INTEGER REFERENCES messages(id),
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            is_bot INTEGER DEFAULT 0
        );

        CREATE TABLE IF NOT EXISTS read_receipts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            message_id INTEGER NOT NULL REFERENCES messages(id),
            user_id INTEGER NOT NULL REFERENCES users(id),
            read_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(message_id, user_id)
        );

        CREATE TABLE IF NOT EXISTS broadcasts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            sender_id INTEGER NOT NULL REFERENCES users(id),
            title TEXT NOT NULL,
            content TEXT NOT NULL,
            target_grades TEXT DEFAULT '[]',
            media_url TEXT DEFAULT '',
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS otp_codes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            phone TEXT NOT NULL,
            code TEXT NOT NULL,
            expires_at DATETIME NOT NULL,
            used INTEGER DEFAULT 0
        );

        CREATE INDEX IF NOT EXISTS idx_messages_group ON messages(group_id);
        CREATE INDEX IF NOT EXISTS idx_messages_sender ON messages(sender_id);
        CREATE INDEX IF NOT EXISTS idx_messages_recipient ON messages(recipient_id);
        CREATE INDEX IF NOT EXISTS idx_messages_created ON messages(created_at);
        CREATE INDEX IF NOT EXISTS idx_users_phone ON users(phone);
        CREATE INDEX IF NOT EXISTS idx_student_photos_name ON student_photos(student_name);
        CREATE INDEX IF NOT EXISTS idx_student_photos_grade ON student_photos(grade);
        CREATE INDEX IF NOT EXISTS idx_group_members_group ON group_members(group_id);
        CREATE INDEX IF NOT EXISTS idx_group_members_user ON group_members(user_id);

        CREATE TABLE IF NOT EXISTS erp_academic_sessions (
            id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT NOT NULL UNIQUE,
            start_date TEXT NOT NULL, end_date TEXT NOT NULL,
            is_current INTEGER NOT NULL DEFAULT 0 CHECK(is_current IN (0,1)),
            created_at TEXT NOT NULL, updated_at TEXT NOT NULL
        );
        CREATE UNIQUE INDEX IF NOT EXISTS idx_erp_current_session
            ON erp_academic_sessions(is_current) WHERE is_current = 1;
        CREATE TABLE IF NOT EXISTS erp_fee_heads (
            id INTEGER PRIMARY KEY AUTOINCREMENT, code TEXT NOT NULL UNIQUE,
            name TEXT NOT NULL, is_refundable INTEGER NOT NULL DEFAULT 0 CHECK(is_refundable IN (0,1)),
            is_active INTEGER NOT NULL DEFAULT 1 CHECK(is_active IN (0,1))
        );
        CREATE TABLE IF NOT EXISTS erp_fee_structures (
            id INTEGER PRIMARY KEY AUTOINCREMENT, session_id INTEGER NOT NULL REFERENCES erp_academic_sessions(id),
            grade TEXT NOT NULL, frequency TEXT NOT NULL CHECK(frequency IN ('monthly','quarterly','annual','one_time')),
            status TEXT NOT NULL DEFAULT 'draft' CHECK(status IN ('draft','published','archived')),
            published_at TEXT, created_at TEXT NOT NULL, updated_at TEXT NOT NULL,
            UNIQUE(session_id, grade)
        );
        CREATE TABLE IF NOT EXISTS erp_fee_structure_items (
            id INTEGER PRIMARY KEY AUTOINCREMENT, structure_id INTEGER NOT NULL REFERENCES erp_fee_structures(id) ON DELETE CASCADE,
            fee_head_id INTEGER NOT NULL REFERENCES erp_fee_heads(id), amount_paise INTEGER NOT NULL CHECK(amount_paise >= 0),
            is_optional INTEGER NOT NULL DEFAULT 0 CHECK(is_optional IN (0,1)), UNIQUE(structure_id, fee_head_id)
        );
        CREATE TABLE IF NOT EXISTS erp_student_fee_plans (
            id INTEGER PRIMARY KEY AUTOINCREMENT, student_id INTEGER NOT NULL REFERENCES erp_students(id),
            session_id INTEGER NOT NULL REFERENCES erp_academic_sessions(id), structure_id INTEGER NOT NULL REFERENCES erp_fee_structures(id),
            transport_opted INTEGER NOT NULL DEFAULT 0 CHECK(transport_opted IN (0,1)),
            UNIQUE(student_id, session_id)
        );
        CREATE TABLE IF NOT EXISTS erp_concessions (
            id INTEGER PRIMARY KEY AUTOINCREMENT, student_id INTEGER NOT NULL REFERENCES erp_students(id),
            session_id INTEGER NOT NULL REFERENCES erp_academic_sessions(id), fee_head_id INTEGER REFERENCES erp_fee_heads(id),
            kind TEXT NOT NULL CHECK(kind IN ('percent','amount')), value INTEGER NOT NULL CHECK(value >= 0),
            reason TEXT NOT NULL, approved_by_user_id INTEGER REFERENCES users(id),
            status TEXT NOT NULL DEFAULT 'active' CHECK(status IN ('active','revoked')),
            created_at TEXT NOT NULL, updated_at TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS erp_invoices (
            id INTEGER PRIMARY KEY AUTOINCREMENT, invoice_number TEXT NOT NULL UNIQUE,
            student_id INTEGER NOT NULL REFERENCES erp_students(id), session_id INTEGER NOT NULL REFERENCES erp_academic_sessions(id),
            period_code TEXT NOT NULL, issue_date TEXT NOT NULL, due_date TEXT NOT NULL,
            gross_paise INTEGER NOT NULL CHECK(gross_paise >= 0), concession_paise INTEGER NOT NULL DEFAULT 0 CHECK(concession_paise >= 0),
            net_paise INTEGER NOT NULL CHECK(net_paise >= 0), paid_paise INTEGER NOT NULL DEFAULT 0 CHECK(paid_paise >= 0),
            status TEXT NOT NULL DEFAULT 'draft' CHECK(status IN ('draft','issued','partially_paid','paid','cancelled')),
            cancel_reason TEXT, idempotency_key TEXT, created_at TEXT NOT NULL, updated_at TEXT NOT NULL
        );
        CREATE UNIQUE INDEX IF NOT EXISTS idx_erp_invoice_period
            ON erp_invoices(student_id, session_id, period_code) WHERE status != 'cancelled';
        CREATE UNIQUE INDEX IF NOT EXISTS idx_erp_invoice_idempotency
            ON erp_invoices(idempotency_key) WHERE idempotency_key IS NOT NULL;
        CREATE INDEX IF NOT EXISTS idx_erp_invoice_status_due ON erp_invoices(status, due_date);
        CREATE TABLE IF NOT EXISTS erp_invoice_lines (
            id INTEGER PRIMARY KEY AUTOINCREMENT, invoice_id INTEGER NOT NULL REFERENCES erp_invoices(id) ON DELETE CASCADE,
            fee_head_id INTEGER REFERENCES erp_fee_heads(id), description TEXT NOT NULL,
            amount_paise INTEGER NOT NULL CHECK(amount_paise >= 0), concession_paise INTEGER NOT NULL DEFAULT 0 CHECK(concession_paise >= 0),
            concession_id INTEGER REFERENCES erp_concessions(id)
        );
        CREATE TABLE IF NOT EXISTS erp_payments (
            id INTEGER PRIMARY KEY AUTOINCREMENT, receipt_number TEXT NOT NULL UNIQUE,
            student_id INTEGER NOT NULL REFERENCES erp_students(id), session_id INTEGER NOT NULL REFERENCES erp_academic_sessions(id),
            amount_paise INTEGER NOT NULL CHECK(amount_paise > 0),
            method TEXT NOT NULL CHECK(method IN ('cash','cheque','neft','upi','dd','adjustment')),
            reference_last4 TEXT CHECK(length(reference_last4) <= 4), bank_label TEXT NOT NULL DEFAULT '',
            paid_at TEXT NOT NULL, status TEXT NOT NULL DEFAULT 'confirmed' CHECK(status IN ('confirmed','reversed')),
            reversal_reason TEXT, collected_by_user_id INTEGER REFERENCES users(id), idempotency_key TEXT UNIQUE,
            created_at TEXT NOT NULL, updated_at TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS erp_payment_allocations (
            id INTEGER PRIMARY KEY AUTOINCREMENT, payment_id INTEGER NOT NULL REFERENCES erp_payments(id) ON DELETE CASCADE,
            invoice_id INTEGER NOT NULL REFERENCES erp_invoices(id), amount_paise INTEGER NOT NULL CHECK(amount_paise > 0), created_at TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS erp_document_counters (scope TEXT PRIMARY KEY, next_value INTEGER NOT NULL);
        CREATE TABLE IF NOT EXISTS erp_teacher_grades (
            user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            grade TEXT NOT NULL,
            PRIMARY KEY(user_id, grade)
        );
        CREATE TABLE IF NOT EXISTS erp_exams (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            session_id INTEGER REFERENCES erp_academic_sessions(id),
            name TEXT NOT NULL,
            term TEXT NOT NULL DEFAULT '',
            grade TEXT NOT NULL DEFAULT '',
            max_marks REAL NOT NULL DEFAULT 100,
            exam_date TEXT NOT NULL DEFAULT '',
            status TEXT NOT NULL DEFAULT 'scheduled',
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS erp_exam_subjects (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            exam_id INTEGER NOT NULL REFERENCES erp_exams(id) ON DELETE CASCADE,
            subject TEXT NOT NULL,
            max_marks REAL NOT NULL DEFAULT 100,
            pass_marks REAL NOT NULL DEFAULT 33,
            created_at TEXT NOT NULL
        );
        CREATE INDEX IF NOT EXISTS idx_erp_exam_subjects_exam
            ON erp_exam_subjects(exam_id);
        CREATE TABLE IF NOT EXISTS erp_exam_marks (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            exam_id INTEGER NOT NULL REFERENCES erp_exams(id) ON DELETE CASCADE,
            subject_id INTEGER NOT NULL REFERENCES erp_exam_subjects(id) ON DELETE CASCADE,
            student_id INTEGER NOT NULL REFERENCES erp_students(id),
            marks_obtained REAL,
            is_absent INTEGER NOT NULL DEFAULT 0,
            remarks TEXT NOT NULL DEFAULT '',
            updated_by INTEGER REFERENCES users(id),
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        );
        CREATE UNIQUE INDEX IF NOT EXISTS idx_erp_exam_marks_subject_student
            ON erp_exam_marks(subject_id, student_id);
        CREATE INDEX IF NOT EXISTS idx_erp_exam_marks_exam
            ON erp_exam_marks(exam_id);
        CREATE TABLE IF NOT EXISTS erp_attendance (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            student_id INTEGER NOT NULL REFERENCES erp_students(id),
            session_id INTEGER NOT NULL REFERENCES erp_academic_sessions(id),
            date TEXT NOT NULL,
            status TEXT NOT NULL,
            remarks TEXT NOT NULL DEFAULT '',
            marked_by INTEGER REFERENCES users(id),
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        );
        CREATE UNIQUE INDEX IF NOT EXISTS idx_erp_attendance_student_date
            ON erp_attendance(student_id, date);
        CREATE INDEX IF NOT EXISTS idx_erp_attendance_date
            ON erp_attendance(date);
        CREATE INDEX IF NOT EXISTS idx_erp_attendance_session
            ON erp_attendance(session_id);
        CREATE TABLE IF NOT EXISTS erp_leave_requests (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            student_id INTEGER NOT NULL REFERENCES erp_students(id),
            session_id INTEGER NOT NULL REFERENCES erp_academic_sessions(id),
            from_date TEXT NOT NULL,
            to_date TEXT NOT NULL,
            leave_type TEXT NOT NULL,
            reason TEXT NOT NULL DEFAULT '',
            status TEXT NOT NULL DEFAULT 'pending',
            decided_by INTEGER REFERENCES users(id),
            decided_at TEXT,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        );
        CREATE INDEX IF NOT EXISTS idx_erp_leave_status
            ON erp_leave_requests(status);
        CREATE INDEX IF NOT EXISTS idx_erp_leave_student
            ON erp_leave_requests(student_id);
    """)
    # Migrations: add columns that might be missing on existing databases
    try:
        conn.execute("ALTER TABLE users ADD COLUMN avatar_url TEXT DEFAULT ''")
        logger.info("Added avatar_url column to users table")
    except sqlite3.OperationalError:
        pass  # Column already exists

    now = _ist_now()
    conn.execute("INSERT OR IGNORE INTO erp_academic_sessions(name,start_date,end_date,is_current,created_at,updated_at) VALUES ('2026-27','2026-04-01','2027-03-31',1,?,?)", (now, now))
    for code, name, refundable in (("TUITION","Tuition",0),("TRANSPORT","Transport",0),("ADMISSION","Admission",0),("ANNUAL","Annual",0),("EXAM","Exam",0)):
        conn.execute("INSERT OR IGNORE INTO erp_fee_heads(code,name,is_refundable,is_active) VALUES (?,?,?,1)", (code,name,refundable))
    conn.commit()
    conn.close()
    logger.info(f"Database initialized at {DB_PATH}")


def _normalize_phone(raw: str) -> str:
    """Normalize a phone number to 10-digit Indian format. Returns '' if invalid."""
    phone = str(raw).strip().replace(" ", "").replace("-", "").replace("+", "")
    # Handle float format from Excel (e.g. '9818311160.0')
    if "." in phone:
        phone = phone.split(".")[0]
    # Handle comma-separated numbers (e.g. '8368260266, 9899536166') — take first
    if "," in phone:
        phone = phone.split(",")[0].strip()
    # Remove country code prefix
    if phone.startswith("91") and len(phone) > 10:
        phone = phone[2:]
    if phone.startswith("0") and len(phone) == 11:
        phone = phone[1:]
    if len(phone) != 10 or not phone.isdigit():
        return ""
    return phone


def _upsert_parent(
    conn: sqlite3.Connection,
    phone: str,
    child_name: str,
    grade: str,
    parent_name: str,
) -> int:
    """Insert or update a parent record with child data. Returns 1 if new parent inserted, 0 otherwise."""
    existing = conn.execute(
        "SELECT id, children FROM users WHERE phone = ?", (phone,)
    ).fetchone()
    entry = {"name": child_name, "grade": grade}
    if existing:
        children = json.loads(existing["children"] or "[]")
        if entry not in children:
            children.append(entry)
            conn.execute(
                "UPDATE users SET children = ? WHERE id = ?",
                (json.dumps(children), existing["id"]),
            )
        return 0
    children_json = json.dumps([entry])
    conn.execute(
        "INSERT OR IGNORE INTO users (phone, name, role, grade, children) VALUES (?, ?, ?, ?, ?)",
        (phone, parent_name, "parent", grade, children_json),
    )
    return 1


def _seed_from_excel(conn: sqlite3.Connection, excel_path: Path) -> int:
    """Parse the PI Academic Session Excel file and seed parent-child relationships.

    The Excel has one sheet per grade (e.g. 'Grade 1A', 'Nursery 1', 'Popsicles 1').
    Each sheet has columns like: S.No., Admission No, STUDENT NAME, Grade,
    FATHER'S NAME, FATHER MOBILE NO., MOTHER NAME, MOTHER MOBILE NO.
    """
    wb = openpyxl.load_workbook(excel_path, read_only=True, data_only=True)
    new_parents = 0

    for sheet_name in wb.sheetnames:
        ws = wb[sheet_name]
        rows = list(ws.iter_rows(values_only=True))
        if not rows:
            continue

        # Find the header row (look for 'STUDENT NAME' or similar)
        header_idx = -1
        header_map: dict[str, int] = {}
        for i, row in enumerate(rows):
            row_str = [str(c).strip().upper() if c else "" for c in row]
            for j, cell in enumerate(row_str):
                if "STUDENT" in cell and "NAME" in cell:
                    header_idx = i
                    break
            if header_idx >= 0:
                # Map column names to indices
                for j, cell in enumerate(row_str):
                    header_map[cell] = j
                break

        if header_idx < 0:
            continue  # No header found, skip this sheet

        # Find relevant column indices using flexible matching
        def _find_col(*candidates: str) -> int:
            """Find column index by trying multiple header name candidates."""
            for candidate in candidates:
                if candidate in header_map:
                    return header_map[candidate]
            return -1

        student_col = _find_col(
            "STUDENT NAME", "STUDENTNAME", "STUDENT  NAME",
        )
        father_name_col = _find_col(
            "FATHER'S NAME", "FATHERNAME", "FATHER NAME",
        )
        father_phone_col = _find_col(
            "FATHER MOBILE NO.", "FATHERMOBILE", "FATHER MOBILE NO",
            "FATHER MOBILE", "FATHER'S MOBILE NO.",
        )
        mother_name_col = _find_col(
            "MOTHER NAME", "MOTHERNAME", "MOTHER'S NAME",
        )
        mother_phone_col = _find_col(
            "MOTHER MOBILE NO.", "MOTHERMOBILE", "MOTHER MOBILE NO",
            "MOTHER MOBILE", "MOTHER'S MOBILE NO.",
        )
        grade_col = _find_col("GRADE", "CLASS")

        if student_col < 0:
            continue  # Can't find student name column

        # Process data rows after header
        for row in rows[header_idx + 1:]:
            if not row or len(row) <= student_col:
                continue
            child_name = str(row[student_col] or "").strip()
            if not child_name or child_name.upper() in ("", "STUDENT NAME"):
                continue

            # Get grade from cell or sheet name
            grade = ""
            if grade_col >= 0 and len(row) > grade_col and row[grade_col]:
                grade = str(row[grade_col]).strip()
            if not grade:
                # Derive grade from sheet name
                grade = sheet_name.strip()

            # Normalize grade format (e.g. "3C" -> "Grade 3C", "Nur 1" -> "Nursery 1")
            grade = _normalize_grade(grade)

            # Process father
            if father_phone_col >= 0 and len(row) > father_phone_col and row[father_phone_col]:
                phone = _normalize_phone(str(row[father_phone_col]))
                father_name = ""
                if father_name_col >= 0 and len(row) > father_name_col and row[father_name_col]:
                    father_name = str(row[father_name_col]).strip()
                if phone:
                    new_parents += _upsert_parent(conn, phone, child_name, grade, father_name)

            # Process mother
            if mother_phone_col >= 0 and len(row) > mother_phone_col and row[mother_phone_col]:
                phone = _normalize_phone(str(row[mother_phone_col]))
                mother_name = ""
                if mother_name_col >= 0 and len(row) > mother_name_col and row[mother_name_col]:
                    mother_name = str(row[mother_name_col]).strip()
                if phone:
                    new_parents += _upsert_parent(conn, phone, child_name, grade, mother_name)

    wb.close()
    return new_parents


def _normalize_grade(grade: str) -> str:
    """Normalize grade strings to a consistent format."""
    g = grade.strip()
    g_upper = g.upper()

    # Already has 'Grade' prefix
    if g_upper.startswith("GRADE "):
        return "Grade " + g[6:].strip().upper()

    # Nursery variations
    if g_upper.startswith("NUR"):
        num = g_upper.replace("NURSERY", "").replace("NUR", "").strip()
        if num:
            return f"Nursery {num}"
        return g

    # Prep variations
    if g_upper.startswith("PREP"):
        num = g_upper.replace("PREP", "").strip()
        if num:
            return f"Prep {num}"
        return g

    # Popsicles
    if "POPSICLE" in g_upper:
        return "Popsicles"

    # Bare number+letter like "3C" or "10A"
    m = re.match(r"^(\d+)\s*([A-Ca-c]?)$", g.strip())
    if m:
        num = m.group(1)
        section = m.group(2).upper()
        return f"Grade {num}{section}" if section else f"Grade {num}"

    return g


def _ist_now() -> str:
    return datetime.now(IST).isoformat(timespec="seconds")


def _upsert_erp_guardian(
    conn: sqlite3.Connection,
    student_id: int,
    name: str,
    phone: str,
    relationship: str,
    is_primary: bool,
    now: str,
) -> None:
    normalized_phone = _normalize_phone(phone)
    guardian = None
    if normalized_phone:
        guardian = conn.execute(
            """SELECT id FROM erp_guardians
               WHERE phone = ? AND lower(full_name) = lower(?)""",
            (normalized_phone, name),
        ).fetchone()
    elif name:
        guardian = conn.execute(
            """SELECT g.id FROM erp_guardians g
               JOIN erp_student_guardians sg ON sg.guardian_id = g.id
               WHERE sg.student_id = ? AND sg.relationship = ?
                 AND lower(g.full_name) = lower(?)""",
            (student_id, relationship, name),
        ).fetchone()

    if guardian:
        guardian_id = guardian["id"]
        conn.execute(
            """UPDATE erp_guardians
               SET full_name = CASE WHEN full_name = '' THEN ? ELSE full_name END,
                   updated_at = ?
               WHERE id = ?""",
            (name, now, guardian_id),
        )
    else:
        cursor = conn.execute(
            """INSERT INTO erp_guardians
               (full_name, phone, created_at, updated_at)
               VALUES (?, ?, ?, ?)""",
            (name, normalized_phone, now, now),
        )
        guardian_id = cursor.lastrowid

    conn.execute(
        """INSERT OR IGNORE INTO erp_student_guardians
           (student_id, guardian_id, relationship, is_primary)
           VALUES (?, ?, ?, ?)""",
        (student_id, guardian_id, relationship, int(is_primary)),
    )


def seed_erp_students_from_pi_sheet() -> int:
    """Import the existing PI roster into the normalized ERP student directory."""
    pi_path = Path(PI_SHEET_PATH)
    if not pi_path.exists():
        logger.warning("ERP seed skipped: PI sheet JSON not found")
        return 0

    with open(pi_path, encoding="utf-8") as file:
        records = json.load(file)

    conn = get_db()
    imported = 0
    duplicate_records = 0
    now = _ist_now()
    try:
        for record in records:
            full_name = str(
                record.get("student_name") or record.get("student") or ""
            ).strip()
            grade = _normalize_grade(str(record.get("grade") or "").strip())
            if not full_name or not grade:
                continue

            source_values = {
                "student": full_name.casefold(),
                "grade": grade.casefold(),
                "father": str(record.get("father_name") or record.get("father") or "")
                .strip()
                .casefold(),
                "father_mobile": _normalize_phone(
                    str(record.get("father_mobile") or "")
                ),
                "mother": str(record.get("mother_name") or record.get("mother") or "")
                .strip()
                .casefold(),
                "mother_mobile": _normalize_phone(
                    str(record.get("mother_mobile") or "")
                ),
                "address": str(record.get("address") or "").strip().casefold(),
            }
            source_key = hashlib.sha256(
                json.dumps(source_values, sort_keys=True).encode("utf-8")
            ).hexdigest()
            cursor = conn.execute(
                """INSERT OR IGNORE INTO erp_students
                   (full_name, grade, address, transport, source, source_key,
                    created_at, updated_at)
                   VALUES (?, ?, ?, ?, 'pi_sheet', ?, ?, ?)""",
                (
                    full_name,
                    grade,
                    str(record.get("address") or "").strip(),
                    str(record.get("transport") or "").strip(),
                    source_key,
                    now,
                    now,
                ),
            )
            imported += cursor.rowcount
            duplicate_records += int(cursor.rowcount == 0)
            student = conn.execute(
                "SELECT id FROM erp_students WHERE source_key = ?",
                (source_key,),
            ).fetchone()
            if not student:
                continue

            guardians = [
                (
                    str(record.get("father_name") or record.get("father") or "").strip(),
                    str(record.get("father_mobile") or "").strip(),
                    "father",
                ),
                (
                    str(record.get("mother_name") or record.get("mother") or "").strip(),
                    str(record.get("mother_mobile") or "").strip(),
                    "mother",
                ),
            ]
            primary_assigned = False
            for name, phone, relationship in guardians:
                if not name and not _normalize_phone(phone):
                    continue
                _upsert_erp_guardian(
                    conn,
                    student["id"],
                    name,
                    phone,
                    relationship,
                    not primary_assigned,
                    now,
                )
                primary_assigned = True

        if imported:
            conn.execute(
                """INSERT INTO erp_audit_log
                   (action, entity_type, details, created_at)
                   VALUES ('import', 'student_roster', ?, ?)""",
                (
                    json.dumps(
                        {
                            "source": "pi_sheet",
                            "imported": imported,
                            "exact_duplicates": duplicate_records,
                        }
                    ),
                    now,
                ),
            )
        conn.commit()
    finally:
        conn.close()

    logger.info(
        "ERP student directory seeded with %d new student(s); %d exact duplicate(s)",
        imported,
        duplicate_records,
    )
    return imported


def seed_school_data():
    """Seed teachers, admins, and class groups from school data."""
    conn = get_db()

    # Create bot user
    conn.execute(
        "INSERT OR IGNORE INTO users (phone, name, role) VALUES (?, ?, ?)",
        ("bot", "PPIS Bot", "bot"),
    )

    # Seed admin users
    admin_names = {
        "9971166562": "Mr. Rahul Gupta",
        "9910034550": "Ms. Purnima Gupta",
        "9599488106": "Ms. Harpreet Kaur",
        "8076455224": "Ms. Alisha Ahuja",
    }
    for phone, name in admin_names.items():
        conn.execute(
            "INSERT OR IGNORE INTO users (phone, name, role) VALUES (?, ?, ?)",
            (phone, name, "admin"),
        )

    # Seed teachers
    seen_phones: set[str] = set()
    for t in TEACHER_DATA:
        phone = t["phone"]
        if not phone or phone in seen_phones:
            continue
        seen_phones.add(phone)
        conn.execute(
            "INSERT OR IGNORE INTO users (phone, name, role, grade) VALUES (?, ?, ?, ?)",
            (phone, t["name"], "teacher", t["grade"]),
        )

    # Load parents from PI Sheet JSON (may have incomplete phone data)
    pi_path = Path(PI_SHEET_PATH)
    json_parent_count = 0
    if pi_path.exists():
        try:
            with open(pi_path) as f:
                students = json.load(f)
            for s in students:
                grade = s.get("grade", "")
                child_name = s.get("student_name", "") or s.get("student", "")
                for phone_key, name_key in [("father_mobile", "father"), ("mother_mobile", "mother")]:
                    phone = s.get(phone_key, "")
                    if not phone:
                        continue
                    phone = _normalize_phone(str(phone))
                    if not phone:
                        continue
                    json_parent_count += _upsert_parent(
                        conn, phone, child_name, grade,
                        s.get("father_name", s.get(name_key, "")) if name_key == "father"
                        else s.get("mother_name", s.get(name_key, "")),
                    )
            logger.info(f"Seeded {json_parent_count} new parents from PI Sheet JSON")
        except Exception as e:
            logger.error(f"Failed to load PI Sheet JSON: {e}")

    # Load parents from Excel file (has complete phone numbers)
    excel_path = Path(EXCEL_PATH)
    excel_parent_count = 0
    if excel_path.exists():
        try:
            excel_parent_count = _seed_from_excel(conn, excel_path)
            logger.info(f"Seeded {excel_parent_count} new parents from Excel")
        except Exception as e:
            logger.error(f"Failed to load Excel: {e}")

    # Create class groups
    all_grades = sorted(
        set(t["grade"] for t in TEACHER_DATA),
        key=lambda g: g,
    )
    for grade in all_grades:
        existing = conn.execute(
            "SELECT id FROM groups_ WHERE grade = ? AND type = 'class'", (grade,)
        ).fetchone()
        if not existing:
            conn.execute(
                "INSERT INTO groups_ (name, grade, type) VALUES (?, ?, ?)",
                (f"{grade} Group", grade, "class"),
            )
            logger.info(f"Created group for {grade}")

    # Create school-wide announcements group
    existing = conn.execute(
        "SELECT id FROM groups_ WHERE type = 'announcement'"
    ).fetchone()
    if not existing:
        conn.execute(
            "INSERT INTO groups_ (name, grade, type) VALUES (?, ?, ?)",
            ("School Announcements", "", "announcement"),
        )

    # Add members to class groups
    groups = conn.execute("SELECT id, grade FROM groups_ WHERE type = 'class'").fetchall()
    for grp in groups:
        grade = grp["grade"]
        # Add teachers for this grade
        for t in TEACHER_DATA:
            if t["grade"] == grade and t["phone"]:
                teacher = conn.execute(
                    "SELECT id FROM users WHERE phone = ?", (t["phone"],)
                ).fetchone()
                if teacher:
                    conn.execute(
                        "INSERT OR IGNORE INTO group_members (group_id, user_id, role) VALUES (?, ?, ?)",
                        (grp["id"], teacher["id"], "teacher"),
                    )
        # Add parents for this grade
        parents = conn.execute(
            "SELECT id, children FROM users WHERE role = 'parent'"
        ).fetchall()
        for parent in parents:
            children = json.loads(parent["children"] or "[]")
            for child in children:
                if child.get("grade") == grade:
                    conn.execute(
                        "INSERT OR IGNORE INTO group_members (group_id, user_id, role) VALUES (?, ?, ?)",
                        (grp["id"], parent["id"], "member"),
                    )
                    break

    # Add admins to all groups
    all_groups = conn.execute("SELECT id FROM groups_").fetchall()
    admin_users = conn.execute("SELECT id FROM users WHERE role = 'admin'").fetchall()
    for grp in all_groups:
        for adm in admin_users:
            conn.execute(
                "INSERT OR IGNORE INTO group_members (group_id, user_id, role) VALUES (?, ?, ?)",
                (grp["id"], adm["id"], "admin"),
            )

    conn.commit()
    conn.close()
    logger.info("School data seeded successfully")
