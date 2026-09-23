# EdFlow by AlgoriSync

An **offline-first School Management System (SMS)** — a single-school Django application
built to run entirely on the school's own LAN with no internet dependency.

## Highlights

- **Offline-first**: every core school operation works without internet. Optional add-ons
  (WhatsApp/SMS APIs, cloud, online payments, AI) never block normal operation.
- **Timetable generator**: the flagship feature — deterministic and offline, powered by
  Google OR-Tools CP-SAT. No AI required.
- **Modular Django monolith**: 27 focused apps (academics, students, staff, fees, exams,
  results, timetable, attendance, transport, library, inventory, finance, payroll, HR,
  communication, etc.).
- **SMS via local Android gateway**: outbound messages are queued in-app and delivered
  through a local gateway app over LAN/USB — no dependency on external bulk-SMS APIs.
- **Real-time UI**: Django Channels/WebSockets for live attendance, notifications and
  dashboard updates.

## Tech stack

| Layer       | Technology |
|-------------|------------|
| Backend     | Django 5 + Django REST Framework |
| Frontend    | Django templates, Bootstrap 5, HTML5/CSS3, JS/AJAX, Chart.js |
| Database    | PostgreSQL (SQLite acceptable for small dev/prototype) |
| Background  | Celery + Redis |
| Real-time   | Django Channels / WebSockets |
| PDF/Excel   | WeasyPrint / ReportLab, openpyxl |
| Data        | Pandas / NumPy |

## Quick start (Windows)

```bat
setup_windows.bat
```

This creates `.venv` from `requirements.txt`, copies `.env.example` to `.env`,
migrates the database, seeds system roles, optionally creates the admin, and
collects static files.

Edit `.env` first: set `SECRET_KEY`, `ALLOWED_HOSTS`, and the `DB_*` values.
Leave `DB_HOST` blank only for a SQLite prototype.

### Development

```bat
.venv\Scripts\activate
python manage.py runserver
```

### Production server (school LAN)

```bat
.venv\Scripts\activate
start_server.bat 0.0.0.0 8000
```

Serves HTTP + WebSockets (Daphne/ASGI) in a single process.

## Documentation

- `ProjectDetails.txt` — the authoritative requirements/spec (the contract for scope).
- `documentation/DEPLOYMENT.md` — PostgreSQL setup, backup scheduling, Android gateway.
- `suggested_layout/` — UI mockups referenced by the spec.

## Repository notes

- Dedicated virtual env at `.venv/` is never committed; recreate per machine from
  `requirements.txt`.
- Secrets (`SECRET_KEY`, `DB_PASSWORD`, `COMMUNICATION_GATEWAY_TOKEN`, ...) live in
  `.env`, never in the repo. `.env.example` is the safe template.

---

© AlgoriSync — EdFlow is a commercial product. See AlgoriSync for licensing.