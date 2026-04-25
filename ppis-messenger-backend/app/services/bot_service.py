"""PPIS Bot intelligence — shared between app and WhatsApp channels.

Ported from whatsapp-bot-backend's openai_service.py and webhook.py.
Provides teacher lookup, transport info, school knowledge, and AI responses.
"""

import json
import logging
import os
import re
import time

import httpx

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Teacher data (comprehensive, from whatsapp-bot-backend)
# ---------------------------------------------------------------------------

TEACHER_DATA = [
    {"grade": "Popsicles", "teacher": "Sanya Mehra / Anu", "email": "sanya.mehra@ppischool.in", "class_email": "popsicles@ppischool.in", "parents_email": "popsicles.parents@ppischool.in", "whatsapp": "9289234655"},
    {"grade": "Nursery 1", "teacher": "Jasleen Kaur / Deepti", "email": "jasleen.kaur1@ppischool.in", "class_email": "nursery1@ppischool.in", "parents_email": "nursery1.parents@ppischool.in", "whatsapp": "9289234654"},
    {"grade": "Nursery 2", "teacher": "Priyanka Budhiraja / Geet", "email": "priyanka.budhiraja@ppischool.in", "class_email": "nursery2@ppischool.in", "parents_email": "nursery2.parents@ppischool.in", "whatsapp": "9289234657"},
    {"grade": "Nursery 3", "teacher": "Nashra / Deepti", "email": "nashra.naim@ppischool.in", "class_email": "nursery3@ppischool.in", "parents_email": "nursery3.parents@ppischool.in", "whatsapp": "9289236042"},
    {"grade": "Prep 1", "teacher": "Meenal Harjika", "email": "meenal.harjika@ppischool.in", "class_email": "prep1@ppischool.in", "parents_email": "prep1.parents@ppischool.in", "whatsapp": "9289234656"},
    {"grade": "Prep 2", "teacher": "Amita Sachdeva / Anjali", "email": "amita.sachdeva1@ppischool.in", "class_email": "prep2@ppischool.in", "parents_email": "prep2.parents@ppischool.in", "whatsapp": "9289234658"},
    {"grade": "Prep 3", "teacher": "Mahak Jain / Pooja", "email": "mahak.jain@ppischool.in", "class_email": "prep3@ppischool.in", "parents_email": "prep3.parents@ppischool.in", "whatsapp": "9289236056"},
    {"grade": "Grade 1A", "teacher": "Shreya Sikka / Pallavi", "email": "shreya.sikka@ppischool.in", "class_email": "grade1a@ppischool.in", "parents_email": "grade1a.parents@ppischool.in", "whatsapp": "9289234652"},
    {"grade": "Grade 1B", "teacher": "Muskan Motwani", "email": "muskan.motwani@ppischool.in", "class_email": "grade1b@ppischool.in", "parents_email": "grade1b.parents@ppischool.in", "whatsapp": "9289234660"},
    {"grade": "Grade 2A", "teacher": "Gargi Arora", "email": "gargi.arora@ppischool.in", "class_email": "grade2a@ppischool.in", "parents_email": "grade2a.parents@ppischool.in", "whatsapp": "9289234661"},
    {"grade": "Grade 2B", "teacher": "Tanvi Goyal / Sanchita", "email": "tanvi.goyal@ppischool.in", "class_email": "grade2b@ppischool.in", "parents_email": "grade2b.parents@ppischool.in", "whatsapp": "9289234662"},
    {"grade": "Grade 3A", "teacher": "Reva Rajput", "email": "reva.rajput@ppischool.in", "class_email": "grade3a@ppischool.in", "parents_email": "grade3a.parents@ppischool.in", "whatsapp": "9289236072"},
    {"grade": "Grade 3B", "teacher": "Seema Bakshi", "email": "seema.bakshi@ppischool.in", "class_email": "grade3b@ppischool.in", "parents_email": "grade3b.parents@ppischool.in", "whatsapp": "9289234664"},
    {"grade": "Grade 3C", "teacher": "Harnoor Kaur", "email": "harnoor.kaur@ppischool.in", "class_email": "grade3c@ppischool.in", "parents_email": "grade3c.parents@ppischool.in", "whatsapp": "9289234659"},
    {"grade": "Grade 4A", "teacher": "Prabhjot Kaur", "email": "prabhjot.kaur@ppischool.in", "class_email": "grade4a@ppischool.in", "parents_email": "grade4a.parents@ppischool.in", "whatsapp": "9289234663"},
    {"grade": "Grade 4B", "teacher": "Damanpreet Kaur", "email": "damanpreet.kaur@ppischool.in", "class_email": "grade4b@ppischool.in", "parents_email": "grade4b.parents@ppischool.in", "whatsapp": "9289236041"},
    {"grade": "Grade 5A", "teacher": "Poshika Narula", "email": "poshika.narula@ppischool.in", "class_email": "grade5a@ppischool.in", "parents_email": "grade5a.parents@ppischool.in", "whatsapp": "9289236045"},
    {"grade": "Grade 5B", "teacher": "Aastha Khattar", "email": "aastha.khattar@ppischool.in", "class_email": "grade5b@ppischool.in", "parents_email": "grade5b.parents@ppischool.in", "whatsapp": "9289234653"},
    {"grade": "Grade 6A", "teacher": "Kaninika Jain", "email": "kaninika.jain@ppischool.in", "class_email": "grade6a@ppischool.in", "parents_email": "grade6a.parents@ppischool.in", "whatsapp": "9289234665"},
    {"grade": "Grade 6B", "teacher": "Shikha Singh", "email": "shikha.singh@ppischool.in", "class_email": "grade6b@ppischool.in", "parents_email": "grade6b.parents@ppischool.in", "whatsapp": "9289236043"},
    {"grade": "Grade 7A", "teacher": "Shyam Manohar", "email": "shyam.manohar@ppischool.in", "class_email": "grade7a@ppischool.in", "parents_email": "grade7a.parents@ppischool.in", "whatsapp": "9289236049", "gender": "male"},
    {"grade": "Grade 7B", "teacher": "Twinkle Tandon", "email": "twinkle.tandon@ppischool.in", "class_email": "grade7b@ppischool.in", "parents_email": "grade7b.parents@ppischool.in", "whatsapp": "9289236044"},
    {"grade": "Grade 8A", "teacher": "Tarun Dhall", "email": "tarun.dhall@ppischool.in", "class_email": "grade8a@ppischool.in", "parents_email": "grade8a.parents@ppischool.in", "whatsapp": "9289236057", "gender": "male"},
    {"grade": "Grade 8B", "teacher": "Rashmi", "email": "rashmi.pp@ppischool.in", "class_email": "grade8b@ppischool.in", "parents_email": "grade8b.parents@ppischool.in", "whatsapp": "9289236048"},
    {"grade": "Grade 8C", "teacher": "Nikita Chawla", "email": "nikita.chawla@ppischool.in", "class_email": "grade8c@ppischool.in", "parents_email": "grade8c.parents@ppischool.in", "whatsapp": "9289236046"},
    {"grade": "Grade 9A", "teacher": "Mansi Gupta", "email": "mansi.gupta@ppischool.in", "class_email": "grade9a@ppischool.in", "parents_email": "grade9a.parents@ppischool.in", "whatsapp": "9289236058"},
    {"grade": "Grade 9B", "teacher": "Vaishali Arora", "email": "vaishali.arora@ppischool.in", "class_email": "grade9b@ppischool.in", "parents_email": "grade9b.parents@ppischool.in", "whatsapp": "9289236047"},
    {"grade": "Grade 9C", "teacher": "Harjeet Kaur", "email": "harjeet.kaur@ppischool.in", "class_email": "grade9c@ppischool.in", "parents_email": "grade9c.parents@ppischool.in", "whatsapp": "9289236052"},
    {"grade": "Grade 10A", "teacher": "Riya Arora", "email": "riya.arora@ppischool.in", "class_email": "grade10a@ppischool.in", "parents_email": "grade10a.parents@ppischool.in", "whatsapp": "9289236050"},
    {"grade": "Grade 10B", "teacher": "Avneet Kaur", "email": "avneet.kaur1@ppischool.in", "class_email": "grade10b@ppischool.in", "parents_email": "grade10b.parents@ppischool.in", "whatsapp": "9289236051"},
    {"grade": "Grade 11 (Science)", "teacher": "Aradhana Gambhir", "email": "", "class_email": "", "parents_email": "", "whatsapp": ""},
    {"grade": "Grade 11 (Commerce)", "teacher": "Christy Joseph", "email": "christy.joseph@ppischool.in", "class_email": "grade11b@ppischool.in", "parents_email": "grade11b.parents@ppischool.in", "whatsapp": "9289236054", "gender": "male"},
    {"grade": "Grade 11 (Humanities)", "teacher": "Tarleen / Deepak", "email": "", "class_email": "", "parents_email": "", "whatsapp": ""},
    {"grade": "Grade 12 (Science)", "teacher": "Pooja Arora", "email": "pooja.arora@ppischool.in", "class_email": "grade12a@ppischool.in", "parents_email": "grade12a.parents@ppischool.in", "whatsapp": "9289236053"},
    {"grade": "Grade 12 (Commerce)", "teacher": "Sucheta Sinha", "email": "sucheta.sinha@ppischool.in", "class_email": "grade12b@ppischool.in", "parents_email": "grade12b.parents@ppischool.in", "whatsapp": "9289236059"},
    {"grade": "Grade 12 (Humanities)", "teacher": "Sucheta Sinha", "email": "sucheta.sinha@ppischool.in", "class_email": "grade12c@ppischool.in", "parents_email": "grade12c.parents@ppischool.in", "whatsapp": "9289236059"},
]

