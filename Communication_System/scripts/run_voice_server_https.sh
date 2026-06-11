#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"
CONTROL_PC_DIR="${PROJECT_DIR}/control_pc"
CERT_FILE="${PROJECT_DIR}/certs/voice-server.crt"
KEY_FILE="${PROJECT_DIR}/certs/voice-server.key"

if [ ! -f "${CERT_FILE}" ] || [ ! -f "${KEY_FILE}" ]; then
  echo "HTTPS certificate not found."
  echo "Run first: ${PROJECT_DIR}/scripts/generate_https_cert.sh <CONTROL_PC_IP>"
  exit 1
fi

cd "${CONTROL_PC_DIR}"
VOICE_SSL_CERTFILE="${CERT_FILE}" \
VOICE_SSL_KEYFILE="${KEY_FILE}" \
PYTHONPATH=. \
.venv/bin/python -m voice_server.main
