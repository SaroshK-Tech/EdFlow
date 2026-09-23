@echo off
setlocal enabledelayedexpansion

echo ==========================================
echo  EdFlow By AlgoriSync - Windows Setup
echo ==========================================
echo.

rem --- 1. Check Python ---
where python >nul 2>nul
if errorlevel 1 (
    echo [ERROR] Python not found in PATH.
    echo Please install Python 3.11+ from https://www.python.org/downloads/
    echo and make sure "Add Python to PATH" is checked.
    exit /b 1
)
for /f "tokens=*" %%i in ('python --version 2^>^&1') do set PYVER=%%i
echo [OK] Python found: %PYVER%

rem --- 2. Create .venv if missing ---
if not exist ".venv\Scripts\activate.bat" (
    echo [..] Creating virtual environment .venv ...
    python -m venv .venv
    if errorlevel 1 (
        echo [ERROR] Failed to create virtual environment.
        exit /b 1
    )
) else (
    echo [OK] Virtual environment .venv already exists.
)

rem --- 3. Activate ---
call ".venv\Scripts\activate.bat"
if errorlevel 1 (
    echo [ERROR] Failed to activate virtual environment.
    exit /b 1
)

rem --- 4. Upgrade pip ---
echo [..] Upgrading pip ...
python -m pip install --upgrade pip
if errorlevel 1 (
    echo [ERROR] Failed to upgrade pip.
    exit /b 1
)

rem --- 5. Install requirements ---
echo [..] Installing requirements from requirements.txt ...
python -m pip install -r requirements.txt
if errorlevel 1 (
    echo [ERROR] Failed to install requirements.
    exit /b 1
)

rem --- 6. Create runtime directories ---
if not exist "logs" mkdir logs
if not exist "backups" mkdir backups
if not exist "media" mkdir media
if not exist "staticfiles" mkdir staticfiles
echo [OK] Runtime directories ready (logs, backups, media, staticfiles).

rem --- 7. .env bootstrap ---
if not exist ".env" (
    echo [..] Creating .env from .env.example ...
    copy /-Y ".env.example" ".env" >nul
    echo [WARN] Edit .env now: set SECRET_KEY, ALLOWED_HOSTS and the DB_* values.
    echo        Leave DB_HOST blank only for a SQLite prototype.
) else (
    echo [OK] .env already present.
)

rem --- 8. Run migrations ---
echo [..] Applying database migrations ...
python manage.py migrate
if errorlevel 1 (
    echo [ERROR] Migration failed. Fix .env then re-run this script.
    exit /b 1
)

rem --- 9. Seed system roles ---
python manage.py seed_roles

rem --- 10. Create administrator ---
if defined ADMIN_USERNAME if defined ADMIN_PASSWORD (
    echo [..] Creating administrator user %ADMIN_USERNAME% ...
    python manage.py create_admin
) else (
    echo [..] Skipping automatic admin creation (ADMIN_USERNAME/ADMIN_PASSWORD not set).
    echo        Create one manually:  manage.py createsuperuser
)

rem --- 11. Collect static files ---
echo [..] Collecting static files ...
python manage.py collectstatic --noinput
if errorlevel 1 (
    echo [ERROR] collectstatic failed.
    exit /b 1
)

echo.
echo ==========================================
echo  Setup complete.
echo.
echo  For a school LAN/intranet server (production):
echo    .venv\Scripts\activate
echo    start_server.bat
echo.
echo  For development (SQLite, auto-reload):
echo    .venv\Scripts\activate
echo    python manage.py runserver
echo.
echo  See documentation\DEPLOYMENT.md for PostgreSQL setup, scheduling
echo  automatic backups, and the Android communication gateway.
echo ==========================================
endlocal