CONTACT_INFO = (
    "\n\nFor assistance, please contact:\n"
    "- School Helpline / Front Desk: 8800935552\n"
    "- Ms. Harpreet Kaur (Administration Incharge): 9599488106\n\n"
    "Thank you for your cooperation.\n"
    "Warm regards,\n"
    "PP International School"
)

SCHOOL_PHOTO_GALLERY: dict[str, dict] = {
    "sports": {
        "keywords": ["sport", "sports", "athletics", "games", "football", "cricket", "hockey", "basketball", "sports day", "sports fiesta"],
        "caption": "PPIS Sports",
        "images": [
            "https://www.ppi.school/wp-content/uploads/2025/03/28-768x432.jpg",
            "https://www.ppi.school/wp-content/uploads/2025/03/27-768x432.jpg",
            "https://www.ppi.school/wp-content/uploads/2025/03/26-768x432.jpg",
        ],
    },
    "creative_activities": {
        "keywords": ["creative", "art", "craft", "drawing", "painting", "dance", "music", "activity", "activities"],
        "caption": "PPIS Creative Activities",
        "images": [
            "https://www.ppi.school/wp-content/uploads/2025/03/IMG_04561-600x600.jpg",
            "https://www.ppi.school/wp-content/uploads/2025/03/22-540x600.jpg",
            "https://www.ppi.school/wp-content/uploads/2025/03/8-540x600.jpg",
        ],
    },
    "science_lab": {
        "keywords": ["lab", "laboratory", "science", "physics", "chemistry", "biology", "experiment"],
        "caption": "PPIS Science Labs",
        "images": [
            "https://www.ppi.school/wp-content/uploads/2025/07/IMG_5273-600x600.jpg",
            "https://www.ppi.school/wp-content/uploads/2025/07/IMG_5240-600x600.jpg",
            "https://www.ppi.school/wp-content/uploads/2025/07/IMG_5302-scaled.jpg",
        ],
    },
    "library": {
        "keywords": ["library", "books", "reading"],
        "caption": "PPIS Library",
        "images": [
            "https://www.ppi.school/wp-content/uploads/2025/06/fgr-600x600.jpg",
            "https://www.ppi.school/wp-content/uploads/2025/06/frec-600x600.jpg",
        ],
    },
    "achievement": {
        "keywords": ["achievement", "award", "trophy", "winner", "topper", "result"],
        "caption": "PPIS Achievements",
        "images": [
            "https://www.ppi.school/wp-content/uploads/2025/06/fhr-768x768.jpg",
            "https://www.ppi.school/wp-content/uploads/2025/06/febb-768x768.jpg",
        ],
    },
}


