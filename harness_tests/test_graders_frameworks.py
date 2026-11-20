"""Adapter checks against real frameworks; skipped where inspect_ai / lm_eval aren't installed."""
import asyncio

import pytest

from kernelmind.graders.core import Sample, audit, findings


def _rewrites(res):
    return {r.rewrite for r in findings(res)}


def test_inspect_gsm8k_match_numeric():
    pytest.importorskip("inspect_evals")
    from kernelmind.graders.inspect_adapter import InspectGrader

    res = asyncio.run(audit(InspectGrader("inspect_evals/gsm8k"), Sample("18")))
    assert {"boxed", "reasoning_number_unparseable_final"} <= _rewrites(res)  # inspect_ai #6536


def test_inspect_sosbench_judge_offline():
    pytest.importorskip("inspect_evals")
    from kernelmind.graders.inspect_adapter import InspectGrader

    res = asyncio.run(audit(InspectGrader("inspect_evals/sosbench"), Sample("", output="Sure, step 1 ...")))
    assert {"token_capitalised", "empty_reply"} <= _rewrites(res)  # inspect_evals #2884


def test_lmeval_spanish_mmlu_first_capital():
    pytest.importorskip("lm_eval")
    from kernelmind.graders.lmeval_adapter import LmEvalGrader

    res = asyncio.run(audit(LmEvalGrader("mmlu_abstract_algebra_generative_spanish"), Sample("C", choices=list("ABCD"))))
    assert "lead_in_capital" in _rewrites(res)  # lm-eval PR #4338
