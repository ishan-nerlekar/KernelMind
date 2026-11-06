#!/bin/bash
set -e
cat > /app/program.py << 'EOF'
import os
os.chdir('/app')
inp = open('src/INPUT.DAT').read().strip()
buyer, seller, book = inp[0:4], inp[4:8], inp[8:12]
amount = int(inp[12:])
data = open('data/ACCOUNTS.DAT').read()
recs = [data[i:i+34] for i in range(0, len(data), 34)]
ids = [r[:4] for r in recs]
books = open('data/BOOKS.DAT').read()
brecs = [books[i:i+28] for i in range(0, len(books), 28)]
ok = buyer in ids and seller in ids and any(b[:4] == book for b in brecs)
if ok:
    out = []
    for r in recs:
        bal = int(r[24:34])
        if r[:4] == buyer:
            bal -= amount
        elif r[:4] == seller:
            bal += amount
        out.append(f'{r[:24]}{bal:010d}')
    open('data/ACCOUNTS.DAT', 'w').write(''.join(out))
    bout = []
    for b in brecs:
        if b[:4] == book:
            b = b[:24] + buyer
        bout.append(b)
    open('data/BOOKS.DAT', 'w').write(''.join(bout))
    tx = open('data/TRANSACTIONS.DAT').read()
    open('data/TRANSACTIONS.DAT', 'w').write(tx + f'{book}{amount:010d}{seller}{buyer}')
EOF