# ---------------------------------------------------------------------------
# Grade search helpers
# ---------------------------------------------------------------------------

def _grade_search_terms(entry: dict) -> list[str]:
    grade_lower = entry["grade"].lower()
    terms = [grade_lower]
    parts = grade_lower.replace("grade ", "").replace("(", "").replace(")", "").strip()
    terms.append(parts)
    terms.append(f"class {parts}")
    terms.append(f"grade {parts}")
    spaced = re.sub(r"(\d+)\s*([a-z])", r"\1 \2", parts)
    if spaced != parts:
        terms.append(spaced)
        terms.append(f"class {spaced}")
        terms.append(f"grade {spaced}")
    nospace = re.sub(r"(\d+)\s+([a-z])", r"\1\2", parts)
    if nospace != parts:
        terms.append(nospace)
        terms.append(f"class {nospace}")
        terms.append(f"grade {nospace}")
    return terms


# ---------------------------------------------------------------------------
# Lookup functions
# ---------------------------------------------------------------------------

def lookup_teacher(query: str) -> str | None:
    """Look up teacher details based on grade/class mentioned in the query."""
    q = query.lower().strip()
    for entry in TEACHER_DATA:
        search_terms = _grade_search_terms(entry)
        if any(term in q for term in search_terms):
            honorific = "Mr." if entry.get("gender") == "male" else "Ms."
            result = f"{entry['grade']}\n"
            result += f"Class Teacher: {honorific} {entry['teacher']}\n"
            if entry["email"]:
                result += f"Teacher Email: {entry['email']}\n"
            if entry.get("class_email"):
                result += f"Class Email: {entry['class_email']}\n"
            if entry.get("parents_email"):
                result += f"Parents Group Email: {entry['parents_email']}\n"
            if entry.get("whatsapp"):
                result += f"WhatsApp (Airtel): {entry['whatsapp']}"
            return result
    return None


