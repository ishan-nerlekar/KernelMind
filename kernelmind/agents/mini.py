"""mini-swe-agent adapter: the agent loop and prompts are mini-swe-agent's own (config mini.yaml);
only command execution is routed into our sandboxed Environment."""
from __future__ import annotations

from pathlib import Path

import yaml
import minisweagent
from minisweagent.agents.default import DefaultAgent
from minisweagent.exceptions import Submitted
from minisweagent.models import get_model

from ..env import Environment
from ..task import Task
from . import Agent

SUBMIT = "COMPLETE_TASK_AND_SUBMIT_FINAL_OUTPUT"


class _EnvAdapter:
    """Implements the small environment protocol mini-swe-agent expects."""

    def __init__(self, env: Environment, timeout: int, extra_env: dict[str, str]):
        self.env, self.timeout = env, timeout
        self.prefix = "".join(f"export {k}={v!r}; " for k, v in extra_env.items())

    def execute(self, action, cwd: str = "", *, timeout: int | None = None) -> dict:
        command = action.get("command", "") if isinstance(action, dict) else str(action)
        r = self.env.exec(self.prefix + command, timeout=timeout or self.timeout)
        lines = r.output.lstrip().splitlines(keepends=True)
        if lines and lines[0].strip() == SUBMIT and r.returncode == 0:
            raise Submitted({"role": "exit", "content": "", "extra": {"exit_status": "Submitted", "submission": ""}})
        return {"output": r.output, "returncode": r.returncode,
                "exception_info": f"command timed out after {timeout or self.timeout}s" if r.timed_out else ""}

    def get_template_vars(self, **kwargs) -> dict:
        return {"system": "Linux", "release": "", "version": "", "machine": "", **kwargs}

    def serialize(self) -> dict:
        return {"info": {"config": {"environment_type": "kernelmind"}}}


class MiniAgent(Agent):
    name = "mini"

    def __init__(self, model: str, step_limit: int = 150, cost_limit: float = 5.0):
        self.model = model
        self.step_limit, self.cost_limit = step_limit, cost_limit
        config_path = Path(minisweagent.__file__).parent / "config" / "mini.yaml"
        self.config = yaml.safe_load(config_path.read_text())

    def run(self, env: Environment, task: Task, out_dir: Path) -> dict:
        limits = task.limits
        model = get_model(self.model, self.config.get("model", {}))
        adapter = _EnvAdapter(env, limits["command_timeout_sec"], self.config.get("environment", {}).get("env", {}))
        agent_cfg = {k: v for k, v in self.config["agent"].items() if k != "mode"}
        agent_cfg.update(step_limit=self.step_limit, cost_limit=self.cost_limit,
                         wall_time_limit_seconds=limits["agent_timeout_sec"],
                         output_path=out_dir / "trajectory.json")
        agent = DefaultAgent(model, adapter, **agent_cfg)
        prompt = task.instruction + "\n\nThe codebase is in /app (your working directory)."
        try:
            info = agent.run(prompt)
            status = info.get("exit_status", "")
        except Exception as e:  # model/API errors end the attempt; the verifier still runs
            status = f"AgentError: {type(e).__name__}: {e}"
        return {"exit_status": status, "steps": agent.n_calls, "cost_usd": round(agent.cost, 4)}
