@echo off
setlocal

echo ==========================================
echo  EdFlow - Production server (Daphne/ASGI)
echo ==========================================
echo.

rem Requires setup_windows.bat to have been run first.
if not exist ".venv\Scripts\daphne.exe" (
    echo [ERROR] Virtual environment not installed yet.
    echo Run setup_windows.bat first.
    exit /b 1
)

call ".venv\Scripts\activate.bat"
if errorlevel 1 (
    echo [ERROR] Failed to activate virtual environment.
    exit /b 1
)

if not exist ".env" (
    echo [ERROR] .env is missing. Run setup_windows.bat first.
    exit /b 1
)

set DJANGO_SETTINGS_MODULE=project.settings.prod

rem Default bind: all school LAN interfaces on port 8000.
rem Override with:  start_server.bat 0.0.0.0 8000
set BIND_HOST=%1
if "%BIND_HOST%"=="" set BIND_HOST=0.0.0.0
set BIND_PORT=%2
if "%BIND_PORT%"=="" set BIND_PORT=8000

rem Serves HTTP + WebSockets (attendance, notifications, dashboard) in one
rem process. Safe to run behind a LAN hostname or a reverse proxy.
echo [..] Starting EdFlow on %BIND_HOST%:%BIND_PORT% (Ctrl+C to stop) ...
echo.
daphne -b %BIND_HOST% -p %BIND_PORT% project.asgi:application
if errorlevel 1 (
    echo [ERROR] Server stopped unexpectedly. Check logs\edflow.log.
    exit /b 1
)
endlocal