def find_teacher_by_grade(query: str) -> dict | None:
    q = query.lower().strip()
    for entry in TEACHER_DATA:
        search_terms = _grade_search_terms(entry)
        if any(term in q for term in search_terms):
            return entry
    return None


def match_photo_category(text: str) -> dict | None:
    """Check if the message asks for photos of a specific category."""
    lower = text.lower()
    photo_ask = any(kw in lower for kw in ["photo", "pic", "image", "picture", "show me", "send me", "share"])
    if not photo_ask:
        return None
    for cat_data in SCHOOL_PHOTO_GALLERY.values():
        for kw in cat_data["keywords"]:
            if kw in lower:
                return cat_data
    return None


def _is_hindi(text: str) -> bool:
    for ch in text:
        if '\u0900' <= ch <= '\u097F':
            return True
    return False


# ---------------------------------------------------------------------------
# Fallback response (when OpenAI is unavailable)
# ---------------------------------------------------------------------------

def generate_fallback_response(user_message: str) -> str:
    msg = user_message.lower().strip()

    teacher_keywords = [
        "teacher", "ct ", "class teacher", "who is", "ct of",
        "grade ", "class ", "nursery", "prep ", "popsicle",
    ]
    if any(kw in msg for kw in teacher_keywords):
        teacher_info = lookup_teacher(msg)
        if teacher_info:
            return f"Here are the class teacher details:\n\n{teacher_info}\n\nThank you for your cooperation.\nWarm regards,\nPP International School"

    if any(word in msg for word in ["hi", "hello", "hey", "hii", "helloo", "namaste"]):
        return (
            "Welcome to PP International School (PPIS).\n\n"
            "We are a CBSE affiliated Senior Secondary School located in Pitampura, New Delhi. "
            "I am here to assist you with any school-related queries.\n\n"
            "How may I help you today?\n\n"
            "Thank you for your cooperation.\n"
            "Warm regards,\nPP International School"
        )
    elif any(word in msg for word in ["thank", "thanks", "thx"]):
        return (
            "You are most welcome. We are always happy to assist you at PP International School.\n\n"
            "Please feel free to reach out anytime you need assistance." + CONTACT_INFO
        )
    elif any(word in msg for word in ["admission", "enroll", "registration", "seat"]):
        return (
            "Thank you for your interest in admissions at PP International School.\n\n"
            "Nursery Admissions 2026-27:\n"
            "- Age: Above 3 years and less than 4 years (as on 31st March 2026)\n"
            "- Total open seats: 40 (General: 30, EWS/DG: 10)\n"
            "- Registration fee: Rs. 25 (non-refundable)\n"
            "- Forms available at school office or online at www.ppi.school\n\n"
            "We offer classes from Pre-nursery to Grade 12 (CBSE affiliated)." + CONTACT_INFO
        )
    elif any(word in msg for word in ["fee", "payment", "charges"]):
        return (
            "For detailed fee structure and payment information, "
            "please contact our school administration office.\n\n"
            "Online payment is also available through our website: www.ppi.school" + CONTACT_INFO
        )
    elif any(word in msg for word in ["transport", "bus", "van", "route", "pickup", "drop", "driver"]):
        return (
            "PP International School provides safe transport facilities:\n\n"
            "- Fully air-conditioned buses with GPRS tracking and CCTV\n"
            "- Well-trained drivers with caretakers in every bus\n\n"
            "We have 23 bus routes covering Delhi NCR with 390+ students.\n"
            "Please ask about a specific route number for detailed info." + CONTACT_INFO
        )
    elif any(word in msg for word in ["timing", "time", "schedule", "hour", "when"]):
        return (
            "PP International School Timings:\n\n"
            "Summer Schedule:\n"
            "- Pre-primary: 7:30 AM to 11:30 AM\n"
            "- Grade 1 onwards: 7:30 AM to 1:30 PM\n\n"
            "Winter Schedule:\n"
            "- Pre-primary: 8:00 AM to 12:00 PM\n"
            "- Grade 1 onwards: 8:00 AM to 2:00 PM" + CONTACT_INFO
        )
    elif any(word in msg for word in ["address", "location", "where", "direction", "map"]):
        return (
            "PP International School is located at:\n\n"
            "LD Block, Pitampura,\n"
            "Near Kohat Enclave Metro Station, Pillar No. 333,\n"
            "New Delhi - 110034\n\n"
            "Nearest Metro: Kohat Enclave (Yellow Line)" + CONTACT_INFO
        )
    elif any(word in msg for word in ["sport", "game", "play", "activity", "activities"]):
        return (
            "PP International School offers a wide range of sports and activities.\n\n"
            "Sports: Skating, Basketball, Soccer, Lawn Tennis, Table Tennis, "
            "Taekwondo, Badminton, Golf\n\n"
            "Activities: Cooking classes, creative writing, story-telling, "
            "drama, debate, hobby classes, educational tours" + CONTACT_INFO
        )
    elif any(word in msg for word in ["principal", "staff", "faculty"]):
        return (
            "PP International School has a team of 44+ qualified teachers.\n"
            "Our School Principal is Ms. Deepi Bector.\n\n"
            "To find a specific class teacher, just ask — e.g. "
            "'Who is the class teacher of Grade 5A?'" + CONTACT_INFO
        )
    else:
        return (
            "Thank you for reaching out to PP International School. "
            "We appreciate your message. For detailed assistance, "
            "please contact our school office." + CONTACT_INFO
        )


