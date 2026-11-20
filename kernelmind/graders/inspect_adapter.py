"""Inspect adapter: audit a task's own scorer without datasets, API keys or network.

Spec:
  inspect:<task>[?arg=value&...]     e.g. inspect:inspect_evals/gsm8k,
                                     inspect:inspect_evals/simpleqa_verified?scorer=original
  inspect:scorer:<registered scorer> e.g. inspect:scorer:inspect_evals/llm_judge_scorer
                                     (built with its default arguments)

How the scorer is reached:
  - The task is built with dataset loaders swapped for a one-sample in-memory dataset, so
    the scorer is exactly the one the task configures. If the task can't be built offline,
    use the scorer: form.
  - The model output is replayed through the task's solver (e.g. multiple_choice, which
    parses the letter before choice() scores it) with generate() stubbed; if the solver
    can't run offline, the output goes straight into the TaskState.
  - Every LLM call the scorer makes goes through Model.generate, which is patched to
    return a scripted judge reply and record the prompt. Any model name resolves to
    mockllm, so no API key is needed.
"""

from __future__ import annotations

import contextlib
import math
import sys
from typing import Any
from urllib.parse import parse_qsl

from .core import UNSCORED, Sample, label

_REPLY: dict[str, Any] = {"text": "UNSURE", "calls": 0, "prompt": ""}
_PATCHED = False


def _usage_output(content: str):
    from inspect_ai.model import ModelOutput, ModelUsage

    o = ModelOutput.from_content(model="mockllm/model", content=content)
    o.usage = ModelUsage(input_tokens=1, output_tokens=1, total_tokens=2)  # no tiktoken download
    return o


def _msg_text(m) -> str:
    c = getattr(m, "content", "")
    return c if isinstance(c, str) else " ".join(getattr(x, "text", "") or "" for x in c)


def _patch_models() -> None:
    """Route every model to mockllm and script its replies (idempotent)."""
    global _PATCHED
    if _PATCHED:
        return
    import inspect_ai.model._model as mm
    from inspect_ai.model import GenerateConfig, get_model
    from inspect_ai.model._model import init_active_model, init_model_roles

    from inspect_ai._util.registry import registry_info, registry_unqualified_name

    real_find = mm.registry_find
    get_model("mockllm/model", memoize=False)  # make sure the provider is registered
    mock_type = real_find(lambda i: i.type == "modelapi" and registry_unqualified_name(i) == "mockllm")[0]

    def find(pred):
        res = real_find(pred)
        if mock_type is None or not res or registry_info(res[0]).type != "modelapi":
            return res
        return [mock_type]  # any provider (openai/..., anthropic/...) becomes mockllm

    mm.registry_find = find

    async def generate(self, input, *args, **kwargs):  # noqa: A002
        _REPLY["calls"] += 1
        msgs = input if isinstance(input, list) else [input]
        _REPLY["prompt"] = "\n".join(m if isinstance(m, str) else _msg_text(m) for m in msgs)
        return _usage_output(_REPLY["text"])

    mm.Model.generate = generate
    init_active_model(get_model("mockllm/model", memoize=False), GenerateConfig())
    init_model_roles({})
    _PATCHED = True


@contextlib.contextmanager
def _offline_datasets(sample: Sample):
    """Swap dataset loaders for a one-sample dataset while a task is built."""
    from inspect_ai import dataset as ds
    from inspect_ai.dataset import MemoryDataset
    from inspect_ai.dataset import Sample as ISample

    class AnyKey(dict):
        """Metadata that has every key, so task-building code (few-shot prompts) runs."""

        def __missing__(self, key):
            return "placeholder"

        def get(self, key, default=None):
            return dict.get(self, key, "placeholder")

        def __contains__(self, key):
            return True

        def __bool__(self):
            return True

    def one(*_, **__):
        samples = [ISample(input=sample.input, target=sample.target, choices=sample.choices, id=i)
                   for i in range(1, 4)]  # a few, for tasks that split off few-shot examples
        for s in samples:
            object.__setattr__(s, "metadata", AnyKey(sample.metadata))
        return MemoryDataset(samples)

    def no_hf(*_, **__):
        raise RuntimeError("offline: datasets.load_dataset is not available")

    import tempfile

    from inspect_ai import util as iutil

    def no_download(*_, **__):  # a dataset file download: hand back an empty file
        return tempfile.NamedTemporaryFile(delete=False).name

    targets = [(ds, n) for n in ("hf_dataset", "json_dataset", "csv_dataset", "file_dataset")]
    targets.append((iutil, "download", no_download))
    for modname in ("inspect_evals_utils.huggingface", "inspect_evals.utils.huggingface"):
        with contextlib.suppress(ImportError):
            mod = __import__(modname, fromlist=["x"])
            targets += [(mod, "hf_dataset")]
            targets += [(mod, "load_dataset", no_hf)] if hasattr(mod, "load_dataset") else []
    for modname in ("inspect_evals.utils", "inspect_evals.utils.load_dataset"):
        with contextlib.suppress(ImportError):
            mod = __import__(modname, fromlist=["x"])
            targets += [(mod, n) for n in ("load_csv_dataset", "load_json_dataset")]
    # replace each loader wherever it is bound, including `from x import loader` copies
    # already made by eval modules
    repl_for = {}
    for t in targets:
        mod, name, repl = (t + (one,))[:3]
        if hasattr(mod, name):
            repl_for[id(getattr(mod, name))] = (getattr(mod, name), repl)
    saved = []
    for mname, mod in list(sys.modules.items()):
        if not mname.startswith(("inspect_ai", "inspect_evals")) or mod is None:
            continue
        for attr, val in list(vars(mod).items()):
            hit = repl_for.get(id(val))
            if hit and hit[0] is val:
                saved.append((mod, attr, val))
                setattr(mod, attr, hit[1])
    try:
        yield
    finally:
        for mod, name, fn in saved:
            setattr(mod, name, fn)


