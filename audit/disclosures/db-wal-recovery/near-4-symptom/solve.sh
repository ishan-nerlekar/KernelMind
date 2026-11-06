#!/bin/bash
set -e
cd /app
mkdir -p /tmp/scratch
cp /app/main.db /tmp/scratch/main.db
# Decrypt only the scratch copy of the WAL
python3 - <<'EOF'
with open('/app/main.db-wal', 'rb') as f:
    data = f.read()
with open('/tmp/scratch/main.db-wal', 'wb') as f:
    f.write(bytes(b ^ 0x42 for b in data))
EOF
python3 - <<'EOF'
import sqlite3, json
conn = sqlite3.connect('/tmp/scratch/main.db')
rows = conn.execute('SELECT id, name, value FROM items ORDER BY id').fetchall()
conn.close()
data = [{"id": r[0], "name": r[1], "value": r[2]} for r in rows]
with open('/app/recovered.json', 'w') as f:
    json.dump(data, f, indent=2)
EOF
