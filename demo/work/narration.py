"""Generate per-scene voiceover narration with edge-tts (neural voices).

Writes mp3 files under demo/work/audio/<key>.mp3 and a JSON manifest with
each scene's duration (from ffprobe).
"""

import asyncio
import json
import subprocess
from pathlib import Path

import edge_tts

VOICE = "en-US-AriaNeural"
RATE = "+4%"

ROOT = Path(__file__).resolve().parent.parent
AUDIO = ROOT / "work" / "audio"
AUDIO.mkdir(parents=True, exist_ok=True)


NARRATION = {
    "open": (
        "EdFlow, by AlgoriSync. The offline-first school management system. "
        "Built for the classroom, and designed for schools where the internet "
        "cannot be relied upon."
    ),
    "dashboard": (
        "One dashboard, the whole school. Thirty learners, twelve staff, "
        "device health, and fee collections beyond four hundred thousand "
        "shillings — every number live, and held locally."
    ),
    "students": (
        "The complete register. Thirty learners across eight classes, each "
        "with a class, a house and guardians — searchable in one list, with "
        "no cloud involved."
    ),
    "student_detail": (
        "A learner's file at a glance: admission number, class, house, "
        "guardians and attendance — all in a single offline record."
    ),
    "timetable": (
        "The flagship. A full term of three hundred and twenty lessons across "
        "eight classes, scheduled deterministically by Google OR-Tools — "
        "fully offline, with no artificial intelligence required."
    ),
    "attendance": (
        "This morning's register: twenty four present, two late, two absent. "
        "Captured in a few seconds, and posted straight to each record."
    ),
    "fees": (
        "Fees that make sense. Four fee heads — tuition, transport, lunch and "
        "activity — with termly vouchers and scholarships applied "
        "automatically."
    ),
    "finance": (
        "Finance in real time. Over four hundred thousand shillings collected, "
        "expenditure near eighty two thousand, and a live cash-flow view "
        "ready to export."
    ),
    "payroll": (
        "Payroll in September: twelve staff, one run. Allowances and "
        "statutory deductions calculated together, and itemised per person."
    ),
    "payroll_run": (
        "Every slip is itemised — gross, allowances, deductions and net pay — "
        "with a pay slip generated for each staff member, printable locally."
    ),
    "staff": (
        "Human resources, end to end. Twelve staff across departments, with "
        "records, documents and ID cards — all produced on the premises."
    ),
    "staff_detail": (
        "Each profile carries role, department and employment details — with "
        "an ID card ready to print in one click."
    ),
    "parents": (
        "Twenty five guardians linked to their children, ready for a secure "
        "portal account the moment the school chooses to open it."
    ),
    "hardware": (
        "Hardware that reports home. Six devices — gateway, printers, "
        "scanners, projector and desktops — with live health across campus."
    ),
    "maintenance": (
        "And when equipment needs attention, maintenance tickets are tracked "
        "from report to resolution by the school's own local team."
    ),
    "communication": (
        "Communications that work with no data. Twelve queued messages, "
        "delivered through a local Android gateway on the school LAN."
    ),
    "notifications": (
        "Announcements reach exactly the right audience — staff, teachers, "
        "or a single class — with a full audit trail of who was told."
    ),
    "reports": (
        "Reports and exports whenever you need them. Excel and PDF generated "
        "on the server, with nothing uploaded anywhere."
    ),
    "close": (
        "EdFlow by AlgoriSync. One Windows server, one school, fully "
        "connected even when the internet is not. Deploy it, and forget "
        "the outages."
    ),
}

LOWER_THIRDS = {
    "dashboard": "Overview · School Dashboard",
    "students": "Students · Master Register",
    "student_detail": "Students · Learner Record",
    "timetable": "Timetable · 320 Lessons, OR-Tools",
    "attendance": "Attendance · Daily Register",
    "fees": "Fees · Heads, Vouchers & Concessions",
    "finance": "Finance · Live Cash Flow",
    "payroll": "Payroll · Monthly Runs",
    "payroll_run": "Payroll · Run & Payslips",
    "staff": "Staff · HR Records",
    "staff_detail": "Staff · Profile & ID Card",
    "parents": "Parents · Guardianship",
    "hardware": "Hardware · Devices & Gateway",
    "maintenance": "Hardware · Maintenance Tickets",
    "communication": "Communication · Offline SMS Queue",
    "notifications": "Notifications · Announcements",
    "reports": "Reports · Excel & PDF Exports",
}

TITLES = {
    "open": ("EdFlow By AlgoriSync", "The Offline-First School Management System", "Product Demonstration"),
    "dashboard": ("At a Glance", "A live, local command centre for the whole school"),
    "students": ("Student Records", "Every learner, class, house and guardian"),
    "timetable": ("Master Timetable", "Deterministic scheduling with Google OR-Tools"),
    "attendance": ("Attendance", "The daily register, captured in seconds"),
    "fees": ("Fees & Concessions", "Accurate balances for every family"),
    "finance": ("Cash Flow", "Income, expenses and refunds in real time"),
    "payroll": ("Payroll", "Allowances, deductions and itemised payslips"),
    "staff": ("Staff & HR", "Records, documents and ID cards"),
    "parents": ("Parents", "Guardianship linked to every learner"),
    "hardware": ("Hardware Health", "Device status and maintenance tickets"),
    "communication": ("Offline Communication", "SMS queued locally, delivered by a LAN gateway"),
    "notifications": ("Announcements", "The right audience. Every time."),
    "reports": ("Reports & Exports", "Excel and PDF, generated on the server"),
    "close": ("EdFlow By AlgoriSync", "One server. One school. Fully offline.", "Deploy on a Windows server and forget the outages"),
}


async def synth(key, text):
    out = AUDIO / f"{key}.mp3"
    tts = edge_tts.Communicate(text, VOICE, rate=RATE)
    await tts.save(str(out))
    return out


def duration_of(path):
    probe = subprocess.run(
        ["ffprobe", "-v", "quiet", "-show_entries", "format=duration",
         "-of", "default=noprint_wrappers=1:nokey=1", str(path)],
        capture_output=True, text=True, check=True)
    return float(probe.stdout.strip())


async def main():
    manifest = {}
    total = 0.0
    for key, text in NARRATION.items():
        out = await synth(key, text)
        d = duration_of(out)
        manifest[key] = {"text": text, "duration": d, "file": str(out)}
        total += d
        print(f"{key}: {d:.2f}s")
    manifest["_meta"] = {"voice": VOICE, "rate": RATE, "total_seconds": round(total, 2)}
    (ROOT / "work" / "audio" / "manifest.json").write_text(json.dumps(manifest, indent=2))
    print(f"TOTAL NARRATION: {total:.2f}s")


if __name__ == "__main__":
    asyncio.run(main())