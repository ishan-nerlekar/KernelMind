"""T4: measure the auditor on KernelMind tasks with planted grader flaws (see tools/plant_flaws.py).

1. Audit each weakened copy in audit/planted-kernelmind/ (candidates are generated there).
2. Regrade the *same* candidates against the task's original, sound tests.
3. A candidate that passes the weakened grader but fails the sound one has found the planted flaw.
   A candidate that passes the sound grader as a lenient suspect, or an alternative it rejects, is a
   suspect against a sound grader: an equivalent mutant, a bad candidate, or a real weakness in
   KernelMind's own tests. Each needs a manual look before it counts as a false positive.

    python3 tools/audit_planted.py --model claude-haiku-5-5 --max-cost 1     # resumable
"""
from __future__ import annotations

import argparse
import json
import shutil
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))

from kernelmind.audit import audit_task, classify  # noqa: E402
from kernelmind.task import load_task, load_tasks  # noqa: E402
from kernelmind.validate import validate_task  # noqa: E402

PLANTED = REPO / "audit" / "planted-kernelmind"
SKIP = {"x-push-lost-update"}  # its witness passes or fails from run to run: no stable ground truth


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--model", required=True)
    p.add_argument("--max-cost", type=float, default=1.0)
    p.add_argument("--out", default=str(REPO / "results" / "audit-planted"))
    p.add_argument("--backend", default="docker")
    a = p.parse_args()
    out, regrade = Path(a.out), Path(a.out) / "regrade"
    regrade.mkdir(parents=True, exist_ok=True)
    flaws = {f["task"]: f for f in json.loads((PLANTED / "planted.json").read_text())}
    spent, rows = 0.0, []
    for task in load_tasks(root=PLANTED):
        if task.id in SKIP:
            continue
        done = out / f"{task.id}.json"
        if done.exists() and (r := json.loads(done.read_text()))["baseline_ok"]:
            weak = r
        else:
            if spent >= a.max_cost:
                print("stopping at --max-cost; rerun to resume")
                break
            print(f"auditing weakened {task.id} ...", flush=True)
            weak, cost = audit_task(task, out, a.backend, a.model, 6, 4, 2)
            spent += cost
        rg = regrade / f"{task.id}.json"
        if rg.exists():
            sound = json.loads(rg.read_text())
        else:
            print(f"regrading {task.id} against the original tests ...", flush=True)
            dst = regrade / "tasks" / task.id
            if dst.exists():
                shutil.rmtree(dst)
            shutil.copytree(out / "tasks" / task.id, dst)
            shutil.rmtree(dst / "tests")
            shutil.copytree(REPO / "tasks" / task.id / "tests", dst / "tests")
            meta = json.loads((dst / "audit_candidates.json").read_text())
            sound = {"task": task.id, **classify(validate_task(load_task(dst), a.backend), meta)}
            rg.write_text(json.dumps(sound, indent=1, default=str))
        w = {c["candidate"]: c["outcome"] for c in weak["candidates"]}
        s = {c["candidate"]: c for c in sound["candidates"]}
        finders = [n for n, o in w.items() if o == "lenient-suspect" and s.get(n, {}).get("outcome") == "caught"]
        if weak.get("starter_passes") and not sound.get("starter_passes"):
            finders.insert(0, "starter")  # the weakened grader accepts doing nothing
        sound_suspects = [n for n, c in s.items() if c["outcome"].endswith("suspect")]
        rows.append({"task": task.id, "removed": flaws[task.id]["removed_tests"],
                     "gross": flaws[task.id].get("gross"), "detected": bool(finders), "found_by": finders,
                     "sound_grader_suspects": sound_suspects,
                     "graded": sum(o != "broken-candidate" for o in w.values()),
                     "broken": sum(o == "broken-candidate" for o in w.values())})
    lines = ["| Task | Planted flaw (tests disabled) | Kind | Detected | Found by | Suspects vs sound grader |",
             "|---|---|---|---|---|---|"]
    for r in rows:
        lines.append(f"| {r['task']} | {', '.join(r['removed'])} | {'gross' if r['gross'] else 'subtle'} "
                     f"| {'yes' if r['detected'] else 'NO'} | {', '.join(r['found_by']) or '-'} "
                     f"| {', '.join(r['sound_grader_suspects']) or '-'} |")
    for kind, sel in (("subtle", [r for r in rows if not r["gross"]]), ("gross", [r for r in rows if r["gross"]])):
        lines.append(f"\n{kind}: detected {sum(r['detected'] for r in sel)}/{len(sel)}")
    lines.append(f"\nsuspects against sound graders (need manual review): {sum(len(r['sound_grader_suspects']) for r in rows)}"
                 f" across {len(rows)} tasks; generation cost this run ${spent:.2f}")
    (out / "T4.md").write_text("\n".join(lines) + "\n")
    print("\n".join(lines))
    return 0


if __name__ == "__main__":
    sys.exit(main())
