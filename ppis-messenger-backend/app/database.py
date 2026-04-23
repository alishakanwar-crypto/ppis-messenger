"""SQLite database for PPIS Messenger."""

import json
import logging
import os
import sqlite3
from pathlib import Path

logger = logging.getLogger(__name__)

DB_PATH = os.environ.get("DB_PATH", "/data/app.db")
# Fallback for local dev
if not os.path.isdir(os.path.dirname(DB_PATH)):
    DB_PATH = os.path.join(os.path.dirname(__file__), "..", "messenger.db")

PI_SHEET_PATH = os.environ.get(
    "PI_SHEET_PATH",
    os.path.join(os.path.dirname(__file__), "..", "pi_sheet_data.json"),
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

    # Load PI Sheet students and seed parents
    pi_path = Path(PI_SHEET_PATH)
    if pi_path.exists():
        try:
            with open(pi_path) as f:
                students = json.load(f)
            parent_count = 0
            for s in students:
                grade = s.get("grade", "")
                # Support both field name formats
                child_name = s.get("student_name", "") or s.get("student", "")
                for phone_key, name_key in [("father_mobile", "father"), ("mother_mobile", "mother")]:
                    phone = s.get(phone_key, "")
                    if not phone:
                        continue
                    phone = str(phone).strip().replace(" ", "").replace("-", "")
                    if phone.startswith("91") and len(phone) > 10:
                        phone = phone[2:]
                    if len(phone) != 10 or not phone.isdigit():
                        continue
                    existing = conn.execute(
                        "SELECT id, children FROM users WHERE phone = ?", (phone,)
                    ).fetchone()
                    if existing:
                        children = json.loads(existing["children"] or "[]")
                        entry = {"name": child_name, "grade": grade}
                        if entry not in children:
                            children.append(entry)
                            conn.execute(
                                "UPDATE users SET children = ? WHERE id = ?",
                                (json.dumps(children), existing["id"]),
                            )
                    else:
                        parent_name = s.get(
                            "father_name", s.get(name_key, "")
                        ) if name_key == "father" else s.get(
                            "mother_name", s.get(name_key, "")
                        )
                        children = [{"name": child_name, "grade": grade}]
                        conn.execute(
                            "INSERT OR IGNORE INTO users (phone, name, role, grade, children) VALUES (?, ?, ?, ?, ?)",
                            (phone, parent_name, "parent", grade, json.dumps(children)),
                        )
                        parent_count += 1
            logger.info(f"Seeded {parent_count} parents from PI Sheet")
        except Exception as e:
            logger.error(f"Failed to load PI Sheet: {e}")

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
