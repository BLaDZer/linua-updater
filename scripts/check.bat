@echo off
REM Run the test suite and linters using the venv.
REM   - python -m pytest tests/
REM   - ruff check linua_updater/
setlocal

set "SCRIPT_DIR=%~dp0"
set "REPO_ROOT=%SCRIPT_DIR%.."
set "VENV_DIR=%REPO_ROOT%\.venv"

if not exist "%VENV_DIR%\Scripts\python.exe" (
    echo [check] No virtual environment found at %VENV_DIR%
    echo [check] Run scripts\setup.bat first.
    exit /b 1
)

set "PY=%VENV_DIR%\Scripts\python.exe"

echo [check] Running pytest
"%PY%" -m pytest "%REPO_ROOT%\tests"

echo [check] Running ruff check
"%PY%" -m ruff check "%REPO_ROOT%\linua_updater"

echo [check] All checks passed.