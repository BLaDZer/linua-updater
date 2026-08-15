#!/usr/bin/env bash
# Build a single-file executable using the venv's PyInstaller.
# Builds for the HOST platform: dist/Linua-Updater on Linux, dist/Linua-Updater.exe
# on Windows (Git Bash). PyInstaller cannot cross-compile, so to produce a Windows
# .exe you must run this on Windows (or rely on the GitHub Actions workflow).
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
VENV_DIR="${REPO_ROOT}/.venv"

PY="${VENV_DIR}/bin/python"
PIP="${VENV_DIR}/bin/pip"

if [ ! -x "${PY}" ]; then
    echo "[build] No virtual environment found at ${VENV_DIR}"
    echo "[build] Run scripts/setup.sh first."
    exit 1
fi

echo "[build] Activating virtual environment"
# shellcheck disable=SC1090
source "${VENV_DIR}/bin/activate"

echo "[build] Installing PyInstaller and dependencies"
pip install -e ".[dev]" -q

echo "[build] Building executable via build.spec"
pyinstaller --noconfirm "${REPO_ROOT}/build.spec"

if [ -f "${REPO_ROOT}/dist/Linua-Updater.exe" ]; then
    echo "[build] Done: dist/Linua-Updater.exe"
elif [ -f "${REPO_ROOT}/dist/Linua-Updater" ]; then
    echo "[build] Done: dist/Linua-Updater"
else
    echo "[build] Build finished, but no artifact was found in dist/."
    exit 1
fi