"""Fetch the current live PI sheet (all grade tabs) into the ERP JSON shape.

Read-only against the published Google Sheet. Produces a rich per-student
record including admission_number, dob, gender so the ERP can key on a stable
admission number instead of name+grade.
"""
import csv
import io
import json
import re
import sys
import urllib.request

BASE = (
    "https://docs.google.com/spreadsheets/d/e/"
    "2PACX-1vQ6ZUQa6hhQ_9QXYIuJuWsleqSZ5vgXbWrRvDfvFpqdEx0iW28Z1GlpLdt9T1F9AvX4BdgPjAmfvH96"
    "/pub?output=csv"
)
GIDS = [
    "1288447916", "2004260388", "1830685668", "1370627064", "1786778811",
    "616483027", "1943511617", "1102992088", "352154940",
    "81657730", "2002492962", "390677163", "2068519553", "873031775",
    "149553903", "22291716", "1168194216", "505784395", "1571684282",
    "353406549", "1466129543", "1448970633", "743552850", "43691386",
    "1591415360", "2010955306", "1384983764", "1505127962", "1630447148",
    "1059379388", "187664454", "573773967", "1080176279", "696644819",
    "523098156", "255213929", "1291854348",
]


def norm(s):
    return " ".join((s or "").strip().split())

def header_norm(s):
    return re.sub(r"[^A-Z0-9]", "", (s or "").upper())


def find_col(header_upper, *names):
    normalized = [header_norm(c) for c in header_upper]
    for want in names:
        for j, c in enumerate(header_upper):
            if c == want:
                return j
        wanted = header_norm(want)
        for j, c in enumerate(normalized):
            if c == wanted:
                return j
    # loose contains
    for want in names:
        for j, c in enumerate(header_upper):
            if want in c:
                return j
    return -1


def main():
    all_rows = []
    tab_results = []
    raw = 0
    for gid in GIDS:
        try:
            r = urllib.request.urlopen(f"{BASE}&gid={gid}", timeout=30)
            if getattr(r, "status", 200) != 200:
                print(f"gid={gid} HTTP {r.status} parse=0", file=sys.stderr)
                continue
            text = r.read().decode("utf-8", "replace")
        except Exception as e:
            print(f"gid={gid} ERR {e!r}", file=sys.stderr)
            continue
        rows = list(csv.reader(io.StringIO(text)))
        if len(rows) < 2:
            print(f"gid={gid} HTTP 200 parse=0 rows={len(rows)}", file=sys.stderr)
            continue
        # find header row with STUDENT NAME
        hidx = -1
        for i, row in enumerate(rows):
            up = [c.strip().upper() for c in row]
            if any(header_norm(c) in ("STUDENTNAME", "NAMEOFSTUDENT") for c in up):
                hidx = i
                break
        if hidx < 0:
            print(f"gid={gid} HTTP 200 parse=0 header_missing rows={len(rows)}", file=sys.stderr)
            continue
        header = [c.strip() for c in rows[hidx]]
        up = [c.upper() for c in header]
        c_name = find_col(up, "STUDENT NAME", "STUDENTNAME")
        c_adm = find_col(
            up, "ADMISSION NUMBER", "ADMISSION NO.", "ADMISSION NO",
            "ADMISSION #", "ADM NO", "ADMISSION",
        )
        c_grade = find_col(up, "GRADE")
        c_previous_grade = find_col(up, "PREVIOUS GRADE", "PREVIOUSGRADE", "PREV GRADE")
        c_transport = find_col(up, "TRANSPORT")
        c_gender = find_col(up, "GENDER")
        c_dob = find_col(up, "DOB")
        c_father = find_col(up, "FATHER'S NAME", "FATHER NAME", "FATHERS NAME", "FATHERNAME")
        c_mother = find_col(up, "MOTHER NAME", "MOTHER'S NAME", "MOTHERS NAME", "MOTHERNAME")
        c_fmob = find_col(up, "FATHER MOBILE NO.", "FATHER MOBILE", "FATHERMOBILE", "FATHERMOBILENO")
        c_mmob = find_col(up, "MOTHER MOBILE NO.", "MOTHER MOBILE", "MOTHERMOBILE", "MOTHERMOBILENO")
        c_addr = find_col(up, "ADDRESS", "RESIDENT ADDRESS", "RESIDENTADDRESS")

        tab_grade = ""
        if c_grade >= 0:
            for row in rows[hidx + 1:]:
                if c_grade < len(row) and row[c_grade].strip():
                    tab_grade = row[c_grade].strip()
                    break

        in_withdrawal = False
        tab_rows = 0
        tab_admissions = 0
        for i in range(hidx + 1, len(rows)):
            row = rows[i]
            if not ",".join(row).strip():
                continue
            first = next((c.strip().lower() for c in row if c.strip()), "")
            if "withdraw" in first:
                in_withdrawal = True
                continue
            if in_withdrawal:
                continue
            if c_name >= len(row):
                continue
            name = row[c_name].strip()
            if (not name or len(name) < 2
                    or name.upper() in ("STUDENT NAME", "STUDENTNAME", "S.NO.", "SR. NO.", "NAME")
                    or name.isdigit()):
                continue
            # skip inline-withdrawn
            if any(c.strip().lower().startswith(("withdraw", "(withdraw")) for c in row if c.strip()):
                continue

            def g(idx):
                return row[idx].strip() if 0 <= idx < len(row) else ""

            grade = g(c_grade) or tab_grade
            raw += 1
            tab_rows += 1
            if g(c_adm):
                tab_admissions += 1
            all_rows.append({
                "student": norm(name),
                "admission_number": norm(g(c_adm)),
                "grade": norm(grade),
                "previous_grade": norm(g(c_previous_grade)),
                "gender": norm(g(c_gender)),
                "dob": norm(g(c_dob)),
                "father": norm(g(c_father)),
                "mother": norm(g(c_mother)),
                "father_mobile": re.sub(r"\D", "", g(c_fmob))[-10:],
                "mother_mobile": re.sub(r"\D", "", g(c_mmob))[-10:],
                "address": norm(g(c_addr)),
                "transport": norm(g(c_transport)),
            })
        print(
            f"gid={gid} HTTP 200 tab_grade={tab_grade or '-'} rows={tab_rows} "
            f"with_admission_number={tab_admissions} header_row={hidx} "
            f"admission_col={c_adm}",
            file=sys.stderr,
        )
        tab_results.append({
            "gid": gid,
            "grade": tab_grade,
            "rows": tab_rows,
            "with_admission_number": tab_admissions,
            "header_row": hidx,
            "admission_col": c_adm,
        })

    # dedup by admission_number if present else (name, grade)
    seen = {}
    out = []
    for s in all_rows:
        key = ("ADM:" + s["admission_number"]) if s["admission_number"] else ("NG:" + s["student"].upper() + "|" + s["grade"])
        if key in seen:
            continue
        seen[key] = 1
        out.append(s)

    with open("/home/ubuntu/erp-build/live_pi_sheet.json", "w") as f:
        json.dump(out, f, indent=2)
    with open("/home/ubuntu/erp-build/live_pi_sheet_tabs.json", "w") as f:
        json.dump(tab_results, f, indent=2)
    with_adm = sum(1 for s in out if s["admission_number"])
    print("raw_active_rows", raw)
    print("unique_students", len(out))
    print("with_admission_number", with_adm)
    print("without_admission_number", len(out) - with_adm)
    grades = {}
    for s in out:
        grades[s["grade"]] = grades.get(s["grade"], 0) + 1
    print("distinct_grades", len(grades))


if __name__ == "__main__":
    main()
