#!/bin/bash
cat > /app/headless_terminal.py <<'EOF'
import os, pty, time, threading, fcntl, termios, struct
from base_terminal import BaseTerminal

class HeadlessTerminal(BaseTerminal):
    def __init__(self):
        pid, fd = pty.fork()
        if pid == 0:
            os.environ['TERM'] = 'xterm'
            os.execvp('bash', ['bash', '-i'])
        self.pid, self.fd = pid, fd
        fcntl.ioctl(fd, termios.TIOCSWINSZ, struct.pack('HHHH', 40, 120, 0, 0))
        threading.Thread(target=self._drain, daemon=True).start()
        time.sleep(0.5)

    def _drain(self):
        while True:
            try:
                if not os.read(self.fd, 4096):
                    break
            except OSError:
                break

    def send_keystrokes(self, keystrokes, wait_sec=0.0):
        keep = ''.join(c for c in keystrokes if c in '\n\x1b' or ord(c) >= 32)
        if keep:
            os.write(self.fd, keep.encode())
        if wait_sec > 0:
            time.sleep(wait_sec)
EOF
