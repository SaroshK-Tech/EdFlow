# EdFlow By AlgoriSync — Production Deployment (Windows LAN server)

This runbook follows the spec's deployment goal (spec §39): install on a local
Windows server/computer and use it through browsers on the school LAN, fully
offline-first. No cloud dependency for core operations.

## 1. Architecture

```
                School computers (browsers)
                         |
                         |  LAN / Wi-Fi   (http://192.168.x.x:8000)
                         v
         ┌───────────────────────────────┐
         │  Windows server / PC          │
         │   Daphne (ASGI) → :8000       │  HTTP + WebSockets
         │   EdFlow Django               │
         │   PostgreSQL (local)          ├─┐
         │   media/  backups/  logs/     │ │ (optional) Redis
         └───────────────┬───────────────┘ │
                         │ local network   │
         Android Communication Gateway ├──┘
         (SMS via SIM / WhatsApp via WiFi)
```

- **Daphne** serves both HTTP and WebSockets (attendance, notifications,
  dashboard) from a single process — no separate reverse proxy required.
- **PostgreSQL** is the production database (SQLite is dev/prototype only).
- **Redis + Celery** are optional. Background jobs and the WebSocket channel
  layer work without them in single-process setups (in-memory fallback).
- The **Android Gateway** is optional and talks to Django over LAN/USB.

## 2. Prerequisites

| Software   | Version / notes                                  |
|------------|--------------------------------------------------|
| Windows    | Server 2016+/10/11 (64-bit)                      |
| Python     | 3.11+ from python.org (tick *Add to PATH*)       |
| PostgreSQL | 14+ — use the official Windows installer         |
| Git        | optional (to clone/update the source)            |

Optional: Redis (Windows port / WSL, or a Linux box on LAN), an Android phone
with the EdFlow Gateway app.

## 3. Install EdFlow

1. Copy the project folder to the server, e.g. `C:\EdFlow` (do **not** put it
   under a user profile path with spaces if you can avoid it).
2. Open a command prompt in `C:\EdFlow` and run:

   ```bat
   setup_windows.bat
   ```

   This creates `.venv`, installs `requirements.txt`, creates runtime folders,
   copies `.env.example` to `.env`, runs `migrate`, seeds system roles, creates
   the administrator (only if `ADMIN_USERNAME`/`ADMIN_PASSWORD` are set), and
   runs `collectstatic`.

3. **Configure PostgreSQL** (skip this only for a SQLite prototype). Connect
   with `psql` as the postgres superuser and run:

   ```sql
   CREATE USER edflow WITH PASSWORD 'choose-a-strong-password';
   CREATE DATABASE edflow OWNER edflow;
   GRANT ALL PRIVILEGES ON DATABASE edflow TO edflow;
   ```

4. Edit `.env`:

   ```ini
   # Core
   SECRET_KEY=<output of: python -c "import secrets; print(secrets.token_urlsafe(50))">
   DEBUG=False
   ALLOWED_HOSTS=localhost,127.0.0.1,192.168.1.10,edflow.local

   # Database (PostgreSQL for production)
   DB_HOST=127.0.0.1
   DB_PORT=5432
   DB_NAME=edflow
   DB_USER=edflow
   DB_PASSWORD=<the password from step 3>

   # Optional: an admin you want created automatically
   ADMIN_USERNAME=admin
   ADMIN_PASSWORD=<a strong password>
   ADMIN_EMAIL=admin@school.local

   # Timezone of the school
   TIME_ZONE=Asia/Kolkata

   # Only if you run behind a TLS reverse proxy
   # COOKIE_SECURE=true
   # ENABLE_HSTS=true

   # Shared secret used by the Android Communication Gateway
   COMMUNICATION_GATEWAY_TOKEN=<long random string>
   ```

5. Re-run migrations/collectstatic if needed:

   ```bat
   .venv\Scripts\activate
   python manage.py migrate
   python manage.py create_admin
   python manage.py collectstatic --noinput
   ```

