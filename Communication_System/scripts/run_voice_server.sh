#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"
CONTROL_PC_DIR="${PROJECT_DIR}/control_pc"

cd "${CONTROL_PC_DIR}"
PYTHONPATH=. .venv/bin/python -m voice_server.main
