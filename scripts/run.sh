#!/usr/bin/env bash
# Run the GUI using the venv.
# Falls back to QT_QPA_PLATFORM=offscreen when no display is available (CI/headless).
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
VENV_DIR="${REPO_ROOT}/.venv"
PY="${VENV_DIR}/bin/python"

if [ ! -x "${PY}" ]; then
    echo "[run] No virtual environment found at ${VENV_DIR}"
    echo "[run] Run scripts/setup.sh first."
    exit 1
fi

# shellcheck disable=SC1090
source "${VENV_DIR}/bin/activate"

cd "${REPO_ROOT}"

if [ -z "${DISPLAY:-}" ] && [ -z "${WAYLAND_DISPLAY:-}" ]; then
    echo "[run] No display detected; using offscreen platform."
    export QT_QPA_PLATFORM=offscreen
fi

exec python -m linua_updater "$@"