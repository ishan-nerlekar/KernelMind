"""Aggregate run results into a leaderboard.

pass@1  = average over tasks of (successful attempts / attempts). The headline number.
pass@k  = chance at least one of k attempts succeeds, unbiased estimator from Chen et al. 2021
          (the Codex/HumanEval paper): 1 - C(n-c, k) / C(n, k), averaged over tasks.
95% CI  = bootstrap over tasks: resample the task set with replacement 2000 times.
          Uncertainty comes mostly from having few tasks, so we resample tasks, not attempts.
Infrastructure errors (passed = null) are excluded and reported separately.
"""
from __future__ import annotations

import json
import random
import statistics
from collections import defaultdict
from math import comb
from pathlib import Path


def pass_at_k(n: int, c: int, k: int) -> float:
    if n - c < k:
        return 1.0
    return 1.0 - comb(n - c, k) / comb(n, k)


def bootstrap_ci(values: list[float], iters: int = 2000, seed: int = 0) -> tuple[float, float]:
    if len(values) < 2:
        return (float("nan"), float("nan"))
    rng = random.Random(seed)
    means = sorted(statistics.fmean(rng.choices(values, k=len(values))) for _ in range(iters))
    return means[int(0.025 * iters)], means[int(0.975 * iters) - 1]


def load(run_dirs: list[Path]) -> list[dict]:
    return [json.loads(p.read_text()) for d in run_dirs for p in sorted(d.glob("*/attempt-*/result.json"))]


def summarize(records: list[dict], k: int = 3) -> list[dict]:
    groups: dict[tuple, list[dict]] = defaultdict(list)
    for r in records:
        groups[(r["agent"], r.get("model") or "-")].append(r)
    rows = []
    for (agent, model), recs in sorted(groups.items()):
        scored = [r for r in recs if r.get("passed") is not None]
        by_task: dict[str, list[bool]] = defaultdict(list)
        tier_of = {}
        for r in scored:
            by_task[r["task"]].append(bool(r["passed"]))
            tier_of[r["task"]] = r["tier"]
        p1 = {t: sum(v) / len(v) for t, v in by_task.items()}
        pk = {t: pass_at_k(len(v), sum(v), k) for t, v in by_task.items() if len(v) >= k}
        tiers = {}
        for tier in sorted(set(tier_of.values())):
            vals = [p1[t] for t in p1 if tier_of[t] == tier]
            tiers[f"tier{tier}"] = statistics.fmean(vals)
        lo, hi = bootstrap_ci(list(p1.values()))
        rows.append({
            "agent": agent, "model": model, "tasks": len(by_task), "attempts": len(scored),
            "errors": len(recs) - len(scored),
            "pass@1": statistics.fmean(p1.values()) if p1 else float("nan"),
            "ci95": (lo, hi),
            f"pass@{k}": statistics.fmean(pk.values()) if pk else None,
            **tiers,
            "cost_usd": sum(r.get("cost_usd") or 0 for r in scored),
            "median_seconds": statistics.median([r["seconds"] for r in scored]) if scored else None,
        })
    return sorted(rows, key=lambda r: -r["pass@1"])


def markdown(rows: list[dict], k: int = 3) -> str:
    tier_cols = sorted({c for r in rows for c in r if c.startswith("tier")})
    head = ["Agent", "Model", "Tasks", "pass@1", "95% CI", f"pass@{k}", *tier_cols, "Cost ($)", "Median s", "Errors"]
    pct = lambda x: "-" if x is None or x != x else f"{100 * x:.1f}%"
    lines = ["| " + " | ".join(head) + " |", "|" + "---|" * len(head)]
    for r in rows:
        lo, hi = r["ci95"]
        lines.append("| " + " | ".join([
            r["agent"], r["model"], str(r["tasks"]), pct(r["pass@1"]),
            "-" if lo != lo else f"{100 * lo:.0f}-{100 * hi:.0f}%", pct(r.get(f"pass@{k}")),
            *[pct(r.get(c)) for c in tier_cols], f"{r['cost_usd']:.2f}",
            "-" if r["median_seconds"] is None else f"{r['median_seconds']:.0f}", str(r["errors"])]) + " |")
    return "\n".join(lines)
