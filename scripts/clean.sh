#!/usr/bin/env bash
# Remove all caches and build artifacts from the repository.
# Deletes dist/, build/, .venv/, *.egg-info, and every __pycache__/ directory,
# *.pyc bytecode, .pytest_cache/ and .ruff_cache/ tree.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"

echo "[clean] Removing build artifacts and caches in ${REPO_ROOT}"

rm -rf \
    "${REPO_ROOT}/dist" \
    "${REPO_ROOT}/build" \
    "${REPO_ROOT}/.venv" \
    "${REPO_ROOT}/.pytest_cache" \
    "${REPO_ROOT}/.ruff_cache" \
    "${REPO_ROOT}"/linua_updater.egg-info \
    "${REPO_ROOT}"/*.egg-info

find "${REPO_ROOT}" -type d -name "__pycache__" -prune -exec rm -rf {} +
find "${REPO_ROOT}" -type f -name "*.pyc" -delete

echo "[clean] Done. Run scripts/setup.sh to recreate the virtual environment."
