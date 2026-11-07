"""Load tasks from tasks/<id>/.

Layout of one task:

    task.toml              metadata (tier, root cause, origin, limits)
    instruction.md         the only text the agent is given
    environment/           Docker build context; environment/app/ becomes /app
    tests/test.sh          hidden verifier, copied in after the agent finishes
    solution/solve.sh      reference fix (must pass)
    alternatives/*/solve.sh  other valid fixes (must pass)
    controls/*/solve.sh    plausible wrong fixes (must fail)
"""
from __future__ import annotations

import tomllib
from dataclasses import dataclass, field
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
TASKS_DIR = REPO / "tasks"
TIERS = {1: "localized", 2: "diagnose", 3: "investigate"}
REQUIRED = ("id", "tier", "root_cause", "origin")


@dataclass
class Fix:
    """A scripted change applied to /app: a reference, alternative or control."""
    name: str
    kind: str  # "reference" | "alternative" | "control"
    path: Path
    expect_failures: list[str] = field(default_factory=list)

    @property
    def should_pass(self) -> bool:
        return self.kind != "control"


@dataclass
class Task:
    root: Path
    meta: dict

    @property
    def id(self) -> str:
        return self.meta["id"]

    @property
    def tier(self) -> int:
        return int(self.meta["tier"])

    @property
    def instruction(self) -> str:
        return (self.root / "instruction.md").read_text()

    @property
    def limits(self) -> dict:
        return {"agent_timeout_sec": 1800, "test_timeout_sec": 600, "command_timeout_sec": 120,
                **self.meta.get("limits", {})}

    @property
    def docker(self) -> dict:
        return {"cap_add": [], "memory": "4g", "cpus": "2", **self.meta.get("docker", {})}

    def fixes(self) -> list[Fix]:
        out = [Fix("reference", "reference", self.root / "solution")]
        for kind, folder in (("alternative", "alternatives"), ("control", "controls")):
            for d in sorted((self.root / folder).glob("*/")):
                expect = d / "expect.txt"
                lines = [l.strip() for l in expect.read_text().splitlines()] if expect.exists() else []
                out.append(Fix(d.name, kind, d, [l for l in lines if l and not l.startswith("#")]))
        return out

    def problems(self) -> list[str]:
        """Structural checks that need no execution."""
        if self.meta.get("external"):  # someone else's task being audited: only what grading needs
            return [f"missing {rel}" for rel in ("environment/Dockerfile", "tests/test.sh", "solution/solve.sh")
                    if not (self.root / rel).exists()]
        errs = [f"task.toml missing '{k}'" for k in REQUIRED if k not in self.meta]
        if self.meta.get("id") != self.root.name:
            errs.append(f"id '{self.meta.get('id')}' does not match directory '{self.root.name}'")
        if self.meta.get("tier") not in TIERS:
            errs.append(f"tier must be one of {sorted(TIERS)}")
        for rel in ("instruction.md", "environment/Dockerfile", "environment/app", "tests/test.sh",
                    "solution/solve.sh"):
            if not (self.root / rel).exists():
                errs.append(f"missing {rel}")
        controls = [f for f in self.fixes() if f.kind == "control"]
        if len(controls) < 3:
            errs.append(f"needs at least 3 wrong-fix controls, has {len(controls)}")
        return errs


def _from_harbor(path: Path, m: dict) -> dict:
    """Map a Harbor-format task.toml (Terminal-Bench 2.0) onto KernelMind's fields."""
    env = m.get("environment", {})
    return {"id": path.name, "tier": 0, "origin": "terminal-bench-2", "external": True,
            "prebuilt_image": env.get("docker_image"),
            "root_cause": m.get("metadata", {}).get("category", "unknown"),
            "limits": {"agent_timeout_sec": int(m.get("agent", {}).get("timeout_sec", 1800)),
                       "test_timeout_sec": int(m.get("verifier", {}).get("timeout_sec", 600))},
            "docker": {"memory": f"{env.get('memory_mb', 4096)}m", "cpus": str(env.get("cpus", 2)),
                       "network": "bridge" if env.get("allow_internet") else "none"}}


def load_task(path: Path) -> Task:
    meta = tomllib.loads((path / "task.toml").read_text())
    if "name" in meta.get("task", {}):
        meta = _from_harbor(path, meta)
    return Task(path, meta)


def load_tasks(ids: list[str] | None = None, tier: int | None = None, root: Path = TASKS_DIR) -> list[Task]:
    tasks = [load_task(p) for p in sorted(root.iterdir()) if (p / "task.toml").exists()]
    if ids:
        known = {t.id for t in tasks}
        missing = [i for i in ids if i not in known]
        if missing:
            raise SystemExit(f"unknown task(s): {', '.join(missing)}")
        tasks = [t for t in tasks if t.id in ids]
    if tier:
        tasks = [t for t in tasks if t.tier == tier]
    return tasks
