from django.core.management.base import BaseCommand

from apps.documents.models import DocumentTemplate

SYSTEM_TEMPLATES = {
    "student_id_card": {
        "name": "Student ID Card",
        "body": "This certifies that {student_name} (Admission No. {admission_number}) "
        "of class {class_name} is a bonafide student of {school_name}.",
    },
    "staff_id_card": {
        "name": "Staff ID Card",
        "body": "This certifies that {student_name} is a bonafide staff member of "
        "{school_name} as recorded.",
    },
    "admission_letter": {
        "name": "Admission Letter",
        "body": "Dear Parent(s)/Guardian(s),\n\nWe are pleased to confirm the admission "
        "of {student_name} (Admission No. {admission_number}) into class {class_name} "
        "at {school_name} with effect from {joined_date}.\n\nWe look forward to a "
        "productive partnership in your ward's education.",
    },
    "bonafide_certificate": {
        "name": "Bonafide Certificate",
        "body": "This is to certify that {student_name} (Admission No. "
        "{admission_number}) is a bonafide student of class {class_name} at "
        "{school_name}. This certificate is issued on {date}.",
    },
    "character_certificate": {
        "name": "Character Certificate",
        "body": "This is to certify that {student_name} (Admission No. "
        "{admission_number}), a former student of {school_name}, was of good character "
        "and conduct during their stay with us.",
    },
    "leaving_certificate": {
        "name": "Leaving Certificate",
        "body": "This is to certify that {student_name} (Admission No. "
        "{admission_number}) of class {class_name} has been a student at {school_name} "
        "and was relieved on {date}. The student is permitted to join any other "
        "institution.",
    },
    "fee_receipt": {
        "name": "Fee Receipt",
        "body": "Received with thanks the fee payment described below:",
    },
}


class Command(BaseCommand):
    help = "Seed the system document templates."

    def handle(self, *args, **options):
        created = updated = 0
        for doc_type, spec in SYSTEM_TEMPLATES.items():
            defaults = {"name": spec["name"], "body": spec["body"], "is_system": True}
            if DocumentTemplate.objects.filter(doc_type=doc_type).exists():
                DocumentTemplate.objects.filter(doc_type=doc_type).update(**defaults)
                updated += 1
            else:
                DocumentTemplate.objects.create(
                    doc_type=doc_type, is_active=True, **defaults
                )
                created += 1
        self.stdout.write(
            self.style.SUCCESS(
                f"System document templates ready: {created} created, {updated} updated."
            )
        )