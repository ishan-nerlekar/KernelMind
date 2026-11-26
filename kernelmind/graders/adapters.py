"""Ways to call a grader. Each adapter turns a spec string into an object with
`grade(output, sample) -> label` (and, for LLM-judge graders, `grade_judge`).

  python:<module or file.py>:<name>[?k=v&k=v]
                                           any function or class in a grader's own source file.
                                           The file is loaded on its own (package __init__ skipped,
                                           missing heavy dependencies stubbed and reported);
                                           arguments are matched by name (solution_str, prediction,
                                           completions, ground_truth, label...); ?k=v fixes the rest;
                                           a class is instantiated and called; the verdict is taken
                                           from score/reward/acc fields, a .score attribute, or the
                                           first item of a (correct, prediction) pair. A function
                                           with no target argument is an extractor: its result is
                                           compared to the target
  cmd:<shell command>                      output on stdin; {target} substituted; verdict =
                                           last stdout line, else the exit code
  inspect:<task or scorer>                 see inspect_adapter.py
  lmeval:<task>                            see lmeval_adapter.py
"""

from __future__ import annotations

import asyncio
import importlib
import importlib.abc
import importlib.machinery
import importlib.util
import inspect
import json
import shlex
import sys
import traceback
import types
from pathlib import Path
from urllib.parse import parse_qsl

from .core import Sample, call, label

OUTPUT_NAMES = ("solution_str", "llm_solution", "prediction", "predictions", "response", "completion", "model_output", "output",
                "generation", "pred", "predict", "text", "content")
TARGET_NAMES = ("ground_truth", "label", "target", "reference", "references", "gold", "gt", "answer", "solution",
                "expected")
VERDICT_KEYS = ("score", "reward", "acc", "accuracy", "correct", "is_correct")


class _Anything:
    """Stand-in for anything from a stubbed module: callable, subclassable, usable as a decorator."""

    def __init__(self, *a, **k):
        pass

    def __call__(self, *a, **k):
        return a[0] if len(a) == 1 and not k and callable(a[0]) else _Anything()

    def __getattr__(self, name):
        if name.startswith("__"):
            raise AttributeError(name)
        return _Anything()

    def __mro_entries__(self, bases):
        return (_Anything,)

    def __or__(self, other):
        return self

    __ror__ = __or__

    def __getitem__(self, key):
        return self

    def __iter__(self):
        return iter(())

    def __bool__(self):
        return False


class _StubModule(types.ModuleType):
    def __getattr__(self, name):
        if name.startswith("__"):
            raise AttributeError(name)
        return _Anything()


class _Stubs(importlib.abc.MetaPathFinder, importlib.abc.Loader):
    def __init__(self):
        self.names: set[str] = set()

    def find_spec(self, fullname, path=None, target=None):
        if any(fullname == n or fullname.startswith(n + ".") for n in self.names):
            return importlib.machinery.ModuleSpec(fullname, self, is_package=True)
        return None

    def create_module(self, spec):
        m = _StubModule(spec.name)
        m.__path__ = []
        return m

    def exec_module(self, module):
        pass


_STUBS = _Stubs()


def load_file(path: str) -> tuple[types.ModuleType, list[str]]:
    """Import one source file on its own: its package's __init__ files are not run (they tend to pull in
    torch, registries, trainers), sibling modules still import, and a missing dependency is stubbed and
    reported rather than fatal. Returns the module and the names that were stubbed."""
    p = Path(path).resolve()
    parts, root = [p.stem], p.parent
    while (root / "__init__.py").exists():
        parts.insert(0, root.name)
        root = root.parent
    if str(root) not in sys.path:
        sys.path.insert(0, str(root))
    for i in range(1, len(parts)):
        pkg = ".".join(parts[:i])
        if pkg not in sys.modules:
            m = types.ModuleType(pkg)
            m.__path__ = [str(root.joinpath(*parts[:i]))]
            sys.modules[pkg] = m
    if _STUBS not in sys.meta_path:
        sys.meta_path.insert(0, _STUBS)  # it only answers for names already chosen for stubbing
    stubbed: list[str] = []
    for _ in range(50):
        sp = importlib.util.spec_from_file_location(".".join(parts), p)
        m = importlib.util.module_from_spec(sp)
        sys.modules[sp.name] = m
        try:
            sp.loader.exec_module(m)
            return m, stubbed
        except Exception as e:
            sys.modules.pop(sp.name, None)
            name = e.name if isinstance(e, ModuleNotFoundError) else _failing_import(e, p, root)
            if not name or name in _STUBS.names:
                raise
            for k in [k for k in sys.modules if k == name or k.startswith(name + ".")]:
                del sys.modules[k]
            _STUBS.names.add(name)
            stubbed.append(name)
    raise ImportError(f"{path}: too many missing modules ({', '.join(stubbed)})")


