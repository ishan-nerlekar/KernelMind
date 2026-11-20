"""Recall sets: bugs confirmed by hand (ours, or reported by others), and how to point the
audit at the grader each one lives in. Nothing here tells the audit what to look for; it
only says which grader and which sample to audit, and what a correct audit must find.

Inspect logs come from make_logs.py runs (real dataset samples); pass their directory.
"""

from __future__ import annotations

from pathlib import Path

from .core import Sample

# grader name -> rewrites (or rewrite prefixes) a correct audit must flag
KNOWN_INSPECT: dict[str, set[str]] = {
    "inspect:inspect_evals/gsm8k": {"boxed", "reasoning_number_unparseable_final"},  # inspect_ai #6536
    "inspect:inspect_evals/gsm8k#large": {"off_by_3"},  # inspect_ai #6537
    "inspect:inspect_evals/gpqa_diamond": {"superseded_draft_bold_line", "bold_label", "backticks"},  # #6534, #6535
    "inspect:inspect_evals/sosbench": {"token_capitalised", "token_upper", "empty_reply"},  # inspect_evals #2884
    "inspect:inspect_evals/coconot": {"token_separator_hyphen"},  # #2883: NON-COMPLIANCE reads as COMPLIANCE
    "inspect:inspect_evals/writingbench": {"token_quoted"},  # #2886
    "inspect:inspect_evals/simpleqa_verified": {"unread_verdict_word:CORRECT"},  # #2887
    "inspect:inspect_evals/strong_reject": {"header_markdown", "header_capitalised"},  # #2916
    "inspect:inspect_evals/vqa_rad": {"trailing_period", "bold_answer"},  # #2917
    "inspect:inspect_evals/macbench": {"hedge"},  # #2918
}
CLEAN_INSPECT = {"inspect:inspect_evals/browse_comp"}  # hardened after #2233: should come back clean

# lm-eval bugs reported by other people (open PRs/issues), not used to design the rewrites
KNOWN_LMEVAL: dict[str, set[str]] = {
    "lmeval:mmlu_pro_biology@custom-extract": {"superseded_draft"},  # first "answer is" wins (#3110/#4417)
    "lmeval:mmlu_abstract_algebra_generative_spanish@default": {"lead_in_capital"},  # first capital A-D (#4338)
    "lmeval:turkishmmlu_cot_biology@get-choice": {"lead_in_capital"},  # first capital A-E in the CoT (#4339)
}


def inspect_targets(log_dir: str | None):
    """[(grader, sample)] for the Inspect recall set."""
    from .inspect_adapter import InspectGrader, grader_from_log

    out = [
        (InspectGrader("inspect_evals/gsm8k"), Sample("18", input="Janet has ducks...")),
        (_renamed(InspectGrader("inspect_evals/gsm8k"), "#large"), Sample("187503", input="How many...")),
        (InspectGrader("inspect_evals/gpqa_diamond"),
         Sample("C", choices=["Argon", "Neon", "Nitrogen", "Krypton"], input="Which is NOT a noble gas?")),
        (InspectGrader("inspect_evals/browse_comp"),
         Sample("1988", input="In what year...?", output="Explanation: ... Exact Answer: 1988")),
    ]
    if log_dir:
        for p in sorted(Path(log_dir).glob("*/*.eval")):
            g, samples = grader_from_log(str(p))
            out += [(g, s) for s in samples]
    return out


def _renamed(g, suffix: str):
    g.name += suffix
    return g


def lmeval_targets():
    from .lmeval_adapter import LmEvalGrader

    ten, four, five = list("ABCDEFGHIJ"), list("ABCD"), list("ABCDE")
    return [
        (LmEvalGrader("mmlu_pro_biology"), Sample("C", choices=ten)),
        (LmEvalGrader("mmlu_abstract_algebra_generative_spanish"), Sample("C", choices=four)),
        (LmEvalGrader("turkishmmlu_cot_biology@get-choice"), Sample("C", choices=five)),
    ]
