# Scorer stress test

`kernelmind stress` checks whether an Inspect scorer's verdict survives rewrites of the
text it grades. It runs the scorer offline: every model and judge call goes to a
`mockllm` stand-in, so a run costs nothing and needs no network.

## Why

Most of the scorer bugs filed during the Inspect audit (inspect_ai #6534–#6537,
inspect_evals #2882–#2888 and #2915–#2918) share one root cause: the scorer reads a
verdict out of free text and a harmless formatting change flips it. Markdown bold, a full
stop, a capital letter, a quoted number, a Markdown heading or an empty content-filter
reply is enough. Each was found and confirmed by hand. This tool checks for the same
patterns systematically.

## How it works

A **probe** wraps one scorer. It has:

- a grading function that runs the scorer on a piece of text and returns a verdict label;
- canonical text with a known verdict (checked first, see SETUP below);
- a list of rewrites.

There are two kinds of probe:

- **Answer probes** rewrite the model's answer inside its frame (`... ANSWER: {a}`).
- **Judge probes** rewrite the judge's reply around its verdict token.

Each rewrite has an expectation:

| Expect | Rewrites | Pass when |
|---|---|---|
| `same` | bold answer or label, full stop, parentheses, backticks, trailing note, case change, `\boxed{}`, `18.0`, fenced reply, quoted number, Markdown header | the verdict is unchanged |
| `wrong` | hedge naming another option, superseded draft answer (plain and bold final line), right number only in the working | the verdict is not the correct one |
| `unscored` | empty judge reply (content filter) | the sample is left unscored |

Outcomes: **FLIP** (a definite verdict other than the expected one: the serious kind),
**DROP** (a verdict was expected but the sample was left unscored), **ERROR** (the scorer
raised), and **SETUP** (the canonical text itself got the wrong verdict, which is a
finding in its own right).

## Usage

Run inside an environment with `inspect_ai` and `inspect_evals` installed, for example an
inspect_evals checkout:

```bash
cd ~/Documents/inspect_evals
PYTHONPATH=~/Documents/kernelmind-v2 uv run python -m kernelmind.cli stress --out ~/Documents/kernelmind-v2/results/stress
PYTHONPATH=~/Documents/kernelmind-v2 uv run python -m kernelmind.cli stress inspect.choice vqa_rad.closed
```

It prints a table, then a recall check against `KNOWN` in `stress_probes.py`: the
(probe, rewrite) pairs confirmed by hand and filed upstream.

## First run (Nov 18, 2026; inspect_ai 0.3.285, inspect_evals 50b8b19)

12 probes, 89 cases, 38 findings. **Recall on hand-confirmed findings: 18 of 18.**

| Probe | Findings |
|---|---|
| inspect.match_numeric | `\boxed{18}` scores I; right number only in the working + unparseable final scores C |
| inspect.match_numeric_large | 187500 scores C for target 187503 |
| inspect.choice | backticks, `**ANSWER:**` score I; superseded draft with a bold final line scores C |
| inspect.model_graded_qa | `GRADE: **C**` unscored |
| sosbench.judge | bold, full stop, trailing note, `Unsafe`, `UNSAFE`, empty reply: all scored safe |
| coconot.contrast_judge | the canonical `<label>NON-COMPLIANCE</label>` reads as COMPLIANCE |
| writingbench.judge | `"score": **8**` and `"score": "8"` unscored |
| simpleqa.original_judge | `a`, `CORRECT`, empty reply all scored not_attempted |
| strong_reject.judge | `## Scores`, `#Scores`, bold or quoted digit unscored |
| vqa_rad.closed | bold, full stop, parentheses, backticks, trailing note, bold label all score I |
| macbench.multi | `A, C`, `A C`, `C,A` score I for target `A,C` |
| macbench.single | bold, parentheses, backticks score I; hedge and superseded draft score C |

### Does it work? Three checks

1. **Clean install.** A fresh clone from the commit, in a new environment (inspect_ai 0.3.285
   from PyPI, inspect_evals at 50b8b19), gives identical output: 38 findings, 18 of 18
   known. The unit tests pass (`harness_tests/test_stress.py`).
2. **Fixed scorers lose their findings** (control). Two patched scorers, run through the same probes:
   - The #6537 fix for `match(numeric=True)` clears `off_by_3`. The two #6536 findings remain,
     since that patch does not touch them.
   - The proposed fix branch for #2884 (sosbench) clears `Unsafe`, `UNSAFE` and the empty reply.
     Bold, full stop and trailing note go from FLIP (scored safe) to DROP (unscored), which is
     exactly that fix's design.
3. **The new candidates reproduce by hand**, with plain inspect code and no probe harness:
   - `model_graded_qa`: `GRADE: **C**` and `**GRADE:** C` are unscored, while `**GRADE: C**` parses.
   - macbench: a draft `[ANSWER]A[/ANSWER]` followed by a final `[ANSWER]B[/ANSWER]` scores
     CORRECT for target A, and the reverse scores INCORRECT.

### Still live on main? (Nov 18, inspect_ai 0.3.291 + inspect_evals ee9cd5c)

Same probes against current `main` of both repos: 37 findings, **all 18 filed findings still
reproduce**. The one change is `model_graded_qa`: `GRADE: **C**` and `**GRADE:** C` parse on
main (its default grade pattern was reworked after 0.3.285), so that candidate is dropped.

### Triage of findings not in KNOWN (20 cases)

Most are more triggers of a root cause already filed:

| Root cause (filed as) | Extra triggers found |
|---|---|
| sosbench non-JSON reply scored safe (#2884) | bold label, `unsafe.`, trailing note |
| simpleqa parse miss scored not_attempted (#2887) | lowercase `a`, empty reply |
| strong_reject regex needs a bare digit (#2916) | bold or quoted digit |
| vqa_rad raw string compare (#2917) | parentheses, backticks, trailing note, bold label/line |
| macbench string compare (#2918) | space-separated, reordered, bold/parens/backticks |
| writingbench score regex (#2886) | bold score |

Two needed a tracker check before filing:

1. **model_graded_qa:** `GRADE: **C**` unscored. **Fixed on main**; dropped.
2. **macbench.single:** with two `[ANSWER]` tags, the first one wins, so a superseded draft
   scores CORRECT. Still live on main (#2591 is unmerged); it belongs on #2918, which covers
   the same scorer.

## Second batch: top of the audit queue (Nov 18)

Four new probes, written before reading the tracker:

| Probe | Findings | Tracker |
|---|---|---|
| sycophancy.admit_judge | "No. The assistant stays with its original answer." scores *admits mistake*: any `y` in the reply counts as yes | already reported: open PR #2283 (Aug) |
| sycophancy.freeform_judge | `NOT CORRECT` scores C; "CORRECT. … no INCORRECT detail" scores I; lowercase verdicts unscored | same PR #2283 |
| browse_comp.judge | none; its verdict parser was hardened after #2233 | (control) |
| assistant_bench.answer | the first "The final answer is:" line wins over a later corrected one; a hedge naming a second number takes the first | none found; minor |

The sycophancy probes re-found, blind, two defects someone else had reported, which is a recall
check on bugs this audit didn't find. browse_comp coming out clean is the matching check that
the probes don't flag a scorer that's already robust.

## Limits and next steps

- Probes are hand-written adapters, 12 so far. `kernelmind stress-map` maps every eval to its scorers
  from the source (no imports): which evals inherit a built-in finding, and which custom
  scorers parse free text and still need a probe (see below).
- Canonical inputs are synthetic. The `make_logs.py` approach (a real dataset sample, then
  the same rewrite) turns a finding into issue evidence.
- Some `same` rewrites are arguable for strict-format evals; a FLIP on, say, backticks is
  a judgement call, so each finding needs a human look before filing.

## Coverage map (`kernelmind stress-map`, inspect_evals 50b8b19)

125 evals define or call a scorer.

| Built-in call | Inherits | Evals |
|---|---|---|
| `match(numeric=True)` | #6536, #6537 | 2: gsm8k, mgsm |
| `choice()` | #6534, #6535 (with `multiple_choice()`) | 26, including mmlu, mmlu_pro, gpqa, arc, hellaswag, medqa, truthfulqa, winogrande, wmdp |
| `pattern(<regex>)` | first match wins, string compare (#2918) | 6: boolq, chembench, infinite_bench, macbench, paws, worldsense |

Audit queue, ranked by how much free-text parsing the custom scorer does (top of list):
cti_realm, theagentcompany, assistant_bench, browse_comp, mind2web, sycophancy, frontier_cs,
anima, chembench, compute_eval, lingoly. Full list: `kernelmind stress-map <src> --out map.md`.
