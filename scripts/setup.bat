@echo off
REM Initialize the virtual environment and install project requirements.
REM Creates .venv (idempotent), upgrades pip, installs the package + dev extras.
setlocal

set "SCRIPT_DIR=%~dp0"
set "REPO_ROOT=%SCRIPT_DIR%.."
set "VENV_DIR=%REPO_ROOT%\.venv"

if exist "%VENV_DIR%\Scripts\python.exe" (
    echo [setup] Virtual environment found at %VENV_DIR%
) else (
    echo [setup] Creating virtual environment at %VENV_DIR%
    python -m venv "%VENV_DIR%"
)

set "PIP=%VENV_DIR%\Scripts\pip.exe"

echo [setup] Upgrading pip
"%PIP%" install --upgrade pip

echo [setup] Installing package and dependencies
"%PIP%" install -e ".[dev]"

echo [setup] Done. Activate with: call "%VENV_DIR%\Scripts\activate"