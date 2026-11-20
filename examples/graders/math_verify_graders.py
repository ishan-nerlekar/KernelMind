"""math-verify used two common ways, as plain grader functions (output, target) -> bool."""
from math_verify import LatexExtractionConfig, parse, verify
from latex2sympy2_extended import NormalizationConfig


def default(output, target):
    """parse() with its default extraction (LaTeX + plain expressions), first match."""
    return bool(verify(parse(f"${target}$"), parse(output)))


def openr1_reward(output, target):
    """The accuracy reward in Hugging Face open-r1 (GRPO training): boxed-first LaTeX extraction."""
    gold = parse(f"${target}$", extraction_mode="first_match")
    ans = parse(output, extraction_config=[LatexExtractionConfig(
        normalization_config=NormalizationConfig(nits=False, malformed_operators=False, basic_latex=True,
                                                 equations=True, boxed="all", units=True),
        boxed_match_priority=0, try_extract_without_anchor=False)], extraction_mode="first_match")
    return bool(verify(gold, ans))