6. Verify the production sanity checks:

   ```bat
   .venv\Scripts\python.exe manage.py check --deploy --settings=project.settings.prod
   ```

## 4. Start the server

```bat
start_server.bat                  # binds 0.0.0.0:8000
start_server.bat 0.0.0.0 8080     # custom port
```

Open `http://localhost:8000` on the server, then from a school computer open
`http://<server-LAN-IP>:8000` (find the IP with `ipconfig`).

For automatic startup on boot, add `start_server.bat` to the Windows Startup
folder, or create a scheduled task:

```bat
schtasks /Create /TN EdFlow /SC ONSTART /RU SYSTEM /RL HIGHEST /TR "C:\EdFlow\start_server.bat"
```

## 5. Automatic backups

Backups run offline to a local disk, USB/external HDD or a network share.
Configure destinations under **Backup & Restore** in the app (once), then
schedule daily backups with Windows Task Scheduler:

```bat
schtasks /Create /TN EdFlowBackup /SC DAILY /ST 01:00 ^
  /TR "C:\EdFlow\.venv\Scripts\python.exe C:\EdFlow\manage.py backup_now --all --verify --settings=project.settings.prod"
```

Backups land in the configured destination folders, are SHA-256 verified, and
older archives are pruned according to each profile's retention setting.
Restore (with an automatic pre-restore safety backup) is available in the UI
and is superuser-only.

## 6. Media & static files

- `collectstatic` copies Bootstrap/JS/vendor assets to `staticfiles/` (served
  by WhiteNoise). Re-run it after every code update.
- User uploads (photos, documents, generated PDFs) live in `media/`. It is
  included in each daily backup archive automatically.
- `backups/` and `logs/` are also created automatically.

## 7. Optional: Redis / Celery

- For larger schools, run a local Redis and point `REDIS_URL` at it so Celery
  can process backups, message queues and report generation in the background.
- Background workers:

  ```bat
  .venv\Scripts\activate
  set DJANGO_SETTINGS_MODULE=project.settings.prod
  celery -A project worker -l info
  ```

  WebSockets then use the Redis channel layer instead of in-memory.

## 8. Upgrading

```bat
git pull
setup_windows.bat                 # installs changes, migrates, collects static
start_server.bat
```

Always take a verification-approved backup before upgrading. `setup_windows.bat`
never deletes data.

## 9. Security notes (school LAN)

- Keep `DEBUG=False` and pin `ALLOWED_HOSTS` (the prod settings reject the
  wildcard and refuse to run with an unset `DB_HOST`).
- Use strong `SECRET_KEY` and `COMMUNICATION_GATEWAY_TOKEN` values.
- The admin is served at `/admin/` by default; set `ADMIN_URL` in `.env`
  (e.g. `ADMIN_URL=manage-school`) to a private path.
- Restrict the Docker-style exposure: the app is designed for intranet use.
  **Do not expose port 8000 to the public Internet without a VPN or a TLS
  reverse proxy.** If you add TLS, set `COOKIE_SECURE=true` and `ENABLE_HSTS=true`.
- Superuser accounts created via `create_admin` print a reminder to change any
  default password immediately.

## 10. Troubleshooting

| Symptom | Fix |
|---|---|
| `SECRET_KEY is not set` | Set `SECRET_KEY` in `.env` |
| `ALLOWED_HOSTS must be pinned` | Fill `ALLOWED_HOSTS` (no `*`) |
| `DB_HOST is not set` | Set the `DB_*` variables (PostgreSQL) |
| `django.db.OperationalError: connection refused` | PostgreSQL not running / wrong port or password |
| Static files missing | Re-run `python manage.py collectstatic --noinput` |
| Can't reach from another PC | Allow port 8000 in Windows Firewall; check `ipconfig` |
| Gateway rejects requests | `COMMUNICATION_GATEWAY_TOKEN` differs between `.env` and the app |
| Migrations out of sync | `python manage.py migrate` after every update |