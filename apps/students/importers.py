import re
import csv
import io
from datetime import datetime

from apps.academics.models import Class, Section
from apps.houses.models import House
from apps.parents.models import Parent

from .models import Status, Student

# Canonical header key -> display label (for error messages).
HEADER_MAP = {
    "admission_no": "Admission No",
    "registration_number": "Registration No",
    "roll_number": "Roll No",
    "first_name": "First Name",
    "middle_name": "Middle Name",
    "last_name": "Last Name",
    "gender": "Gender",
    "klass": "Class",
    "section": "Section",
    "status": "Status",
    "phone": "Phone",
    "email": "Email",
    "address": "Address",
    "date_of_birth": "Date of Birth",
    "house": "House",
    "previous_school": "Previous School",
    "medical_notes": "Medical Notes",
    "remarks": "Remarks",
    "parent_name": "Parent/Guardian Name",
    "parent_phone": "Parent/Guardian Phone",
    "parent_email": "Parent/Guardian Email",
    "parent_relationship": "Parent Relationship",
}

# Accepted header spellings -> canonical key.
HEADER_ALIASES = {
    "admission no": "admission_number",
    "admission_no": "admission_number",
    "admission": "admission_number",
    "reg no": "registration_number",
    "regulation number": "registration_number",
    "registration no": "registration_number",
    "roll no": "roll_number",
    "roll": "roll_number",
    "first name": "first_name",
    "firstname": "first_name",
    "middle name": "middle_name",
    "middlename": "middle_name",
    "last name": "last_name",
    "lastname": "last_name",
    "surname": "last_name",
    "sex": "gender",
    "gender": "gender",
    "class": "klass",
    "class name": "klass",
    "klass": "klass",
    "grade": "klass",
    "section": "section",
    "status": "status",
    "phone": "phone",
    "mobile": "phone",
    "telephone": "phone",
    "email": "email",
    "address": "address",
    "dob": "date_of_birth",
    "date of birth": "date_of_birth",
    "birth date": "date_of_birth",
    "house": "house",
    "previous school": "previous_school",
    "medical notes": "medical_notes",
    "medical": "medical_notes",
    "remarks": "remarks",
    "notes": "remarks",
    "parent/guardian name": "parent_name",
    "parent guardian name": "parent_name",
    "parent name": "parent_name",
    "parent/guardian phone": "parent_phone",
    "parent guardian phone": "parent_phone",
    "parent phone": "parent_phone",
    "parent/guardian email": "parent_email",
    "parent guardian email": "parent_email",
    "parent email": "parent_email",
    "parent relationship": "parent_relationship",
    "relationship": "parent_relationship",
}

GENDER_VALUES = {"male", "female", "other"}
GENDER_ALIASES = {
    "m": "male", "male": "male", "boy": "male", "mr": "male",
    "f": "female", "female": "female", "girl": "female", "miss": "female",
    "other": "other",
}
STATUS_VALUES = {"active", "inactive", "left", "graduated", "suspended"}
STATUS_ALIASES = {
    "active": "active", "current": "active", "enrolled": "active",
    "inactive": "inactive",
    "left": "left", "withdrawn": "left", "transferred": "left",
    "graduated": "graduated",
    "suspended": "suspended", "expelled": "suspended",
}
DATE_FORMATS = ("%Y-%m-%d", "%d/%m/%Y", "%m/%d/%Y", "%d-%m-%Y")


def _wanted_keys():
    return set(HEADER_MAP) | set(HEADER_ALIASES.values())


def normalize_header(cell):
    """Normalise a header cell to aliased form: lower, strip, collapse spaces,
    hyphen→space, strip non-alphanumerics."""
    value = str(cell or "").strip()
    value = value.replace("-", " ").replace("_", " ").replace("/", " ")
    value = re.sub(r"\s+", " ", value).strip()
    value = re.sub(r"[^a-z0-9 ]", "", value.lower())
    return value


def io_string(text):
    return io.StringIO(text)


