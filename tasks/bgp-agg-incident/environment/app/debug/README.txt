repro.sh     builds gobgpd from /app and runs the reproduction (default 25 seconds; pass a number to
             change it). Each router stand-in's log is printed at the end; all logs stay in /tmp/repro.
edge1.toml   edge1's configuration for the reproduction (same settings as production for these peers)
speaker.py   the router stand-ins: a minimal IPv4-unicast BGP speaker. Flags match each router's real capabilities: rtr7's
             platform supports RFC 8950 extended next hops but not RFC 8654 extended messages.
             Every stand-in enforces the message size limits.
