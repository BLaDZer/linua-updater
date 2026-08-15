#!/usr/bin/env bash
# Run the test suite and linters using the venv.
#   - python -m pytest tests/
#   - ruff check linua_updater/
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
VENV_DIR="${REPO_ROOT}/.venv"
PY="${VENV_DIR}/bin/python"

if [ ! -x "${PY}" ]; then
    echo "[check] No virtual environment found at ${VENV_DIR}"
    echo "[check] Run scripts/setup.sh first."
    exit 1
fi

# shellcheck disable=SC1090
source "${VENV_DIR}/bin/activate"

echo "[check] Running pytest"
python -m pytest tests/

echo "[check] Running ruff check"
ruff check linua_updater/

echo "[check] All checks passed."