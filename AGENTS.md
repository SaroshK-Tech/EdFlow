# AGENTS.md

## Context
"EdFlow By AlgoriSync" is an offline-first, single-school School Management System (Django).
The repo is greenfield: **no code yet**. `ProjectDetails.txt` is the authoritative spec
(1284 lines). Read it before implementing anything — it is the contract for scope, modules,
and constraints. There is no README, git history, or existing app to mimic.

## Mandatory reading / references
- `ProjectDetails.txt` — the full requirements spec.
- `suggested_layout/` — UI mockups (`.webp`). Spec §28 explicitly REQUIRES inspecting these
  before implementing the interface and treating them as UX/UI guidance.

## Constraints that are easy to get wrong
- **Offline-first**: every core school operation must work with no internet. Internet features
  (WhatsApp, SMS APIs, cloud, online payments, AI) are optional add-ons and must never block
  normal operation.
- **V1 = exactly ONE school**. Do NOT implement campuses, branches, multi-tenant, or SaaS.
  Keep the architecture extensible for them later, but do not build the complexity now.
- **Modular Django monolith** is preferred; avoid microservices.
- **Timetable generator** is the flagship feature: deterministic, offline, built with
  Google OR-Tools CP-SAT. AI must NOT be required for it.
- **SMS communication**: outbound messages go through a local Android gateway app talking to
  Django via local API/USB/LAN — prefer that over ADB/UI automation and over making the system
  depend on an external SMS API. All outbound messages are queued with status/retry state.
- **Primary DB is PostgreSQL**; SQLite is acceptable only for small dev/prototype.
- **No cloud AI in V1**; any future AI is optional and local (Ollama/llama.cpp-compatible),
  and must enforce the logged-in user's permissions.

## Project conventions (mandatory, per spec §30–31)
- Dedicated virtual env at `.venv/` — never committed, never copied between machines; recreate
  per machine from `requirements.txt`.
- Keep root `requirements.txt` in sync whenever dependencies change.
- Provide/run `setup_windows.bat` as the Windows setup entrypoint.
- `.gitignore` must exclude `.venv/`, `__pycache__/`, `*.pyc`, `.env`, secrets, logs, local
  databases, backups, IDE files. Never commit credentials.

## Stack commitment (spec §29)
Django + DRF (where APIs are needed) · Django templates + HTML5/CSS3 + Bootstrap 5 + JS/AJAX
· Celery + Redis for background jobs · Django Channels/WebSockets for real-time · WeasyPrint
and/or ReportLab for PDFs · openpyxl for Excel · Pandas/NumPy for data · Chart.js for charts ·
deploy target is a local Windows server on the school LAN.

## Suggested Django app structure (spec §38, adjustable)
`core, accounts, school, students, parents, admissions, academics, timetable, attendance,
staff, hr, payroll, houses, exams, results, progress, fees, finance, transport, library,
inventory, discipline, communication, documents, reports, notifications, backup, hardware`