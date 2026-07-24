@echo off
setlocal
title VolunteerHub - Rajagiri Campus Volunteer System
color 0A

:: Always switch to the directory where this batch file is located
cd /d "%~dp0"

echo =========================================================================
echo               VolunteerHub — Rajagiri Campus Volunteer System
echo =========================================================================
echo.

:: Use virtual environment python executable if present, fallback to py launcher
set "PYTHON_EXE=py"
if exist "%~dp0venv\Scripts\python.exe" (
    set "PYTHON_EXE=%~dp0venv\Scripts\python.exe"
)

echo [1/2] Opening web browser at http://127.0.0.1:8000/accounts/login/ ...
start http://127.0.0.1:8000/accounts/login/

echo [2/2] Starting Django Development Server...
echo.
echo Server URL: http://127.0.0.1:8000/accounts/login/
echo Press Ctrl+C in this window to stop the server at any time.
echo =========================================================================
echo.

"%PYTHON_EXE%" manage.py runserver 127.0.0.1:8000

pause
