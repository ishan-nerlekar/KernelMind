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
from . import Agent, BudgetExceeded

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
        import litellm
        self.model = model
        self.step_limit, self.cost_limit = step_limit, cost_limit
        config_path = Path(minisweagent.__file__).parent / "config" / "mini.yaml"
        self.config = yaml.safe_load(config_path.read_text())
        # Local (Ollama) or very new models have no price in LiteLLM's table. Record $0 instead of
        # crashing; the per-attempt step limit still bounds the run.
        self.priced = model in litellm.model_cost or model.split("/", 1)[-1] in litellm.model_cost
        if not self.priced:
            self.config.setdefault("model", {})["cost_tracking"] = "ignore_errors"
        if model.startswith(("ollama/", "ollama_chat/")):
            # Ollama's default context is a few thousand tokens and silently truncates long agent
            # histories. 16K fits a 8B model plus Docker in 16 GB of RAM.
            kwargs = self.config.setdefault("model", {}).setdefault("model_kwargs", {})
            kwargs["num_ctx"] = 16384

    def preflight(self) -> None:
        """One tiny real request before any attempt starts: catches a bad key, model name, missing
        dependency or stopped Ollama in seconds, instead of after minutes of retries."""
        import litellm
        kwargs = {k: v for k, v in self.config.get("model", {}).get("model_kwargs", {}).items()
                  if k != "drop_params"}
        try:
            litellm.completion(model=self.model, messages=[{"role": "user", "content": "Reply with OK."}],
                               max_tokens=256, drop_params=True, num_retries=0, **kwargs)
        except Exception as e:
            raise SystemExit(f"Preflight failed for model '{self.model}': {type(e).__name__}: {str(e)[:400]}")

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
            if "Global cost/call limit exceeded" in str(e):
                raise BudgetExceeded(str(e)) from e
            status = f"AgentError: {type(e).__name__}: {e}"
        return {"exit_status": status, "steps": agent.n_calls, "cost_usd": round(agent.cost, 4),
                "cost_known": self.priced}
