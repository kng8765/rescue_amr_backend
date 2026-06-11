#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"
CONTROL_PC_DIR="${PROJECT_DIR}/control_pc"

cd "${PROJECT_DIR}"
PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 \
PYTHONPATH="${CONTROL_PC_DIR}" \
"${CONTROL_PC_DIR}/.venv/bin/python" -m pytest "${CONTROL_PC_DIR}/tests" "$@"
