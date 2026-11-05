#!/bin/bash
# Reproduces the incident in this container: builds gobgpd from /app, starts it with edge1's
# configuration, and connects it to stand-ins for dc1 (announces 2,100 host routes), rtr7 (legacy
# platform) and rtr11 (newer platform). Usage: repro.sh [seconds to run, default 25]
# Expected when healthy: all sessions stay up and rtr7 and rtr11 each hold all 2,100 host routes.
set -u
cd "$(dirname "$0")"
W=/tmp/repro
# Stop processes left over from an earlier run that was interrupted (they would still hold port 179).
[ -f "$W/pids" ] && kill $(cat "$W/pids") 2>/dev/null && sleep 1
rm -rf "$W"; mkdir -p "$W"
trap 'kill $(jobs -p) 2>/dev/null; wait 2>/dev/null' EXIT
(cd /app && go build -o "$W/gobgpd" ./cmd/gobgpd) || exit 1
python3 speaker.py --name dc1   --listen 127.0.0.30 --asn 4200000300 --id 10.30.0.1  --extended --announce 2100 > "$W/dc1.log" 2>&1 &
echo $! >> "$W/pids"
sleep 1
"$W/gobgpd" -f edge1.toml --log-level=info > "$W/gobgpd.log" 2>&1 &
echo $! >> "$W/pids"
# The aggregation routers come up after edge1 has the host routes, as rtr7 did after its reboot.
sleep 5
python3 speaker.py --name rtr7  --listen 127.0.0.7  --asn 64707      --id 10.20.0.7  --extended-nexthop > "$W/rtr7.log" 2>&1 &
echo $! >> "$W/pids"
python3 speaker.py --name rtr11 --listen 127.0.0.11 --asn 4200000211 --id 10.20.0.11 --extended --extended-nexthop > "$W/rtr11.log" 2>&1 &
echo $! >> "$W/pids"
sleep "${1:-25}"
for r in dc1 rtr7 rtr11; do echo "===== $r"; cat "$W/$r.log"; done
echo "(full logs, including edge1's gobgpd.log, are kept in $W)"
