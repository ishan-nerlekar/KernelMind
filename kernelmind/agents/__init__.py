"""Agents that attempt a task inside an Environment.

- oracle: applies the reference solution. Proves the pipeline works end to end (score must be 100%).
- mini:   mini-swe-agent, a small open scaffold (bash-only tool loop). Every model runs
          through the same scaffold, prompts and limits, so score differences come from the model.
"""
from __future__ import annotations

from pathlib import Path

from ..env import Environment
from ..task import Task


class BudgetExceeded(Exception):
    """The run's total spending cap was reached. Not a model failure: the attempt is not scored."""


def get_agent(name: str, model: str | None, cost_per_attempt: float = 5.0):
    if name == "oracle":
        from .oracle import OracleAgent
        return OracleAgent()
    if name == "mini":
        if not model:
            raise SystemExit("--model is required for the mini agent (a LiteLLM model name)")
        from .mini import MiniAgent
        return MiniAgent(model, cost_limit=cost_per_attempt)
    raise SystemExit(f"unknown agent '{name}' (choose oracle or mini)")


class Agent:
    name: str
    model: str | None = None

    def run(self, env: Environment, task: Task, out_dir: Path) -> dict:
        """Work on the task in env. Returns {exit_status, steps, cost_usd}."""
        raise NotImplementedError
