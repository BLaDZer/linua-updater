@echo off
REM Build a single-file executable using the venv's PyInstaller.
REM Builds for the HOST platform: dist\Linua-Updater.exe on Windows.
REM PyInstaller cannot cross-compile, so to produce a Windows .exe you must
REM run this on Windows (or rely on the GitHub Actions workflow).
setlocal

set "SCRIPT_DIR=%~dp0"
set "REPO_ROOT=%SCRIPT_DIR%.."
set "VENV_DIR=%REPO_ROOT%\.venv"

if not exist "%VENV_DIR%\Scripts\python.exe" (
    echo [build] No virtual environment found at %VENV_DIR%
    echo [build] Run scripts\setup.bat first.
    exit /b 1
)

set "PY=%VENV_DIR%\Scripts\python.exe"
set "PIP=%VENV_DIR%\Scripts\pip.exe"

echo [build] Installing PyInstaller and dependencies
"%PIP%" install -e ".[dev]"

echo [build] Building executable via build.spec
call "%VENV_DIR%\Scripts\activate.bat"
pyinstaller --noconfirm "%REPO_ROOT%\build.spec"

if exist "%REPO_ROOT%\dist\Linua-Updater.exe" (
    echo [build] Done: dist\Linua-Updater.exe
) else (
    echo [build] Build finished, but no artifact was found in dist\.
    exit /b 1
)