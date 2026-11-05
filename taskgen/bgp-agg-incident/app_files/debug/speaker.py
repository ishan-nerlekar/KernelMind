#!/usr/bin/env python3
"""Minimal BGP speaker standing in for a third-party router (IPv4 unicast only).

It listens for edge1's connection, negotiates like the router it stands in for, enforces the
message size limit RFC 4271/8654 require, and logs what it receives. With --announce N it also
originates N /32 host routes once the session is up (the data-center source).
"""
import argparse, socket, struct, sys, threading, time

MARKER = b"\xff" * 16
OPEN, UPDATE, NOTIFICATION, KEEPALIVE = 1, 2, 3, 4


def log(name, msg):
    print(f"{time.strftime('%H:%M:%S')} {name}: {msg}", flush=True)


def recv_exact(s, n):
    b = b""
    while len(b) < n:
        c = s.recv(n - len(b))
        if not c:
            raise EOFError
        b += c
    return b


def msg(t, body=b""):
    return MARKER + struct.pack("!HB", 19 + len(body), t) + body


def open_msg(asn, rid, extended, extended_nexthop):
    caps = bytes([1, 4, 0, 1, 0, 1]) + bytes([2, 0]) + bytes([65, 4]) + struct.pack("!I", asn)
    if extended_nexthop:
        caps += bytes([5, 6, 0, 1, 0, 1, 0, 2])  # IPv4 unicast over IPv6 next hops (RFC 8950)
    if extended:
        caps += bytes([6, 0])
    params = bytes([2, len(caps)]) + caps
    my_as = asn if asn < 65536 else 23456
    return msg(OPEN, struct.pack("!BHH4sB", 4, my_as, 90, socket.inet_aton(rid), len(params)) + params)


def peer_caps(body):
    caps, plen, i = [], body[9], 10
    while i < 10 + plen:
        ptype, l = body[i], body[i + 1]
        if ptype == 2:
            j = i + 2
            while j < i + 2 + l:
                caps.append(body[j])
                j += 2 + body[j + 1]
        i += 2 + l
    return caps


def prefixes(b):
    out, i = [], 0
    while i < len(b):
        plen = b[i]
        n = (plen + 7) // 8
        out.append(socket.inet_ntoa(b[i + 1:i + 1 + n].ljust(4, b"\0")) + f"/{plen}")
        i += 1 + n
    return out


def announcements(asn, rid, count):
    attrs = (bytes([0x40, 1, 1, 0]) + bytes([0x40, 2, 6, 2, 1]) + struct.pack("!I", asn)
             + bytes([0x40, 3, 4]) + socket.inet_aton(rid))
    for start in range(0, count, 800):
        nlri = b"".join(bytes([32]) + socket.inet_aton(f"10.{40 + i // 65536}.{(i // 256) % 256}.{i % 256}")
                        for i in range(start, min(count, start + 800)))
        yield msg(UPDATE, struct.pack("!H", 0) + struct.pack("!H", len(attrs)) + attrs + nlri)


def session(conn, a):
    lock = threading.Lock()
    alive = True

    def send(m):
        with lock:
            conn.sendall(m)

    def keepalives():
        while alive:
            time.sleep(10)
            try:
                send(msg(KEEPALIVE))
            except OSError:
                return

    rib = set()
    send(open_msg(a.asn, a.id, a.extended, a.extended_nexthop))
    while True:
        hdr = recv_exact(conn, 19)
        length, t = struct.unpack("!HB", hdr[16:19])
        body = recv_exact(conn, length - 19)
        if t == OPEN:
            caps = peer_caps(body)
            ext = a.extended and 6 in caps
            limit = 65535 if ext else 4096
            log(a.name, f"OPEN from edge1, capabilities {caps}")
            send(msg(KEEPALIVE))
            threading.Thread(target=keepalives, daemon=True).start()
            log(a.name, "session established")
            for m in announcements(a.asn, a.id, a.announce):
                send(m)
            if a.announce:
                log(a.name, f"announced {a.announce} routes")
        elif length > limit:
            log(a.name, f"NOTIFICATION sent: message header error / bad message length ({length} bytes)")
            send(msg(NOTIFICATION, bytes([1, 2]) + struct.pack("!H", length)))
            alive = False
            return
        elif t == UPDATE:
            wl = struct.unpack("!H", body[:2])[0]
            al = struct.unpack("!H", body[2 + wl:4 + wl])[0]
            for p in prefixes(body[2:2 + wl]):
                rib.discard(p)
            rib.update(prefixes(body[4 + wl + al:]))
            log(a.name, f"UPDATE {length} bytes, {sum(p.startswith('10.4') for p in rib)} host routes held")
        elif t == NOTIFICATION:
            log(a.name, f"NOTIFICATION received {body[0]}/{body[1]}")
            alive = False
            return


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--name", required=True)
    p.add_argument("--listen", required=True, help="address to listen on, port 179")
    p.add_argument("--asn", type=int, required=True)
    p.add_argument("--id", required=True)
    p.add_argument("--extended", action="store_true", help="supports RFC 8654 extended messages")
    p.add_argument("--extended-nexthop", action="store_true", help="supports RFC 8950 extended next hops")
    p.add_argument("--announce", type=int, default=0)
    a = p.parse_args()
    s = socket.socket()
    s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    s.bind((a.listen, 179))
    s.listen(1)
    while True:
        conn, _ = s.accept()
        try:
            session(conn, a)
        except (EOFError, OSError):
            log(a.name, "connection closed")
        conn.close()


if __name__ == "__main__":
    sys.exit(main())
