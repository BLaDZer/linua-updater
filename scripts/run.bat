@echo off
REM Run the GUI using the venv.
setlocal

set "SCRIPT_DIR=%~dp0"
set "REPO_ROOT=%SCRIPT_DIR%.."
set "VENV_DIR=%REPO_ROOT%\.venv"
set "PY=%VENV_DIR%\Scripts\python.exe"

if not exist "%PY%" (
    echo [run] No virtual environment found at %VENV_DIR%
    echo [run] Run scripts\setup.bat first.
    exit /b 1
)

cd /d "%REPO_ROOT%"
"%PY%" -m linua_updater %*