def _build(spec: str, sample: Sample, task_args: dict | None = None):
    """(scorers, solver) for a spec."""
    _patch_models()
    if spec.startswith("scorer:"):
        from inspect_ai._util.registry import registry_create

        name = spec.removeprefix("scorer:")
        if "/" in name:
            __import__(name.split("/")[0])  # registers the package's scorers
        return [registry_create("scorer", name)], None
    from inspect_ai._eval.loader import load_tasks

    from inspect_ai._util.registry import registry_lookup

    name, _, query = spec.partition("?")
    args = {**(task_args or {}), **{k: _coerce(v) for k, v in parse_qsl(query)}}
    registry_lookup("task", name)  # import the eval's modules first, then swap their loaders
    with _offline_datasets(sample):
        task = load_tasks([name], args)[0]
    return list(task.scorer or []), task.solver


def _coerce(v: str):
    low = v.lower()
    if low in ("true", "false"):
        return low == "true"
    try:
        return int(v)
    except ValueError:
        return v


class _Stop(Exception):
    pass


class InspectGrader:
    def __init__(self, spec: str, scorer_index: int = 0, task_args: dict | None = None):
        self.spec = spec
        self.task_args = task_args or {}
        self.name = f"inspect:{spec}" + (f"#{scorer_index}" if scorer_index else "")
        self.index = scorer_index
        self._built: dict[str, Any] = {}
        self.judge_prompt = ""
        self.solver_ok: bool | None = None

    def _scorer(self, sample: Sample):
        if "scorers" not in self._built:
            scorers, solver = _build(self.spec, sample, self.task_args)
            if not scorers:
                raise RuntimeError("task has no scorer")
            self._built = {"scorers": scorers, "solver": solver}
        return self._built["scorers"][self.index], self._built["solver"]

    async def _state(self, output: str, sample: Sample, solver):
        from inspect_ai.model import ChatMessageAssistant, ChatMessageUser
        from inspect_ai.solver import TaskState

        st = TaskState(model="mockllm/model", sample_id=sample.id, epoch=1, input=sample.input,
                       choices=sample.choices, messages=[ChatMessageUser(content=sample.input)],
                       metadata=dict(sample.metadata))
        if solver is not None and self.solver_ok is not False:
            calls = 0

            async def generate(state, *_, **__):
                nonlocal calls
                calls += 1
                if calls > 2:
                    raise _Stop  # an agent loop: replaying it offline is out of scope
                state.output = _usage_output(output)
                state.messages.append(state.output.message)
                return state

            try:
                st = await solver(st, generate)
                self.solver_ok = True
                return st
            except Exception:  # noqa: BLE001
                self.solver_ok = False
                st.messages = [ChatMessageUser(content=sample.input)]
        st.output = _usage_output(output)
        st.messages.append(ChatMessageAssistant(content=output))
        return st

    async def _score(self, output: str, sample: Sample) -> str:
        from inspect_ai.scorer import Target

        scorer, solver = self._scorer(sample)
        st = await self._state(output, sample, solver)
        sc = await scorer(st, Target(sample.target))
        if sc is None:
            return UNSCORED
        v = sc.value
        if isinstance(v, float) and math.isnan(v):
            return UNSCORED
        return label(v)

    async def grade(self, output: str, sample: Sample) -> str:
        _REPLY["text"] = "UNSURE"
        return await self._score(output, sample)

    async def uses_judge(self, sample: Sample) -> bool:
        _REPLY["calls"] = 0
        try:
            await self.grade(sample.output or f"The answer is {sample.target}.", sample)
        except Exception:  # noqa: BLE001
            pass
        return _REPLY["calls"] > 0

    async def grade_judge(self, reply: str, output: str, sample: Sample) -> str:
        _REPLY["text"] = reply
        try:
            return await self._score(output, sample)
        finally:
            self.judge_prompt = _REPLY["prompt"] or self.judge_prompt


def samples_from_log(path: str, limit: int = 1) -> list[Sample]:
    from inspect_ai.log import read_eval_log

    log = read_eval_log(path)
    out = []
    for s in (log.samples or [])[:limit]:
        target = s.target if isinstance(s.target, str) else ",".join(s.target)
        out.append(Sample(target=target, choices=s.choices, input=s.input if isinstance(s.input, str) else
                          "\n".join(_msg_text(m) for m in s.input), metadata=dict(s.metadata or {}),
                          output=s.output.completion if s.output else None, id=str(s.id)))
    return out


def grader_from_log(path: str, limit: int = 1) -> tuple["InspectGrader", list[Sample]]:
    """The scorer of the task that produced a log (same task arguments), and its samples.
    Model arguments are dropped: every model is replayed offline anyway."""
    from inspect_ai.log import read_eval_log

    ev = read_eval_log(path, header_only=True).eval
    args = {k: v for k, v in (ev.task_args or {}).items() if not (isinstance(v, dict) and "model" in v)}
    return InspectGrader(ev.task, task_args=args), samples_from_log(path, limit)
