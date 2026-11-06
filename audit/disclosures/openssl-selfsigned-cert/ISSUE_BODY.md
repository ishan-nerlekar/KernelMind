**What the instruction requires**
> Generate a 2048-bit RSA private key: Save it as `/app/ssl/server.key`. Ensure proper permissions (600) for the key file
> Create a self-signed certificate with the following details: ... Organization Name: "DevOps Team", Common Name: "dev-internal.company.local"
> Create a combined PEM file that includes both the private key and certificate

**What passes today** (scripts below)
- `ca-signed-not-self-signed`: creates a throwaway CA and signs `server.crt` with it. The certificate is not self-signed.
- `key-mode-077`: `chmod 077 server.key`, so group and others can read and write the key and the owner can't.
- `pem-unrelated-key`: `server.pem` holds a freshly generated key and certificate, neither of which is `server.key` or `server.crt`.
- `cn-and-o-outside-subject-fields`: the subject's CN is `wrong.example.com` and O is `Acme`; the required strings appear only in the OU and a SAN.

**Why the tests miss it**
- Self-signed is never checked: nothing compares issuer and subject or verifies the signature.
- `key_permissions <= 0o600` compares the mode as a number. `0o077` (63) is less than `0o600` (384), so it passes.
- The PEM test only checks that the file contains the strings `PRIVATE KEY` and `CERTIFICATE` and that a certificate can be parsed from it.
- CN and O are substring checks on the whole `openssl x509 -text` output.

**Suggested fix** (below): require no group/other bits on the key; check the subject's CN and O fields, issuer equals subject, `openssl verify -CAfile server.crt server.crt`, and that the certificate matches `server.key`; check that the PEM's certificate and key are `server.crt` and `server.key`.
Checked locally (pytest with OpenSSL 3, no Docker): the reference passes; each solution above fails.

**Reproduce** (Harbor oracle agent with the solution swapped in):
```bash
cp -R openssl-selfsigned-cert /tmp/openssl-selfsigned-cert-check
# put one of the solve.sh scripts below in /tmp/openssl-selfsigned-cert-check/solution/solve.sh, then:
harbor trial start -p /tmp/openssl-selfsigned-cert-check -a oracle
```

<details><summary><code>ca-signed-not-self-signed/solve.sh</code> (passes the current tests)</summary>

```bash
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
```
</details>

<details><summary><code>cn-and-o-outside-subject-fields/solve.sh</code> (passes the current tests)</summary>

```bash
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
```
</details>

<details><summary><code>key-mode-077/solve.sh</code> (passes the current tests)</summary>

```bash
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
```
</details>

<details><summary><code>pem-unrelated-key/solve.sh</code> (passes the current tests)</summary>

```bash
#!/bin/bash
mkdir -p /app/ssl && cd /app/ssl
openssl genrsa -out server.key 2048
chmod 600 server.key
openssl req -new -x509 -key server.key -out server.crt -days 365 -subj "/O=DevOps Team/CN=dev-internal.company.local"
openssl req -new -x509 -newkey rsa:1024 -nodes -keyout other.key -out other.crt -days 1 -subj "/CN=x"
cat other.key other.crt > server.pem
rm other.key other.crt
{ openssl x509 -in server.crt -noout -subject; openssl x509 -in server.crt -noout -dates; openssl x509 -in server.crt -noout -fingerprint -sha256; } > verification.txt
cat > /app/check_cert.py <<'EOF'
print('CN: dev-internal.company.local')
print('Expires: 2030-01-01')
print('Certificate verification successful')
EOF
```
</details>

<details><summary>Patch to <code>tests/test_outputs.py</code></summary>

```diff
--- a/openssl-selfsigned-cert/tests/test_outputs.py	2026-11-06 17:32:51.856976580 +0000
+++ b/openssl-selfsigned-cert/tests/test_outputs.py	2026-11-06 17:32:51.882326786 +0000
@@ -19,7 +19,8 @@
 
     # Check key permissions (should be restrictive)
     key_permissions = os.stat(key_file).st_mode & 0o777
-    assert key_permissions <= 0o600, f"Key permissions too open: {key_permissions:o}"
+    # A numeric <= also accepts modes like 077; require no group/other access instead.
+    assert key_permissions & 0o077 == 0, f"Key permissions too open: {key_permissions:o}"
 
     # Verify key is 2048 bits
     process = subprocess.run(
@@ -53,6 +54,24 @@
         "Certificate does not have correct Organization Name"
     )
 
+    # The certificate must be self-signed by server.key, with CN and O in the subject itself.
+    def _out(*args):
+        return subprocess.run(["openssl", *args], capture_output=True, text=True).stdout.strip()
+
+    subject = _out("x509", "-in", cert_file, "-noout", "-subject", "-nameopt", "multiline")
+    assert re.search(r"commonName\s*=\s*dev-internal\.company\.local\s*$", subject, re.M), (
+        "Certificate subject CN is not dev-internal.company.local"
+    )
+    assert re.search(r"organizationName\s*=\s*devops team\s*$", subject, re.M | re.I), (
+        "Certificate subject O is not DevOps Team"
+    )
+    assert _out("x509", "-in", cert_file, "-noout", "-issuer").split("=", 1)[1] == \
+        _out("x509", "-in", cert_file, "-noout", "-subject").split("=", 1)[1], "Certificate is not self-signed"
+    verify = subprocess.run(["openssl", "verify", "-CAfile", cert_file, cert_file], capture_output=True, text=True)
+    assert verify.returncode == 0, f"Certificate is not self-signed: {verify.stdout}{verify.stderr}"
+    assert _out("x509", "-in", cert_file, "-noout", "-modulus") == \
+        _out("rsa", "-in", "/app/ssl/server.key", "-noout", "-modulus"), "Certificate does not match server.key"
+
     # Get certificate validity dates
     dates_process = subprocess.run(
         ["openssl", "x509", "-in", cert_file, "-noout", "-dates"],
@@ -101,6 +120,17 @@
     )
     assert process.returncode == 0, "Failed to extract certificate from PEM file"
 
+    # The combined file must hold server.key and server.crt, not some other key pair.
+    def _out(*args):
+        return subprocess.run(["openssl", *args], capture_output=True, text=True).stdout.strip()
+
+    cert_fp = _out("x509", "-in", "/app/ssl/server.crt", "-noout", "-fingerprint", "-sha256")
+    assert cert_fp and _out("x509", "-in", pem_file, "-noout", "-fingerprint", "-sha256") == cert_fp, (
+        "PEM file does not contain server.crt"
+    )
+    assert _out("rsa", "-in", pem_file, "-noout", "-modulus") == \
+        _out("rsa", "-in", "/app/ssl/server.key", "-noout", "-modulus"), "PEM file does not contain server.key"
+
 
 def test_verification_file():
     """Test that the verification file exists with correct content."""
```
</details>
