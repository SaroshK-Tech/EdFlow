"""Tests for the students CSV bulk-import pipeline (spec §5)."""

import io

from django.contrib.auth import get_user_model
from django.test import TestCase

from apps.academics.models import Class, Section
from apps.houses.models import House
from apps.parents.models import Parent
from apps.students.models import Student

from . import importers

U = get_user_model()


def _upload(text):
    class F:
        def __init__(self, data):
            self.data = data.encode("utf-8")

        def read(self):
            return self.data

    return F(text)


class HeaderNormaliseTests(TestCase):
    def test_various_spellings_map(self):
        cases = {
            "Admission No": "admission_number",
            "admission_no": "admission_number",
            "First Name": "first_name",
            "Parent/Guardian Name": "parent_name",
            "Date of Birth": "date_of_birth",
            "DOB": "date_of_birth",
            "Reg No.": "registration_number",
        }
        for header, key in cases.items():
            resolved = importers.HEADER_ALIASES[importers.normalize_header(header)]
            self.assertEqual(resolved, key)


class ParseCsvTests(TestCase):
    def test_semi_colon_delimited(self):
        upload = _upload("Admission No;First Name;Gender\nADM1;Zara;Female\n")
        columns, alias_list, rows = importers.parse_csv_file(upload)
        self.assertEqual(columns[0], "admission_number")
        self.assertEqual(rows[0]["gender"], "Female")
        self.assertEqual(alias_list[0], "admission no")

    def test_unknown_header_is_none(self):
        upload = _upload("Admission No;Something Else\nADM1;x\n")
        columns, _, rows = importers.parse_csv_file(upload)
        self.assertEqual(columns[1], None)
        self.assertEqual(len(rows), 1)


class ResolveRowTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.klass = Class.objects.create(name="Grade 6")
        cls.section = Section.objects.create(klass=cls.klass, name="A")
        cls.house = House.objects.create(name="Blue")

    def test_resolve_objects(self):
        data = {
            "klass": "Grade 6",
            "section": "A",
            "house": "Blue",
            "gender": "m",
            "status": "current",
            "date_of_birth": "2014-05-06",
        }
        importers.resolve_row_data(data)
        self.assertEqual(data["_class"], self.klass)
        self.assertEqual(data["_section"], self.section)
        self.assertEqual(data["_house"], self.house)
        self.assertEqual(data["gender"], "male")
        self.assertEqual(data["status"], "active")
        self.assertEqual(str(data["date_of_birth"]), "2014-05-06")

    def test_missing_class_raises(self):
        with self.assertRaises(ValueError):
            importers.resolve_row_data({"klass": "Grade 99"})

    def test_section_without_class_raises(self):
        with self.assertRaises(ValueError):
            importers.resolve_row_data({"section": "A"})

    def test_bad_dob_raises(self):
        with self.assertRaises(ValueError):
            importers.resolve_row_data({"date_of_birth": "nonsense"})


class ParseAndValidateTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.klass = Class.objects.create(name="Grade 5")

    def test_happy_path(self):
        upload = _upload(
            "Admission No,First Name,Class,Gender\n"
            "G5-100,Asha,Grade 5,Female\n"
            "G5-101,Ben,Grade 5,Male\n"
        )
        valid, errors, summary = importers.parse_and_validate(upload)
        self.assertEqual(summary["row_count"], 2)
        self.assertEqual(len(valid), 2)
        self.assertEqual(len(errors), 0)

    def test_missing_required_fields(self):
        upload = _upload("Admission No,First Name\nG5-200,\n\nG5-201,\n")
        valid, errors, summary = importers.parse_and_validate(upload)
        self.assertEqual(len(valid), 0)
        self.assertEqual(len(errors), 2)
        self.assertTrue(any("Missing First Name" in e for e in errors[0]["errors"]))

    def test_duplicate_admission_number(self):
        Student.objects.create(admission_number="G5-DUP", first_name="Existing")
        upload = _upload("Admission No,First Name\nG5-DUP,New\n")
        _, errors, _ = importers.parse_and_validate(upload)
        self.assertTrue(any("already in database" in e for e in errors[0]["errors"]))

    def test_empty_file(self):
        upload = _upload("")
        _, _, summary = importers.parse_and_validate(upload)
        self.assertEqual(summary["row_count"], 0)
        self.assertEqual(summary["error"], 1)


class CommitImportTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.klass = Class.objects.create(name="Grade 4")
        cls.user = U.objects.create_superuser("import-user", "x@x.test", "pw")

    def test_creates_students_and_dedupes_parents(self):
        data = {
            "admission_number": "G4-1",
            "first_name": "Tara",
            "klass": "Grade 4",
            "gender": "f",
            "parent_name": "Mama Tara",
            "parent_phone": "0711111111",
        }
        importers.resolve_row_data(data)
        importers.commit_import([{"data": data}], request=None)
        st = Student.objects.get(admission_number="G4-1")
        self.assertEqual(st.klass, self.klass)
        self.assertEqual(st.gender, "female")
        parent = Parent.objects.get(phone="0711111111")
        self.assertIn(st, parent.students.all())
        self.assertTrue(parent.is_primary)

    def test_parent_dedupe_shared_across_two_students(self):
        rows = []
        for n in ("G4-2", "G4-3"):
            data = {
                "admission_number": n,
                "first_name": f"Kid {n}",
                "klass": "Grade 4",
                "parent_name": "Shared Parent",
                "parent_phone": "0722222222",
            }
            importers.resolve_row_data(data)
            rows.append({"data": data})
        result = importers.commit_import(rows, request=None)
        self.assertEqual(result["created"], 2)
        self.assertEqual(result["parents"], 1)
        self.assertEqual(Parent.objects.filter(phone="0722222222").count(), 1)

    def test_skip_guardians(self):
        data = {
            "admission_number": "G4-4",
            "first_name": "NoParent",
            "klass": "Grade 4",
            "parent_name": "Should Not Exist",
            "parent_phone": "0733333333",
        }
        importers.resolve_row_data(data)
        importers.commit_import([{"data": data}], request=None, skip_guardians=True)
        self.assertEqual(Parent.objects.count(), 0)


class SerializeRowTests(TestCase):
    def test_public_fields_and_iso_dates_only(self):
        data = {
            "admission_number": "A1",
            "date_of_birth": __import__("datetime").date(2014, 5, 6),
            "_class": "not-serialisable",
        }
        importers.resolve_row_data = lambda d: d
        payload = importers.serialize_rows(
            [{"row_number": 2, "data": dict(data), "errors": []}], []
        )
        item = payload[0]
        self.assertEqual(item["kind"], "valid")
        self.assertEqual(item["row_number"], 2)
        self.assertNotIn("_class", item["data"])
        self.assertEqual(item["data"]["date_of_birth"], "2014-05-06")