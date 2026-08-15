#!/usr/bin/env bash
# Initialize the virtual environment and install project requirements.
# Creates .venv (idempotent), upgrades pip, installs the package + dev extras.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"

VENV_DIR="${REPO_ROOT}/.venv"

if [ -x "${VENV_DIR}/bin/python" ]; then
    echo "[setup] Virtual environment found at ${VENV_DIR}"
else
    echo "[setup] Creating virtual environment at ${VENV_DIR}"
    python3 -m venv "${VENV_DIR}"
fi

PY="${VENV_DIR}/bin/python"
PIP="${VENV_DIR}/bin/pip"

echo "[setup] Upgrading pip"
"${PIP}" install --upgrade pip

echo "[setup] Installing package and dependencies"
"${PIP}" install -e ".[dev]" -q

echo "[setup] Done. Activate with: source ${VENV_DIR}/bin/activate"