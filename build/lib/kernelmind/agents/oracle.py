from __future__ import annotations

from pathlib import Path

from ..env import Environment
from ..task import Task
from ..verify import apply_fix
from . import Agent


class OracleAgent(Agent):
    name = "oracle"

    def run(self, env: Environment, task: Task, out_dir: Path) -> dict:
        apply_fix(env, task.fixes()[0])  # the reference solution
        return {"exit_status": "Submitted", "steps": 1, "cost_usd": 0.0}