def _failing_import(e: Exception, target: Path, root: Path) -> str | None:
    """The module, imported by `target`, whose own import raised `e` (e.g. a registry that subclasses a
    stubbed class). Only modules inside the grader's source tree are named, so an error in the target
    itself, or in an installed library, is raised as is."""
    frames = [Path(f.filename) for f in traceback.extract_tb(e.__traceback__) if not f.filename.startswith("<")]
    after = frames[frames.index(target) + 1:] if target in frames else []
    if not after or root not in after[0].parents:
        return None
    rel = after[0].relative_to(root).with_suffix("")
    return ".".join(rel.parts[:-1] if rel.name == "__init__" else rel.parts)


def verdict(value):
    """The scoring part of a grader's return value."""
    if hasattr(value, "score") and not isinstance(value, (dict, str)):
        return value.score  # e.g. open-instruct VerificationResult
    if isinstance(value, dict):
        return next((value[k] for k in VERDICT_KEYS if k in value), value)
    if isinstance(value, (list, tuple)) and value and (len(value) == 1 or isinstance(value[0], (bool, int, float))):
        return verdict(value[0])  # [score] from a batch call, or (correct, prediction)
    return value


def _same(got, target: str) -> bool:
    """An extractor's result matches the target: same text, or the same number (18.0 vs 18), since the
    comparison that follows extraction is the grader's own and usually numeric-aware."""
    if got is None:
        return False
    got = str(got).strip()
    try:
        return got == target or float(got) == float(target)
    except ValueError:
        return False


def _value(s: str):
    try:
        return json.loads(s)
    except ValueError:
        return s


class PythonGrader:
    def __init__(self, spec: str):
        spec_, _, query = spec.partition("?")
        mod, _, attr = spec_.rpartition(":")
        self.fixed = {k: _value(v) for k, v in parse_qsl(query)}
        self.stubbed: list[str] = []
        if mod.endswith(".py"):
            m, self.stubbed = load_file(mod)
        else:
            m = importlib.import_module(mod)
        fn = getattr(m, attr)
        self.fn = fn() if inspect.isclass(fn) else fn
        self.name = f"python:{spec}"
        if self.stubbed:
            print(f"[grader-audit] {self.name}: stubbed missing modules {', '.join(self.stubbed)}", file=sys.stderr)
        params = [p for p in inspect.signature(self.fn).parameters.values()
                  if p.kind not in (p.VAR_POSITIONAL, p.VAR_KEYWORD)]
        names = [p.name for p in params]
        self.batch = bool(names) and names[0] == "completions"  # TRL reward functions
        self.out_param = "completions" if self.batch else next((n for n in OUTPUT_NAMES if n in names), None)
        self.target_param = next((n for n in TARGET_NAMES if n in names and n != self.out_param), None)
        self.other = [p.name for p in params if p.default is p.empty and p.name not in
                      (self.out_param, self.target_param) and p.name not in self.fixed]
        # No target argument: an extractor (postprocessor, answer parser); its result is compared to the target.
        self.extractor = self.out_param is not None and self.target_param is None
        self.by_name = self.out_param is not None
        self._with_sample = not self.by_name and len(params) >= 3

    async def grade(self, output: str, sample: Sample) -> str:
        if self.by_name:
            kw = dict(self.fixed)
            kw.update({n: None for n in self.other})  # e.g. open-instruct's tokenized_prediction, unused for text
            if self.batch:
                kw["completions"] = [[{"role": "assistant", "content": output}]]
                kw[self.target_param] = [sample.target]
            elif self.extractor:
                kw[self.out_param] = output
                got = await call(self.fn, **kw)
                return label(_same(got, sample.target))
            else:
                kw[self.out_param], kw[self.target_param] = output, sample.target
            return label(verdict(await call(self.fn, **kw)))
        args = (output, sample.target, sample) if self._with_sample else (output, sample.target)
        return label(verdict(await call(self.fn, *args, **self.fixed)))


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
