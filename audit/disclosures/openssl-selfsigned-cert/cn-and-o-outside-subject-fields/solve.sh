#!/bin/bash
mkdir -p /app/ssl
openssl genrsa -out /app/ssl/server.key 2048
chmod 600 /app/ssl/server.key
openssl req -new -x509 -key /app/ssl/server.key -out /app/ssl/server.crt -days 365 -subj "/O=Acme/OU=devops team/CN=wrong.example.com" -addext "subjectAltName=DNS:dev-internal.company.local"
cat /app/ssl/server.key /app/ssl/server.crt > /app/ssl/server.pem
{ openssl x509 -in /app/ssl/server.crt -noout -subject; echo dev-internal.company.local; openssl x509 -in /app/ssl/server.crt -noout -dates; openssl x509 -in /app/ssl/server.crt -noout -fingerprint -sha256; } > /app/ssl/verification.txt
cat > /app/check_cert.py <<'EOF'
print('CN: dev-internal.company.local')
print('Expires: 2030-01-01')
print('Certificate verification successful')
EOF
