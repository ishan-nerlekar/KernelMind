"""Run an agent on tasks: fresh environment per attempt, agent works, hidden tests decide."""
from __future__ import annotations

import json
import re
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from pathlib import Path

from .agents import get_agent
from .env import make_env
from .task import REPO, Task
from .verify import run_tests

RESULTS = REPO / "results"


def _attempt(agent_name: str, model: str | None, task: Task, n: int, backend: str, run_dir: Path) -> dict:
    out = run_dir / task.id / f"attempt-{n}"
    out.mkdir(parents=True, exist_ok=True)
    record = {"task": task.id, "tier": task.tier, "root_cause": task.meta["root_cause"],
              "origin": task.meta["origin"], "attempt": n, "agent": agent_name, "model": model,
              "backend": backend, "started": datetime.now(timezone.utc).isoformat()}
    start = time.time()
    try:
        agent = get_agent(agent_name, model)
        with make_env(task, backend) as env:
            record.update(agent.run(env, task, out))
            record["agent_seconds"] = round(time.time() - start, 1)
            diff = env.exec('git -C "$APP_DIR" add -A >/dev/null 2>&1 && git -C "$APP_DIR" diff --cached')
            (out / "agent.diff").write_text(diff.output if diff.returncode == 0 else "")
            record["verdict"] = run_tests(env).to_dict()
        record["passed"] = record["verdict"]["passed"]
    except Exception as e:  # infrastructure failure: recorded, excluded from scores
        record.update(passed=None, error=f"{type(e).__name__}: {e}")
    record["seconds"] = round(time.time() - start, 1)
    (out / "result.json").write_text(json.dumps(record, indent=2))
    return record


def run(tasks: list[Task], agent: str, model: str | None, attempts: int, backend: str, jobs: int,
        run_id: str | None = None) -> Path:
    if agent != "oracle" and backend != "docker":
        raise SystemExit("agents other than oracle must run with --backend docker (sandboxed)")
    slug = re.sub(r"[^A-Za-z0-9.-]+", "-", model or agent)
    run_id = run_id or f"{datetime.now():%Y%m%d-%H%M%S}-{agent}-{slug}"
    run_dir = RESULTS / run_id
    run_dir.mkdir(parents=True, exist_ok=True)
    (run_dir / "run.json").write_text(json.dumps(
        {"agent": agent, "model": model, "attempts": attempts, "backend": backend,
         "tasks": [t.id for t in tasks]}, indent=2))
    work = [(t, n) for t in tasks for n in range(1, attempts + 1)
            if not (run_dir / t.id / f"attempt-{n}" / "result.json").exists()]  # resumable
    with ThreadPoolExecutor(max_workers=jobs) as pool:
        futures = [pool.submit(_attempt, agent, model, t, n, backend, run_dir) for t, n in work]
        for f in as_completed(futures):
            r = f.result()
            mark = {True: "PASS", False: "fail", None: "ERROR"}[r["passed"]]
            print(f"{mark:5} {r['task']} #{r['attempt']} ({r['seconds']}s)", flush=True)
    return run_dir
