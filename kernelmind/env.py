"""Execution environments.

Every environment exposes the same paths, so task scripts work unchanged in both:

    /app            the codebase the agent works on (APP_DIR)
    /tests          hidden verifier, copied in only after the agent finishes (TESTS_DIR)
    /solution       a fix script being applied during validation (SOLUTION_DIR)
    /logs/verifier  verifier output: reward.txt and results.json (LOGS_DIR)

DockerEnv is the real backend: no network, capped memory/CPU/pids, fresh container per attempt.
LocalEnv runs on the host in a temp directory (network-isolated with unshare when possible).
It exists only for fast task development and CI without Docker; never run agents with it.
"""
from __future__ import annotations

import hashlib
import os
import shutil
import subprocess
import tempfile
import uuid
from dataclasses import dataclass
from pathlib import Path

from .task import Task

PATHS = {"APP_DIR": "/app", "TESTS_DIR": "/tests", "SOLUTION_DIR": "/solution", "LOGS_DIR": "/logs/verifier"}


@dataclass
class ExecResult:
    returncode: int
    output: str
    timed_out: bool = False


class Environment:
    task: Task

    def exec(self, command: str, timeout: int = 120) -> ExecResult: ...
    def copy_in(self, src: Path, dst: str) -> None: ...
    def read_text(self, path: str) -> str | None: ...
    def stop(self) -> None: ...

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        self.stop()


def _run(cmd: list[str], timeout: int, **kw) -> ExecResult:
    try:
        p = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, timeout=timeout,
                           text=True, encoding="utf-8", errors="replace", **kw)
        return ExecResult(p.returncode, p.stdout)
    except subprocess.TimeoutExpired as e:
        out = e.output.decode("utf-8", "replace") if isinstance(e.output, bytes) else (e.output or "")
        return ExecResult(124, out + f"\n[timed out after {timeout}s]", timed_out=True)


# ---------------------------------------------------------------- local

def _can_unshare() -> bool:
    if os.geteuid() != 0 or not shutil.which("unshare"):
        return False
    return subprocess.run(["unshare", "-n", "true"], capture_output=True).returncode == 0


class LocalEnv(Environment):
    def __init__(self, task: Task):
        self.task = task
        self.root = Path(tempfile.mkdtemp(prefix=f"km-{task.id}-"))
        self.dirs = {k: self.root / v.lstrip("/") for k, v in PATHS.items()}
        for d in self.dirs.values():
            d.mkdir(parents=True, exist_ok=True)
        shutil.copytree(task.root / "environment" / "app", self.dirs["APP_DIR"], dirs_exist_ok=True)
        self.prefix = ["unshare", "-n", "--"] if _can_unshare() else []

    def _host(self, path: str) -> Path:
        for key, mount in PATHS.items():
            if path == mount or path.startswith(mount + "/"):
                return self.dirs[key] / path[len(mount):].lstrip("/")
        raise ValueError(f"LocalEnv only maps {sorted(PATHS.values())}, not {path}")

    def exec(self, command: str, timeout: int = 120) -> ExecResult:
        env = {**os.environ, **{k: str(v) for k, v in self.dirs.items()}, "HOME": str(self.root)}
        return _run([*self.prefix, "bash", "-c", command], timeout, cwd=self.dirs["APP_DIR"], env=env)

    def copy_in(self, src: Path, dst: str) -> None:
        shutil.copytree(src, self._host(dst), dirs_exist_ok=True)

    def read_text(self, path: str) -> str | None:
        p = self._host(path)
        return p.read_text(errors="replace") if p.exists() else None

    def stop(self) -> None:
        shutil.rmtree(self.root, ignore_errors=True)


# ---------------------------------------------------------------- docker

def _context_hash(path: Path) -> str:
    h = hashlib.sha256()
    for p in sorted(path.rglob("*")):
        if p.is_file() and "__pycache__" not in p.parts:
            h.update(str(p.relative_to(path)).encode())
            h.update(p.read_bytes())
    return h.hexdigest()[:12]


def build_image(task: Task) -> str:
    context = task.root / "environment"
    tag = f"kernelmind/{task.id}:{_context_hash(context)}"
    if subprocess.run(["docker", "image", "inspect", tag], capture_output=True).returncode == 0:
        return tag
    cmd = ["docker", "build", "-q", "-t", tag]
    if base := os.environ.get("KM_BASE_IMAGE"):  # offline development only
        cmd += ["--build-arg", f"BASE_IMAGE={base}"]
    r = _run([*cmd, str(context)], timeout=1800)
    if r.returncode:
        raise RuntimeError(f"docker build failed for {task.id}:\n{r.output[-3000:]}")
    return tag


class DockerEnv(Environment):
    def __init__(self, task: Task):
        self.task = task
        self.image = build_image(task)
        self.name = f"km-{task.id}-{uuid.uuid4().hex[:8]}"
        d = task.docker
        cmd = ["docker", "run", "-d", "--name", self.name, "--network", "none",
               "--memory", d["memory"], "--cpus", str(d["cpus"]), "--pids-limit", "2048",
               "--security-opt", "no-new-privileges"]
        for cap in d["cap_add"]:
            cmd += ["--cap-add", cap]
        r = _run([*cmd, self.image, "sleep", "infinity"], timeout=120)
        if r.returncode:
            raise RuntimeError(f"docker run failed: {r.output}")
        self.exec("mkdir -p " + " ".join(PATHS.values()))

    def exec(self, command: str, timeout: int = 120) -> ExecResult:
        envs = [x for k, v in PATHS.items() for x in ("-e", f"{k}={v}")]
        return _run(["docker", "exec", "-w", "/app", *envs, self.name, "bash", "-c", command], timeout)

    def copy_in(self, src: Path, dst: str) -> None:
        self.exec(f"mkdir -p {dst}")
        r = _run(["docker", "cp", f"{src}/.", f"{self.name}:{dst}"], timeout=300)
        if r.returncode:
            raise RuntimeError(f"docker cp failed: {r.output}")

    def read_text(self, path: str) -> str | None:
        r = _run(["docker", "exec", self.name, "cat", path], timeout=60)
        return r.output if r.returncode == 0 else None

    def stop(self) -> None:
        subprocess.run(["docker", "rm", "-f", self.name], capture_output=True)


BACKENDS = {"docker": DockerEnv, "local": LocalEnv}


def make_env(task: Task, backend: str) -> Environment:
    return BACKENDS[backend](task)
