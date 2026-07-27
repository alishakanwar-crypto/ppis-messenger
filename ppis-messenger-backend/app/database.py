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
    """)
    # Migrations: add columns that might be missing on existing databases
    try:
        conn.execute("ALTER TABLE users ADD COLUMN avatar_url TEXT DEFAULT ''")
        logger.info("Added avatar_url column to users table")
    except sqlite3.OperationalError:
        pass  # Column already exists

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

    roster_conn = get_db()
    try:
        roster_count = roster_conn.execute(
            "SELECT COUNT(*) AS count FROM erp_students"
        ).fetchone()["count"]
    finally:
        roster_conn.close()
    if roster_count > 0:
        logger.info(
            "ERP roster already populated (%d students); skipping boot seed — use resync",
            roster_count,
        )
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
                   (admission_number, full_name, grade, date_of_birth, gender,
                    address, transport, source, source_key,
                    created_at, updated_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, 'pi_sheet', ?, ?, ?)""",
                (
                    str(record.get("admission_number") or "").strip(),
                    full_name,
                    grade,
                    str(record.get("dob") or record.get("date_of_birth") or "").strip(),
                    str(record.get("gender") or "").strip(),
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


def _roster_name(value: str) -> str:
    return re.sub(r"[^A-Z0-9]", "", str(value or "").upper())


def _record_parent_phones(record: dict) -> set[str]:
    return {
        phone
        for phone in (
            _normalize_phone(str(record.get("father_mobile") or "")),
            _normalize_phone(str(record.get("mother_mobile") or "")),
        )
        if phone
    }


def _student_guardian_snapshot(conn: sqlite3.Connection, student_id: int) -> dict:
    rows = conn.execute(
        """SELECT sg.relationship, g.full_name, g.phone
           FROM erp_student_guardians sg
           JOIN erp_guardians g ON g.id = sg.guardian_id
           WHERE sg.student_id = ? ORDER BY sg.relationship""",
        (student_id,),
    ).fetchall()
    return {
        row["relationship"]: {
            "full_name": row["full_name"],
            "phone": row["phone"],
        }
        for row in rows
    }


def _resync_record(record: dict) -> dict:
    return {
        "admission_number": str(record.get("admission_number") or "").strip(),
        "full_name": str(
            record.get("student_name") or record.get("student") or ""
        ).strip(),
        "grade": _normalize_grade(str(record.get("grade") or "").strip()),
        "date_of_birth": str(
            record.get("date_of_birth") or record.get("dob") or ""
        ).strip(),
        "gender": str(record.get("gender") or "").strip(),
        "address": str(record.get("address") or "").strip(),
        "transport": str(record.get("transport") or "").strip(),
        "father_name": str(
            record.get("father_name") or record.get("father") or ""
        ).strip(),
        "father_mobile": _normalize_phone(str(record.get("father_mobile") or "")),
        "mother_name": str(
            record.get("mother_name") or record.get("mother") or ""
        ).strip(),
        "mother_mobile": _normalize_phone(str(record.get("mother_mobile") or "")),
    }


def resync_erp_students_from_pi_sheet(
    dry_run: bool,
    withdraw: bool = False,
) -> dict:
    """Reconcile ERP students against the current PI roster.

    This is intentionally not called from application startup.  A dry run
    performs no database writes, including audit writes.
    """
    pi_path = Path(PI_SHEET_PATH)
    if not pi_path.exists():
        raise FileNotFoundError(f"PI sheet JSON not found: {pi_path}")
    with open(pi_path, encoding="utf-8") as file:
        live = [_resync_record(record) for record in json.load(file)]
    live = [record for record in live if record["full_name"] and record["grade"]]

    conn = get_db()
    try:
        erp_rows = conn.execute("SELECT * FROM erp_students").fetchall()
        erp = [dict(row) for row in erp_rows]
        live_by_admission: dict[str, list[dict]] = {}
        live_by_name: dict[str, list[dict]] = {}
        for row in live:
            if row["admission_number"]:
                live_by_admission.setdefault(row["admission_number"], []).append(row)
            live_by_name.setdefault(_roster_name(row["full_name"]), []).append(row)

        guardian_phones = {}
        for row in erp:
            guardian_phones[row["id"]] = {
                x["phone"]
                for x in conn.execute(
                    """SELECT g.phone FROM erp_student_guardians sg
                       JOIN erp_guardians g ON g.id = sg.guardian_id
                       WHERE sg.student_id = ?""",
                    (row["id"],),
                ).fetchall()
                if x["phone"]
            }

        matches: dict[int, dict] = {}
        match_methods: dict[int, str] = {}
        claimed_live: set[int] = set()

        def claim(row, candidates, method):
            candidates = [item for item in candidates if id(item) not in claimed_live]
            if len(candidates) != 1:
                return None
            candidate = candidates[0]
            matches[row["id"]] = candidate
            match_methods[row["id"]] = method
            claimed_live.add(id(candidate))
            return candidate

        # Stable identifiers first.
        for row in erp:
            if row["admission_number"]:
                claim(row, live_by_admission.get(row["admission_number"], []), "admission_number")

        # Parent phones intentionally ignore grade to handle promotions and
        # stale grade nomenclature in the old ERP snapshot.
        for row in erp:
            if row["id"] in matches:
                continue
            phones = guardian_phones[row["id"]]
            candidates = [
                item for item in live_by_name.get(_roster_name(row["full_name"]), [])
                if phones.intersection(_record_parent_phones(item))
            ]
            claim(row, candidates, "name_parent_phone")

        # A unique normalized name is the final safe fallback. Multiple
        # students with the same normalized name remain unmatched.
        for row in erp:
            if row["id"] in matches:
                continue
            claim(
                row,
                live_by_name.get(_roster_name(row["full_name"]), []),
                "unique_name",
            )

        matched_live_ids = {id(candidate) for candidate in matches.values()}
        method_counts = {
            "admission_number": sum(
                method == "admission_number" for method in match_methods.values()
            ),
            "name_parent_phone": sum(
                method == "name_parent_phone" for method in match_methods.values()
            ),
            "unique_name": sum(
                method == "unique_name" for method in match_methods.values()
            ),
        }
        admission_backfill = {"unambiguous": 0, "ambiguous": 0, "unmatched": 0}
        for row in erp:
            if row["admission_number"]:
                continue
            candidate = matches.get(row["id"])
            if candidate is not None and candidate["admission_number"]:
                admission_backfill["unambiguous"] += 1
            elif len([
                item for item in live_by_name.get(_roster_name(row["full_name"]), [])
                if id(item) not in claimed_live
            ]) > 1:
                admission_backfill["ambiguous"] += 1
            else:
                admission_backfill["unmatched"] += 1

        summary = {
            "matched_unchanged": 0,
            "matched_updated": 0,
            "grade_promotions": 0,
            "other_field_changes": 0,
            "new_inserts": 0,
            "ambiguous_live": 0,
            "not_in_current_sheet": 0,
            "new_inserts_list": [],
            "ambiguous_live_list": [],
            "not_in_current_sheet_list": [],
            "match_methods": method_counts,
            "admission_backfill": admission_backfill,
            "live_grades": sorted({_normalize_grade(row["grade"]) for row in live}),
            "erp_grades_without_live_tab": [],
        }
        tabs_path = pi_path.with_name("live_pi_sheet_tabs.json")
        if not tabs_path.exists():
            bundled_tabs = Path(__file__).resolve().parent.parent / "pi_sheet_tabs.json"
            tabs_path = bundled_tabs if bundled_tabs.exists() else tabs_path
        if tabs_path.exists():
            with open(tabs_path, encoding="utf-8") as tabs_file:
                tab_rows = json.load(tabs_file)
            live_tab_grades = sorted(
                {_normalize_grade(str(row.get("grade") or "")) for row in tab_rows}
                - {""}
            )
        else:
            live_tab_grades = summary["live_grades"]
        summary["live_tab_grades"] = live_tab_grades
        summary["erp_grades_without_live_tab"] = sorted(
            {
                _normalize_grade(row["grade"])
                for row in erp
                if _normalize_grade(row["grade"]) not in live_tab_grades
            }
        )
        now = _ist_now()
        for row in erp:
            candidate = matches.get(row["id"])
            if candidate is None:
                summary["not_in_current_sheet"] += 1
                summary["not_in_current_sheet_list"].append(
                    {
                        "name": row["full_name"],
                        "grade": row["grade"],
                        "admission_number": row["admission_number"],
                        "parent_phones": sorted(guardian_phones[row["id"]]),
                    }
                )
                continue
            before = {
                "admission_number": row["admission_number"],
                "grade": row["grade"],
                "transport": row["transport"],
                "gender": row["gender"],
                "date_of_birth": row["date_of_birth"],
                "address": row["address"],
                "status": row["status"],
                "guardians": _student_guardian_snapshot(conn, row["id"]),
            }
            expected_guardians = {
                relationship: {"full_name": name, "phone": phone}
                for relationship, name, phone in (
                    ("father", candidate["father_name"], candidate["father_mobile"]),
                    ("mother", candidate["mother_name"], candidate["mother_mobile"]),
                )
                if name or phone
            }
            after = {
                "admission_number": candidate["admission_number"],
                "grade": candidate["grade"],
                "transport": candidate["transport"],
                "gender": candidate["gender"],
                "date_of_birth": candidate["date_of_birth"],
                "address": candidate["address"],
                "status": "active",
                "guardians": expected_guardians,
            }
            changed = before != after
            if not changed:
                summary["matched_unchanged"] += 1
                continue
            summary["matched_updated"] += 1
            if before["grade"] != after["grade"]:
                summary["grade_promotions"] += 1
            if any(before[field] != after[field] for field in (
                "admission_number", "transport", "gender", "date_of_birth",
                "address", "status", "guardians",
            )):
                summary["other_field_changes"] += 1
            if not dry_run:
                conn.execute(
                    """UPDATE erp_students SET admission_number=?, grade=?,
                       transport=?, gender=?, date_of_birth=?, address=?,
                       status='active', updated_at=? WHERE id=?""",
                    (
                        candidate["admission_number"], candidate["grade"],
                        candidate["transport"], candidate["gender"],
                        candidate["date_of_birth"], candidate["address"],
                        now, row["id"],
                    ),
                )
                conn.execute(
                    "DELETE FROM erp_student_guardians WHERE student_id = ?",
                    (row["id"],),
                )
                primary = False
                for name, phone, relationship in (
                    (candidate["father_name"], candidate["father_mobile"], "father"),
                    (candidate["mother_name"], candidate["mother_mobile"], "mother"),
                ):
                    if name or phone:
                        _upsert_erp_guardian(
                            conn, row["id"], name, phone, relationship,
                            not primary, now,
                        )
                        primary = True
                conn.execute(
                    """INSERT INTO erp_audit_log
                       (action, entity_type, entity_id, details, created_at)
                       VALUES ('resync_update', 'student', ?, ?, ?)""",
                    (row["id"], json.dumps({"before": before, "after": after}), now),
                )

        unmatched_erp_names = {
            _roster_name(row["full_name"])
            for row in erp
            if row["id"] not in matches
        }
        for candidate in live:
            if id(candidate) in matched_live_ids:
                continue
            if _roster_name(candidate["full_name"]) in unmatched_erp_names:
                summary["ambiguous_live"] += 1
                summary["ambiguous_live_list"].append(
                    {"name": candidate["full_name"], "grade": candidate["grade"]}
                )
                continue
            summary["new_inserts"] += 1
            summary["new_inserts_list"].append(
                {"name": candidate["full_name"], "grade": candidate["grade"]}
            )
            if not dry_run:
                cursor = conn.execute(
                    """INSERT INTO erp_students
                       (admission_number, full_name, grade, date_of_birth, gender,
                        address, transport, status, source, source_key,
                        created_at, updated_at)
                       VALUES (?, ?, ?, ?, ?, ?, ?, 'active', 'pi_sheet', ?, ?, ?)""",
                    (
                        candidate["admission_number"], candidate["full_name"],
                        candidate["grade"], candidate["date_of_birth"],
                        candidate["gender"], candidate["address"],
                        candidate["transport"],
                        hashlib.sha256(
                            json.dumps(candidate, sort_keys=True).encode()
                        ).hexdigest(),
                        now, now,
                    ),
                )
                conn.execute(
                    """INSERT INTO erp_audit_log
                       (action, entity_type, entity_id, details, created_at)
                       VALUES ('resync_insert', 'student', ?, ?, ?)""",
                    (cursor.lastrowid, json.dumps({"after": candidate}), now),
                )
        if not dry_run:
            if withdraw:
                for row in erp:
                    if row["id"] not in matches and row["status"] == "active":
                        conn.execute(
                            "UPDATE erp_students SET status='withdrawn', updated_at=? WHERE id=?",
                            (now, row["id"]),
                        )
                        conn.execute(
                            """INSERT INTO erp_audit_log
                               (action, entity_type, entity_id, details, created_at)
                               VALUES ('resync_withdraw', 'student', ?, ?, ?)""",
                            (
                                row["id"],
                                json.dumps({
                                    "before": {"status": row["status"], "grade": row["grade"]},
                                    "after": {"status": "withdrawn"},
                                }),
                                now,
                            ),
                        )
            conn.commit()
        return summary
    finally:
        conn.close()


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