def parse_csv_file(uploaded_file):
    """Read/decode upload, sniff dialect, return (canonical_columns, rows) where
    rows are dicts of canonical key -> cell text and skip a stray BOM."""
    raw = uploaded_file.read()
    text = raw.decode("utf-8-sig") if raw[:3] == b"\xef\xbb\xbf" else raw.decode("utf-8", errors="replace")
    sample = text[:4096]
    try:
        dialect = csv.Sniffer().sniff(sample, delimiters=",;\t")
    except csv.Error:
        dialect = csv.excel
    reader = csv.reader(io_string(text), dialect)
    rows = [r for r in reader]

    if not rows:
        return [], [], []

    header = rows[0]
    columns = []
    alias_list = []
    for cell in header:
        columns.append(HEADER_ALIASES.get(normalize_header(cell)))
        alias_list.append(normalize_header(cell))

    data = []
    for row in rows[1:]:
        if not any(str(c).strip() for c in row):
            continue
        record = {}
        for idx, col in enumerate(columns):
            if col is None:
                continue
            record[col] = (row[idx] if idx < len(row) else "").strip()
        if record:
            data.append(record)
    return columns, alias_list, data


def _parse_date(value):
    value = (value or "").strip()
    if not value:
        return None
    for fmt in DATE_FORMATS:
        try:
            return datetime.strptime(value, fmt).date()
        except ValueError:
            continue
    raise ValueError(f"Unrecognised date {value!r} (try YYYY-MM-DD)")


def resolve_row_data(data):
    """Mutate `data` (plain string values) adding resolved objects:
    date_of_birth -> date, _class/_section/_house -> model instances, and
    normalised gender/status. Raises ValueError on a problem.
    """
    gender = (data.get("gender") or "").strip().lower()
    if gender:
        data["gender"] = GENDER_ALIASES.get(gender, gender)
        if data["gender"] not in GENDER_VALUES:
            raise ValueError(f"Unknown gender {data['gender']!r}")

    status = (data.get("status") or "").strip().lower()
    if status:
        data["status"] = STATUS_ALIASES.get(status, status)
        if data["status"] not in STATUS_VALUES:
            raise ValueError(f"Unknown status {data['status']!r}")

    dob = (data.get("date_of_birth") or "").strip()
    if dob:
        data["date_of_birth"] = _parse_date(dob)

    klass_name = (data.get("klass") or "").strip()
    if klass_name:
        klass = Class.objects.filter(name=klass_name).first()
        if not klass:
            raise ValueError(f"Class {klass_name!r} does not exist")
        data["_class"] = klass
        section_name = (data.get("section") or "").strip()
        if section_name:
            section = Section.objects.filter(klass=klass, name=section_name).first()
            if not section:
                raise ValueError(f"Section {section_name!r} not found in {klass_name}")
            data["_section"] = section
    elif (data.get("section") or "").strip():
        raise ValueError("Section given but Class is missing")

    house_name = (data.get("house") or "").strip()
    if house_name:
        house = House.objects.filter(name=house_name).first()
        if not house:
            raise ValueError(f"House {house_name!r} does not exist")
        data["_house"] = house
    return data


