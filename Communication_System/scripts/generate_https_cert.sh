#!/usr/bin/env bash
set -euo pipefail

if [ "$#" -lt 1 ]; then
  echo "Usage: $0 <CONTROL_PC_IP>"
  echo "Example: $0 192.168.0.10"
  exit 1
fi

CONTROL_PC_IP="$1"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"
CERT_DIR="${PROJECT_DIR}/certs"
CA_CNF="${CERT_DIR}/voice-local-ca.cnf"
SERVER_CNF="${CERT_DIR}/voice-server-${CONTROL_PC_IP}.cnf"

mkdir -p "${CERT_DIR}"

cat > "${CA_CNF}" <<EOF
[req]
default_bits = 2048
prompt = no
default_md = sha256
distinguished_name = dn
x509_extensions = v3_ca

[dn]
CN = Rescue Voice Local Test CA
O = Rescue Voice Test

[v3_ca]
basicConstraints = critical, CA:true
keyUsage = critical, keyCertSign, cRLSign
subjectKeyIdentifier = hash
authorityKeyIdentifier = keyid:always,issuer
EOF

cat > "${SERVER_CNF}" <<EOF
[req]
default_bits = 2048
prompt = no
default_md = sha256
distinguished_name = dn
req_extensions = v3_req

[dn]
CN = rescue-voice.local

[v3_req]
basicConstraints = CA:false
keyUsage = critical, digitalSignature, keyEncipherment
extendedKeyUsage = serverAuth
subjectAltName = @alt_names

[alt_names]
IP.1 = ${CONTROL_PC_IP}
IP.2 = 127.0.0.1
DNS.1 = localhost
EOF

openssl req \
  -x509 \
  -nodes \
  -days 3650 \
  -newkey rsa:2048 \
  -keyout "${CERT_DIR}/voice-local-ca.key" \
  -out "${CERT_DIR}/voice-local-ca.crt" \
  -config "${CA_CNF}"

openssl req \
  -nodes \
  -newkey rsa:2048 \
  -keyout "${CERT_DIR}/voice-server.key" \
  -out "${CERT_DIR}/voice-server.csr" \
  -config "${SERVER_CNF}"

openssl x509 \
  -req \
  -days 365 \
  -in "${CERT_DIR}/voice-server.csr" \
  -CA "${CERT_DIR}/voice-local-ca.crt" \
  -CAkey "${CERT_DIR}/voice-local-ca.key" \
  -CAcreateserial \
  -out "${CERT_DIR}/voice-server.crt" \
  -extensions v3_req \
  -extfile "${SERVER_CNF}"

echo "Generated:"
echo "  ${CERT_DIR}/voice-local-ca.crt"
echo "  ${CERT_DIR}/voice-local-ca.key"
echo "  ${CERT_DIR}/voice-server.crt"
echo "  ${CERT_DIR}/voice-server.key"
echo
echo "Install this CA certificate on Android:"
echo "  ${CERT_DIR}/voice-local-ca.crt"
echo
echo "Do not install the server certificate on Android:"
echo "  ${CERT_DIR}/voice-server.crt"
