"""lm-evaluation-harness adapter: a task's own filter pipeline and metric, run offline.

Spec: lmeval:<task>[@<filter pipeline>]   e.g. lmeval:mmlu_pro_biology,
                                          lmeval:turkishmmlu_cot_biology@get-choice

The task's YAML (includes resolved) gives the filter_list and metric_list; each filter is
built the way lm-eval builds it, and the metric is called the way lm-eval's
ConfigurableTask calls it for generate_until tasks. The gold answer is the sample's
target (no dataset is downloaded), so tasks with their own process_results are skipped.
"""

from __future__ import annotations

from .core import Sample, label

_TM = None


def _task_manager():
    global _TM
    if _TM is None:
        import logging

        logging.getLogger("lm-eval").setLevel(logging.ERROR)
        from lm_eval.tasks import TaskManager

        _TM = TaskManager()
    return _TM


def task_config(task: str) -> dict:
    from lm_eval.tasks._yaml_loader import load_yaml

    entry = _task_manager().task_index[task]
    if not entry.yaml_path:
        raise ValueError(f"{task} has no YAML config")
    return load_yaml(entry.yaml_path, resolve_func=True)


class LmEvalGrader:
    def __init__(self, spec: str):
        from lm_eval.api.registry import get_metric
        from lm_eval.filters import build_filter_ensemble

        task, _, pipeline = spec.partition("@")
        cfg = task_config(task)
        if cfg.get("output_type") != "generate_until":
            raise ValueError(f"{task}: output_type {cfg.get('output_type')!r} (only generate_until is graded from text)")
        if cfg.get("process_results"):
            raise ValueError(f"{task}: custom process_results needs a real document")
        pipelines = cfg.get("filter_list") or [{"name": "none", "filter": [{"function": "take_first"}]}]
        chosen = next((p for p in pipelines if p["name"] == pipeline), None) if pipeline else pipelines[0]
        if chosen is None:
            raise ValueError(f"{task}: no filter pipeline {pipeline!r} ({[p['name'] for p in pipelines]})")
        self.filter = build_filter_ensemble(
            chosen["name"], [(f["function"], {k: v for k, v in f.items() if k != "function"}) for f in chosen["filter"]])
        self.metrics = []
        for m in cfg.get("metric_list") or [{"metric": "exact_match"}]:
            name = m["metric"]
            fn = name if callable(name) else get_metric(name, m.get("hf_evaluate", False))
            if fn is None:
                continue
            kw = {k: v for k, v in m.items() if k not in ("metric", "aggregation", "higher_is_better", "hf_evaluate")}
            self.metrics.append((getattr(fn, "__name__", str(name)), fn, kw))
        if not self.metrics:
            raise ValueError(f"{task}: no metric lm-eval can compute here")
        self.name = f"lmeval:{task}@{chosen['name']}"

    async def grade(self, output: str, sample: Sample) -> str:
        doc = {"choices": sample.choices or [], **sample.metadata}
        resps = [[output]]
        for f in self.filter.filters:
            resps = list(f().apply(resps, [doc]))
        result = resps[0]
        gold = sample.target
        scores = {}
        for name, fn, kw in self.metrics:
            try:
                v = fn(references=[gold], predictions=[result], **kw)
            except TypeError:
                v = fn([gold, result])
            scores[name] = v.get(name, next(iter(v.values()))) if isinstance(v, dict) else v
        return label(scores if len(scores) > 1 else next(iter(scores.values())))