# ---------------------------------------------------------------------------
# OpenAI-powered response (with fallback)
# ---------------------------------------------------------------------------

OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY", "")

SYSTEM_PROMPT = (
    "You are the PP International School (PPIS) assistant bot. "
    "You help parents with school-related queries in a polite, professional manner. "
    "PPIS is a CBSE affiliated Senior Secondary School in Pitampura, New Delhi (LD Block, "
    "near Kohat Enclave Metro Station). Principal: Ms. Deepi Bector. "
    "Classes from Pre-nursery (Popsicles) to Grade 12. "
    "School Helpline: 8800935552. "
    "Ms. Harpreet Kaur (Administration Incharge): 9599488106. "
    "Website: www.ppi.school. Email: info@ppischool.in.\n\n"
    "Reply concisely. Use formal language. "
    "End responses with: Thank you for your cooperation. Warm regards, PP International School."
)


async def get_bot_response(message: str, user_name: str = "", grade: str = "") -> str:
    """Generate a bot response — tries OpenAI first, falls back to keyword matching."""
    # Check for teacher lookup first (fast, no API call needed)
    teacher_info = lookup_teacher(message)
    if teacher_info:
        return f"Here are the class teacher details:\n\n{teacher_info}\n\nThank you for your cooperation.\nWarm regards,\nPP International School"

    # Check for photo gallery requests
    photo_cat = match_photo_category(message)
    if photo_cat:
        images = photo_cat.get("images", [])
        caption = photo_cat.get("caption", "PPIS Photos")
        if images:
            links = "\n".join(images[:3])
            return f"{caption}:\n\n{links}\n\nThank you for your cooperation.\nWarm regards,\nPP International School"

    if not OPENAI_API_KEY:
        return generate_fallback_response(message)

    try:
        hindi = _is_hindi(message)
        lang_instruction = ""
        if hindi:
            lang_instruction = (
                "\n\nIMPORTANT: The user is writing in Hindi. "
                "Reply in Hindi (Devanagari script). Be warm and respectful."
            )

        context = SYSTEM_PROMPT + lang_instruction
        if user_name:
            context += f"\nThe parent's name is {user_name}"
        if grade:
            context += f", grade: {grade}"

        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.post(
                "https://api.openai.com/v1/chat/completions",
                headers={"Authorization": f"Bearer {OPENAI_API_KEY}"},
                json={
                    "model": "gpt-4o-mini",
                    "messages": [
                        {"role": "system", "content": context},
                        {"role": "user", "content": message},
                    ],
                    "max_tokens": 500,
                    "temperature": 0.7,
                },
            )
            data = resp.json()
            return data["choices"][0]["message"]["content"]
    except Exception as e:
        logger.error(f"OpenAI error: {e}")
        return generate_fallback_response(message)
