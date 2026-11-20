"""Ways to call a grader. Each adapter turns a spec string into an object with
`grade(output, sample) -> label` (and, for LLM-judge graders, `grade_judge`).

  python:<module or file.py>:<function>   fn(output, target) or fn(output, target, sample)
  cmd:<shell command>                      output on stdin; {target} substituted; verdict =
                                           last stdout line, else the exit code
  inspect:<task or scorer>                 see inspect_adapter.py
  lmeval:<task>                            see lmeval_adapter.py
"""

from __future__ import annotations

import asyncio
import importlib
import importlib.util
import inspect
import shlex
from pathlib import Path

from .core import Sample, call, label


class PythonGrader:
    def __init__(self, spec: str):
        mod, _, fn = spec.rpartition(":")
        if mod.endswith(".py"):
            sp = importlib.util.spec_from_file_location(Path(mod).stem, mod)
            m = importlib.util.module_from_spec(sp)
            sp.loader.exec_module(m)
        else:
            m = importlib.import_module(mod)
        self.fn = getattr(m, fn)
        self.name = f"python:{spec}"
        self._with_sample = len(inspect.signature(self.fn).parameters) >= 3

    async def grade(self, output: str, sample: Sample) -> str:
        args = (output, sample.target, sample) if self._with_sample else (output, sample.target)
        return label(await call(self.fn, *args))


class CommandGrader:
    def __init__(self, command: str):
        self.command = command
        self.name = f"cmd:{command}"

    async def grade(self, output: str, sample: Sample) -> str:
        cmd = self.command.replace("{target}", shlex.quote(sample.target))
        p = await asyncio.create_subprocess_shell(cmd, stdin=asyncio.subprocess.PIPE,
                                                  stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.DEVNULL)
        out, _ = await asyncio.wait_for(p.communicate(output.encode()), timeout=60)
        last = out.decode(errors="replace").strip().splitlines()
        return last[-1].strip() if last else f"exit={p.returncode}"


def load_grader(spec: str):
    kind, _, rest = spec.partition(":")
    if kind == "python":
        return PythonGrader(rest)
    if kind == "cmd":
        return CommandGrader(rest)
    if kind == "inspect":
        from .inspect_adapter import InspectGrader
        return InspectGrader(rest)
    if kind == "lmeval":
        from .lmeval_adapter import LmEvalGrader
        return LmEvalGrader(rest)
    raise ValueError(f"unknown grader kind {kind!r} (python:, cmd:, inspect:, lmeval:)")
