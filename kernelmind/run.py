"""Run an agent on tasks: fresh environment per attempt, agent works, hidden tests decide."""
from __future__ import annotations

import json
import re
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from pathlib import Path

from .agents import BudgetExceeded, get_agent
from .env import make_env
from .task import REPO, Task
from .verify import run_tests

RESULTS = REPO / "results"


STOP = threading.Event()  # set when the run's spending cap is hit


def _attempt(agent_name: str, model: str | None, task: Task, n: int, backend: str, run_dir: Path,
             cost_per_attempt: float) -> dict | None:
    if STOP.is_set():
        return None  # skipped; no result.json, so a later resume picks it up
    out = run_dir / task.id / f"attempt-{n}"
    out.mkdir(parents=True, exist_ok=True)
    record = {"task": task.id, "tier": task.tier, "root_cause": task.meta["root_cause"],
              "origin": task.meta["origin"], "attempt": n, "agent": agent_name, "model": model,
              "backend": backend, "started": datetime.now(timezone.utc).isoformat()}
    start = time.time()
    try:
        agent = get_agent(agent_name, model, cost_per_attempt)
        with make_env(task, backend) as env:
            record.update(agent.run(env, task, out))
            record["agent_seconds"] = round(time.time() - start, 1)
            diff = env.exec('git -C "$APP_DIR" add -A >/dev/null 2>&1 && git -C "$APP_DIR" diff --cached')
            (out / "agent.diff").write_text(diff.output if diff.returncode == 0 else "")
            record["verdict"] = run_tests(env).to_dict()
        record["passed"] = record["verdict"]["passed"]
    except BudgetExceeded as e:  # spending cap: stop the run; this attempt is redone on resume
        STOP.set()
        print(f"SPENDING CAP REACHED: {e}. Stopping; rerun the same command with a higher --max-cost to resume.")
        return None
    except Exception as e:  # infrastructure failure: recorded, excluded from scores
        record.update(passed=None, error=f"{type(e).__name__}: {e}")
    record["seconds"] = round(time.time() - start, 1)
    (out / "result.json").write_text(json.dumps(record, indent=2))
    return record


def _done(run_dir: Path, task: Task, n: int) -> bool:
    """Resume support: an attempt is done once it has a scored result. Infrastructure errors are retried."""
    f = run_dir / task.id / f"attempt-{n}" / "result.json"
    return f.exists() and json.loads(f.read_text()).get("passed") is not None


def run(tasks: list[Task], agent: str, model: str | None, attempts: int, backend: str, jobs: int,
        run_id: str | None = None, max_cost: float = 0.0, cost_per_attempt: float = 5.0) -> Path:
    if agent != "oracle" and backend != "docker":
        raise SystemExit("agents other than oracle must run with --backend docker (sandboxed)")
    if agent == "mini":
        print(f"preflight: checking {model} ...", flush=True)
        get_agent(agent, model).preflight()
    if agent == "mini":  # mini-swe-agent enforces this total across every attempt in this process
        from minisweagent.models import GLOBAL_MODEL_STATS
        GLOBAL_MODEL_STATS.cost_limit = max_cost
    STOP.clear()
    slug = re.sub(r"[^A-Za-z0-9.-]+", "-", model or agent)
    run_id = run_id or f"{datetime.now():%Y%m%d-%H%M%S}-{agent}-{slug}"
    run_dir = RESULTS / run_id
    run_dir.mkdir(parents=True, exist_ok=True)
    (run_dir / "run.json").write_text(json.dumps(
        {"agent": agent, "model": model, "attempts": attempts, "backend": backend,
         "max_cost_usd": max_cost, "cost_per_attempt_usd": cost_per_attempt,
         "tasks": [t.id for t in tasks]}, indent=2))
    work = [(t, n) for t in tasks for n in range(1, attempts + 1) if not _done(run_dir, t, n)]
    with ThreadPoolExecutor(max_workers=jobs) as pool:
        futures = [pool.submit(_attempt, agent, model, t, n, backend, run_dir, cost_per_attempt)
                   for t, n in work]
        for f in as_completed(futures):
            r = f.result()
            if r is None:
                continue
            mark = {True: "PASS", False: "fail", None: "ERROR"}[r["passed"]]
            print(f"{mark:5} {r['task']} #{r['attempt']} ({r['seconds']}s)", flush=True)
    return run_dir
