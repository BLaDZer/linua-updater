@echo off
REM Remove all caches and build artifacts from the repository.
REM Deletes dist\, build\, .venv\, *.egg-info, and every __pycache__ directory,
REM *.pyc bytecode, .pytest_cache\ and .ruff_cache\ tree.
setlocal

set "SCRIPT_DIR=%~dp0"
set "REPO_ROOT=%SCRIPT_DIR%.."

echo [clean] Removing build artifacts and caches in %REPO_ROOT%

for %%D in (
    "%REPO_ROOT%\dist"
    "%REPO_ROOT%\build"
    "%REPO_ROOT%\.venv"
    "%REPO_ROOT%\.pytest_cache"
    "%REPO_ROOT%\.ruff_cache"
    "%REPO_ROOT%\linua_updater.egg-info"
) do (
    if exist "%%~D" (
        rd /s /q "%%~D"
    )
)

for /d %%D in ("%REPO_ROOT%\*.egg-info") do rd /s /q "%%D"
for /d /r "%REPO_ROOT%" %%D in (__pycache__) do rd /s /q "%%D"
for /r "%REPO_ROOT%" %%F in (*.pyc) do del /q "%%F"

echo [clean] Done. Run scripts\setup.bat to recreate the virtual environment.