def parse_and_validate(uploaded_file):
    """Validate an uploaded CSV.

    Returns (valid_rows, error_rows, summary) where each row item is a dict:
        row_number, data, errors
    and summary is a dict with counts plus any header-level warnings.
    """
    columns, alias_list, rows = parse_csv_file(uploaded_file)

    unknown = sorted({h or "?" for idx, h in enumerate(alias_list) if columns[idx] is None})
    warning = []
    if unknown:
        warning.append(
            f"Ignored unrecognised column(s): {', '.join(unknown)}. "
            f"Supported: {', '.join(sorted(HEADER_MAP.values()))}."
        )

    required = ["admission_number", "first_name"]
    valid, errors = [], []

    if not rows:
        return valid, errors, {
            "row_count": 0,
            "valid": 0,
            "error": 1,
            "warnings": warning or ["File appears empty (no data rows)."],
        }

    if not any(c is not None for c in columns):
        # Nothing in the header matched at all.
        return valid, errors, {
            "row_count": len(rows),
            "valid": 0,
            "error": len(rows),
            "warnings": warning
            or ["No columns matched. Expected headers e.g. "
                "Admission No, First Name, Class, Section, Gender, Phone..."],
        }

    existing_numbers = set(
        Student.objects.filter(
            admission_number__in=[r.get("admission_number", "") for r in rows]
        ).values_list("admission_number", flat=True)
    )

    valid_count = 0
    for idx, row in enumerate(rows, start=2):
        data = dict(row)
        errs = []

        for key in required:
            if not (data.get(key) or "").strip():
                errs.append(f"Missing {HEADER_MAP[key]}")

        admission = (data.get("admission_number") or "").strip()
        if admission and admission in existing_numbers:
            errs.append(f"Admission No {admission} already in database")

        try:
            resolve_row_data(data)
        except ValueError as exc:
            errs.append(str(exc))

        item = {"row_number": idx, "data": data, "errors": errs}
        if errs:
            errors.append(item)
        else:
            valid.append(item)
            valid_count += 1

    return valid, errors, {
        "row_count": len(rows),
        "valid": valid_count,
        "error": len(errors),
        "warnings": warning,
    }


def serialize_rows(valid_rows, error_rows):
    """Convert validated/dubious rows to a JSON-safe list for the session."""
    payload = []
    for kind, items in (("valid", valid_rows), ("error", error_rows)):
        for item in items:
            data = dict(item["data"])
            for key in list(data):
                if key.startswith("_"):
                    data.pop(key, None)
            if data.get("date_of_birth"):
                data["date_of_birth"] = data["date_of_birth"].isoformat()
            payload.append(
                {"kind": kind, "row_number": item["row_number"],
                 "data": data, "errors": list(item["errors"])}
            )
    return payload


def commit_import(valid_rows, request=None, skip_guardians=False):
    """Persist validated rows. Returns dict with counts.
    Parent/guardian rows are deduped by (name, phone, email)."""
    from apps.core.logging import audit

    created_numbers = []
    parent_count = 0
    parent_cache = {}

    for item in valid_rows:
        d = resolve_row_data(dict(item["data"]))
        student = Student.objects.create(
            admission_number=d.get("admission_number"),
            registration_number=(d.get("registration_number") or None),
            roll_number=d.get("roll_number", "") or "",
            first_name=d.get("first_name"),
            middle_name=d.get("middle_name", "") or "",
            last_name=d.get("last_name", "") or "",
            date_of_birth=d.get("date_of_birth"),
            gender=d.get("gender", "") or "",
            phone=d.get("phone", "") or "",
            email=d.get("email", "") or "",
            address=d.get("address", "") or "",
            klass=d.get("_class"),
            section=d.get("_section"),
            house=d.get("_house"),
            status=d.get("status", Status.ACTIVE) or Status.ACTIVE,
            previous_school=d.get("previous_school", "") or "",
            medical_notes=d.get("medical_notes", "") or "",
            remarks=d.get("remarks", "") or "",
        )
        created_numbers.append(student.admission_number)
        if request:
            audit(request, f"student.import {student.admission_number}")

        if skip_guardians:
            continue

        parent_name = (d.get("parent_name") or "").strip()
        parent_phone = (d.get("parent_phone") or "").strip()
        parent_email = (d.get("parent_email") or "").strip()
        parent_rel = (d.get("parent_relationship") or "").strip()

        if parent_name or parent_phone or parent_email:
            key = (parent_name, parent_phone, parent_email)
            parent = parent_cache.get(key)
            if not parent:
                parts = parent_name.split(" ", 1)
                parent = Parent.objects.create(
                    first_name=parts[0] or (parent_phone or "Guardian"),
                    last_name=parts[1] if len(parts) > 1 else "",
                    relationship=parent_rel or "Guardian",
                    phone=parent_phone,
                    email=parent_email,
                )
                parent_cache[key] = parent
                parent_count += 1
            parent.students.add(student)
            if not parent.is_primary:
                parent.is_primary = True
                parent.save(update_fields=["is_primary"])

    return {
        "created": len(created_numbers),
        "numbers": created_numbers,
        "parents": parent_count,
    }