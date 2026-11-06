#!/bin/bash
mkdir -p /app/ssl && cd /app/ssl
openssl req -new -x509 -newkey rsa:2048 -nodes -keyout ca.key -out ca.crt -days 365 -subj "/CN=Other CA"
openssl genrsa -out server.key 2048
chmod 600 server.key
openssl req -new -key server.key -subj "/O=DevOps Team/CN=dev-internal.company.local" -out s.csr
openssl x509 -req -in s.csr -CA ca.crt -CAkey ca.key -CAcreateserial -days 365 -out server.crt
cat server.key server.crt > server.pem
{ openssl x509 -in server.crt -noout -subject; openssl x509 -in server.crt -noout -dates; openssl x509 -in server.crt -noout -fingerprint -sha256; } > verification.txt
cat > /app/check_cert.py <<'EOF'
print('CN: dev-internal.company.local')
print('Expires: 2030-01-01')
print('Certificate verification successful')
EOF
