**What the instruction requires**
> Has support for modifier keys like `"\x03"` for control C, etc.

**What passes today**
`drops-ctrl-c/solve.sh` (below) is a working pty-backed terminal whose `send_keystrokes` silently drops every control character except `\n` and `\x1b`, so Ctrl-C never reaches the shell. It passes `test_cancel_command`.

**Why the tests miss it**
`test_cancel_command` runs `sleep 10 && echo 'Hello, world!' > /app/cancel.txt`, sends `\x03`, waits 0.5 s and asserts that `/app/cancel.txt` doesn't exist. At that point the sleep has about 9 seconds left, so the file can't exist whether or not Ctrl-C worked.

**Suggested fix** (below): after the existing assertion, type a new command and check it runs within a second. If Ctrl-C didn't interrupt the sleep, the shell is still busy and the new command hasn't run.
Checked locally (pytest with tmux, no Docker): the reference passes 5 of 5 runs; the solution above fails.
Confirmed under Harbor 0.25 (`harbor trial start -a oracle`): on the current tests the reference and every solution above score reward 1.0; with the patch below, the reference scores 1.0 and every solution 0.0.

**Reproduce** (Harbor oracle agent with the solution swapped in):
```bash
cp -R headless-terminal /tmp/headless-terminal-check
# put one of the solve.sh scripts below in /tmp/headless-terminal-check/solution/solve.sh, then:
harbor trial start -p /tmp/headless-terminal-check -a oracle
```

<details><summary><code>drops-ctrl-c/solve.sh</code> (passes the current tests)</summary>

```bash
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
```
</details>

<details><summary>Patch to <code>tests/test_outputs.py</code></summary>

```diff
--- a/headless-terminal/tests/test_outputs.py	2026-11-06 17:33:38.184193781 +0000
+++ b/headless-terminal/tests/test_outputs.py	2026-11-06 17:33:38.206646398 +0000
@@ -67,6 +67,12 @@
 
     assert not path.exists()
 
+    # cancel.txt is absent at this point whether or not Ctrl-C worked (the sleep has 9 s left), so also
+    # check that the shell is free again: a new command must run now, not after the sleep finishes.
+    terminal.send_keystrokes("echo after > /app/after_cancel.txt")
+    terminal.send_keystrokes("\n", wait_sec=1)
+    assert Path("/app/after_cancel.txt").exists(), "the shell is still busy: Ctrl-C did not interrupt the command"
+
 
 def test_startup_files():
     """
```
</details>
