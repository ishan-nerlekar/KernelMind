"""kernelmind command line.

  kernelmind list
  kernelmind validate [TASK ...] [--backend docker|local]
  kernelmind run --agent mini --model claude-opus-5-5 --max-cost 20 [--tasks ...] [--attempts 3]
  kernelmind report results/<run-id> [...]
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from .task import TASKS_DIR, TIERS, load_tasks


def cmd_list(args) -> int:
    for t in load_tasks(tier=args.tier):
        print(f"{t.id:40} tier {t.tier} ({TIERS[t.tier]:11}) {t.meta['root_cause']:28} {t.meta['origin']}")
    return 0


def cmd_validate(args) -> int:
    from .validate import validate_task
    all_ok = True
    report = []
    root = Path(args.tasks_dir).expanduser().resolve() if args.tasks_dir else TASKS_DIR
    for task in load_tasks(args.tasks or None, args.tier, root):
        checks = validate_task(task, args.backend)
        ok = all(c.ok for c in checks)
        all_ok &= ok
        print(f"\n{'OK  ' if ok else 'FAIL'} {task.id}")
        for c in checks:
            v = c.verdict
            score = f"{v.checks_passed}/{v.checks_total}" if v and v.checks_total is not None else ""
            got = "-" if v is None else ("pass" if v.passed else "fail")
            print(f"   {'ok ' if c.ok else 'BAD'} {c.kind:11} {c.subject:24} expect {c.expected:4} got {got:4} "
                  f"{score:>9}  {c.reason}")
            report.append({"task": c.task, "subject": c.subject, "kind": c.kind, "expected": c.expected,
                           "ok": c.ok, "reason": c.reason,
                           "verdict": v.to_dict() if v else None, "seconds": round(c.seconds, 1)})
    if args.json:
        Path(args.json).write_text(json.dumps(report, indent=2))
    print("\nALL TASKS VALID" if all_ok else "\nVALIDATION FAILED")
    return 0 if all_ok else 1


def cmd_run(args) -> int:
    from .run import run
    tasks = load_tasks(args.tasks or None, args.tier)
    if args.agent == "mini" and args.max_cost <= 0:
        raise SystemExit("--max-cost is required for model runs (total USD cap for this run)")
    run_dir = run(tasks, args.agent, args.model, args.attempts, args.backend, args.jobs, args.run_id,
                  args.max_cost, args.cost_per_attempt)
    from .report import load, markdown, summarize
    records = load([run_dir])
    print("\n" + markdown(summarize(records)))
    print(f"\nresults: {run_dir}")
    if args.agent == "oracle" and not all(r.get("passed") for r in records):
        print("ORACLE BELOW 100%: the harness or a task is broken")
        return 1
    return 0


def cmd_audit(args) -> int:
    from .audit import audit_task, summary_rows
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    root = Path(args.tasks_dir).expanduser().resolve()
    spent, results = 0.0, []
    for task in load_tasks(args.tasks or None, None, root):
        done = out / f"{task.id}.json"
        if done.exists() and (prev := json.loads(done.read_text()))["baseline_ok"]:  # resume: keep finished tasks
            results.append(prev)
            continue
        if args.model and spent >= args.max_cost:
            print(f"stopping: generation spend ${spent:.2f} reached --max-cost; rerun with the same --out to resume")
            break
        print(f"auditing {task.id} ...", flush=True)
        r, cost = audit_task(task, out, args.backend, args.model, args.mutants, args.near_misses, args.alternatives)
        spent += cost
        results.append(r)
        sus = [c["candidate"] for c in r["candidates"] if c["outcome"].endswith("suspect")]
        print(f"  baseline {'ok' if r['baseline_ok'] else 'BROKEN'}; suspects: {', '.join(sus) or 'none'}; ${cost:.3f}")
    table = "\n".join(summary_rows(results))
    (out / "summary.md").write_text(table + "\n")
    print("\n" + table + f"\n\ngeneration cost this run: ${spent:.2f}; details in {out}/<task>.json")
    return 0


def cmd_report(args) -> int:
    from .report import load, markdown, summarize
    rows = summarize(load([Path(d) for d in args.runs]), k=args.k)
    print(markdown(rows, k=args.k))
    return 0


def main(argv=None) -> int:
    p = argparse.ArgumentParser(prog="kernelmind")
    sub = p.add_subparsers(dest="cmd", required=True)

    s = sub.add_parser("list", help="list tasks")
    s.add_argument("--tier", type=int)
    s.set_defaults(fn=cmd_list)

    s = sub.add_parser("validate", help="check starter fails, fixes pass, wrong fixes fail")
    s.add_argument("tasks", nargs="*")
    s.add_argument("--tier", type=int)
    s.add_argument("--backend", choices=["docker", "local"], default="docker")
    s.add_argument("--json", help="write a JSON report here")
    s.add_argument("--tasks-dir", help="validate tasks from another directory, e.g. a Terminal-Bench 2.0 checkout")
    s.set_defaults(fn=cmd_validate)

    s = sub.add_parser("run", help="run an agent on tasks")
    s.add_argument("--agent", default="mini", choices=["mini", "oracle"])
    s.add_argument("--model", help="LiteLLM model name: claude-opus-5-5, gpt-6.1-sol, ollama_chat/qwen3:8b")
    s.add_argument("--tasks", nargs="*")
    s.add_argument("--tier", type=int)
    s.add_argument("--attempts", type=int, default=1)
    s.add_argument("--jobs", type=int, default=4)
    s.add_argument("--backend", choices=["docker", "local"], default="docker")
    s.add_argument("--run-id", help="reuse an id to resume an interrupted run")
    s.add_argument("--max-cost", type=float, default=0.0, help="hard total USD cap for this run (required for models)")
    s.add_argument("--cost-per-attempt", type=float, default=2.0, help="USD cap per attempt (default 2)")
    s.set_defaults(fn=cmd_run)

    s = sub.add_parser("audit", help="probe another benchmark's verifiers with near-miss and alternative solutions")
    s.add_argument("tasks", nargs="*")
    s.add_argument("--tasks-dir", required=True, help="e.g. external/tb2")
    s.add_argument("--out", required=True, help="results directory; rerun with the same one to resume")
    s.add_argument("--model", help="LiteLLM model for near misses and alternatives (omit for mutants only)")
    s.add_argument("--max-cost", type=float, default=1.0, help="USD cap on generation for this run")
    s.add_argument("--mutants", type=int, default=6)
    s.add_argument("--near-misses", type=int, default=4)
    s.add_argument("--alternatives", type=int, default=2)
    s.add_argument("--backend", choices=["docker", "local"], default="docker")
    s.set_defaults(fn=cmd_audit)

    s = sub.add_parser("report", help="leaderboard from one or more run directories")
    s.add_argument("runs", nargs="+")
    s.add_argument("-k", type=int, default=2)
    s.set_defaults(fn=cmd_report)

    args = p.parse_args(argv)
    return args.fn(args)


if __name__ == "__main__":
    sys.exit(main())
