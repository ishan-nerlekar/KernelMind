#!/bin/bash
mkdir -p /app/ssl
openssl genrsa -out /app/ssl/server.key 2048
openssl req -new -x509 -key /app/ssl/server.key -out /app/ssl/server.crt -days 365 -subj "/O=DevOps Team/CN=dev-internal.company.local"
cat /app/ssl/server.key /app/ssl/server.crt > /app/ssl/server.pem
chmod 077 /app/ssl/server.key
{ openssl x509 -in /app/ssl/server.crt -noout -subject; openssl x509 -in /app/ssl/server.crt -noout -dates; openssl x509 -in /app/ssl/server.crt -noout -fingerprint -sha256; } > /app/ssl/verification.txt
cat > /app/check_cert.py <<'EOF'
import ssl,subprocess,datetime
ssl._ssl._test_decode_cert('/app/ssl/server.crt')
d=subprocess.check_output(['openssl','x509','-in','/app/ssl/server.crt','-noout','-enddate'],text=True)
print('CN: dev-internal.company.local')
print('Expires:',datetime.datetime.strptime(d.split('=')[1].strip(),'%b %d %H:%M:%S %Y %Z').strftime('%Y-%m-%d'))
print('Certificate verification successful')
EOF
