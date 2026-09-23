from django.core.management.base import BaseCommand

from apps.communication.models import Channel, MessageTemplate, MessageBatch, Outbox

SYSTEM_TEMPLATES = {
    "student_absent": {
        "name": "Student Absent",
        "channel": Channel.SMS,
        "body": "Dear {parent_name}, this is to inform you that {student_name} "
        "({admission_number}) of class {class_name} was absent on {date}. "
        "- {school_name}",
    },
    "late_arrival": {
        "name": "Late Arrival",
        "channel": Channel.SMS,
        "body": "Dear {parent_name}, {student_name} ({admission_number}) arrived late "
        "today {date}. Kindly ensure prompt arrival. - {school_name}",
    },
    "fee_reminder": {
        "name": "Fee Reminder",
        "channel": Channel.SMS,
        "body": "Dear {parent_name}, this is a friendly reminder that fees for "
        "{student_name} ({admission_number}) are due. Thank you. - {school_name}",
    },
    "fee_overdue": {
        "name": "Fee Overdue",
        "channel": Channel.SMS,
        "body": "Dear {parent_name}, fees for {student_name} ({admission_number}) "
        "are now overdue. Please clear the balance as soon as possible. - {school_name}",
    },
    "result_announcement": {
        "name": "Result Announcement",
        "channel": Channel.WHATSAPP,
        "body": "Dear {parent_name}, results for {student_name} ({admission_number}) "
        "are now available for collection. - {school_name}",
    },
    "ptm_reminder": {
        "name": "PTM Reminder",
        "channel": Channel.SMS,
        "body": "Dear {parent_name}, Parent-Teacher Meeting for {student_name} "
        "({admission_number}) is scheduled. Kindly attend. - {school_name}",
    },
    "homework": {
        "name": "Homework",
        "channel": Channel.WHATSAPP,
        "body": "Dear {parent_name}, homework for {student_name} ({admission_number}) "
        "has been assigned today. Please supervise completion. - {school_name}",
    },
    "assignment": {
        "name": "Assignment",
        "channel": Channel.WHATSAPP,
        "body": "Dear {parent_name}, {student_name} ({admission_number}) has a new "
        "assignment submission due. Kindly assist. - {school_name}",
    },
    "exam_reminder": {
        "name": "Exam Reminder",
        "channel": Channel.SMS,
        "body": "Dear {parent_name}, examinations for {student_name} start soon. "
        "Please ensure adequate preparation. - {school_name}",
    },
    "holiday_notice": {
        "name": "Holiday Notice",
        "channel": Channel.SMS,
        "body": "Dear {parent_name}, the school will be closed for holidays from {date}. "
        "School resumes on the next working day. - {school_name}",
    },
    "emergency_announcement": {
        "name": "Emergency Announcement",
        "channel": Channel.SMS,
        "body": "EMERGENCY: {parent_name}, {school_name} has issued an urgent notice. "
        "Kindly contact the school immediately.",
    },
    "admission_confirmation": {
        "name": "Admission Confirmation",
        "channel": Channel.SMS,
        "body": "Dear {parent_name}, we are pleased to confirm admission of "
        "{student_name} ({admission_number}) into class {class_name}. Welcome! - {school_name}",
    },
    "transport_notification": {
        "name": "Transport Notification",
        "channel": Channel.SMS,
        "body": "Dear {parent_name}, a transport update for {student_name} "
        "({admission_number}). Kindly check with the transport office. - {school_name}",
    },
    "staff_notification": {
        "name": "Staff Notification",
        "channel": Channel.WHATSAPP,
        "body": "Attention staff: an official notice has been posted. Please check the "
        "staff portal for details. - {school_name}",
    },
    "general_announcement": {
        "name": "General Announcement",
        "channel": Channel.SMS,
        "body": "Dear {parent_name}, {school_name} wishes to inform you of the "
        "following: please check the school notice board.",
    },
}


class Command(BaseCommand):
    help = "Seed (or update) the system message templates and clear test queues."

    def handle(self, *args, **options):
        created = 0
        updated = 0
        for key, spec in SYSTEM_TEMPLATES.items():
            exists = MessageTemplate.objects.filter(key=key).exists()
            defaults = {
                "name": spec["name"],
                "channel": spec["channel"],
                "body": spec["body"],
                "is_system": True,
            }
            if exists:
                MessageTemplate.objects.filter(key=key).update(**defaults)
                updated += 1
            else:
                MessageTemplate.objects.update_or_create(
                    key=key, defaults={**defaults, "is_active": True}
                )
                created += 1
        self.stdout.write(
            self.style.SUCCESS(
                f"System message templates ready: {created} created, {updated} updated."
            )
        )