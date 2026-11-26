# Grader audit: point it at any grader

`kernelmind grader-audit` checks whether a grader's verdict survives rewrites that keep the
meaning of a model's answer, and whether it rejects near misses. It treats the grader as a
black box: the same audit runs on an Inspect scorer, an lm-evaluation-harness filter and
metric, a Python function or a command-line script. No datasets, API keys or network are
needed; LLM-judge calls are replayed offline.

```bash
kernelmind grader-audit --grader inspect:inspect_evals/gsm8k --target 18
kernelmind grader-audit --grader lmeval:mmlu_pro_biology --target C --choices "A|B|C|D|E|F|G|H|I|J"
kernelmind grader-audit --grader python:my_scorer.py:grade --target 18
kernelmind grader-audit --grader "cmd:./grade.sh {target}" --target 18      # output on stdin
kernelmind grader-audit --log run.eval                                      # a log's own scorer and samples
kernelmind grader-sweep lmeval --out results/graders/lmeval                 # every grader, ranked
```

Inspect and lm-eval graders need those packages installed in the environment you run from.

## How it works

**Answer graders** (the grader reads the model's output):

1. *Which formats does it read?* The correct answer and a wrong one are written in a dozen
   common formats (`ANSWER: X`, `The answer is (X).`, `#### X`, `\boxed{X}`, a bare answer...),
   each bare and after a line of reasoning. A format is *read* when the two get different
   verdicts. This replaces the hand-written adapters of `kernelmind stress`.
2. *Rewrites in each read format.* Meaning kept (bold, a full stop, parentheses, backticks, a
   trailing note, a bold label, `\boxed{}`, `18.0`, a lead-in sentence whose first word starts
   with another option's letter): the verdict must not change. Near misses (a superseded draft,
   a hedge naming another option, the right number only in the working, off by 3): the verdict
   must not be the correct one.

**Judge graders** (the grader asks an LLM and parses its reply): every model call is
intercepted and answered with a scripted reply. Candidate replies come from the judge prompt
itself: its verdict words, JSON keys, XML tags, `GRADE:` lines and any output format it spells
out with `<placeholders>`. Replies that get different verdicts are canonical; their rewrites
(bold or quoted token, a full stop, a capital letter, a code fence, a trailing note, a Markdown
header, `NOT_ATTEMPTED` written `NOT ATTEMPTED`, an empty content-filter reply) must keep the
verdict. Two checks need no canonical reply: verdict words that contain one another must not
collapse into one verdict, and a verdict word the prompt asks for must not read as "unknown".

Outcomes: FLIP (a definite wrong verdict), DROP (unscored where a verdict was due), ERROR.
Graders that read none of the formats are reported as `NOFORMAT`, not guessed at.

## Does it work? (Nov 20, 2026)

**Recall without per-grader code.** Each known bug is audited by pointing the tool at the grader
it lives in, nothing else (`kernelmind grader-audit --recall all`):

| Set | Re-found |
|---|---|
| Our hand-confirmed Inspect findings (inspect_ai #6534–#6537, inspect_evals #2883–#2887, #2916–#2918) | 17 / 17 |
| lm-eval bugs reported by others (MMLU-Pro first match #3110/#4417, Spanish MMLU-Redux #4338, TurkishMMLU CoT #4339) | 3 / 3 |
| A scorer known to be robust (browse_comp, hardened after #2233) | clean |

Caveat: the rewrite families were extended while building the tool (off by 3, the lead-in
sentence, separator spellings, unread verdict words, multi-slot formats), after seeing which
known bugs the first version missed. So this is recall on bugs the tool was tuned against;
the sweep below is the test on graders it was not tuned for.

**Sweeps.** No datasets are downloaded, so each grader is audited on synthetic samples (the
first of: a letter with options, a number, a word, that it reads).

- *lm-eval* (d6de816): 4,790 generative task pipelines; the 2,739 that extract an answer
  (rather than compare the whole output, as QA and translation tasks do) fall into 127
  distinct configurations. 48 audited, 70 read none of the synthetic formats, 9 skipped.
- *inspect_evals* (50b8b19, inspect_ai 0.3.285): 250 tasks. 73 audited, 163 read none of the
  synthetic formats (agent tasks, judges that need real sample metadata), 14 timed out.
  39 tasks show the #6534/#6535 pattern (backticks, bold label, superseded draft), in line with
  the static map's 26 `choice()` evals, several of which define more than one task.

Rankings: `results/graders/` (local). Every flagged grader needs a human look before filing:
some "same" rewrites are judgement calls for strict-format tasks.

## Pointing at a grader's own source file (Nov 26)

The `python:` adapter now takes a grader straight from the repository it lives in, with no wrapper:

```bash
kernelmind grader-audit --grader python:verl/verl/utils/reward_score/math_dapo.py:compute_score --target 18
kernelmind grader-audit --grader "python:verl/verl/utils/reward_score/gsm8k.py:compute_score?method=\"flexible\"" --target 18
kernelmind grader-audit --grader python:open-instruct/open_instruct/ground_truth_utils.py:GSM8KVerifier --target 18
kernelmind grader-audit --grader python:trl/trl/rewards/accuracy_rewards.py:_grade --target '\frac{3}{4}'
kernelmind grader-audit --grader "python:opencompass/opencompass/utils/text_postprocessors.py:first_option_postprocess?options=\"ABCD\"" \
  --target C --choices "A|B|C|D"
```

- **Loading.** The file is imported on its own: its package `__init__` files are skipped (they usually import a
  trainer, torch or a registry), sibling modules still import, and a dependency that is not installed, or a sibling
  module that fails to import, is replaced by a stub and named on stderr. A stub can hide a dependency the grader
  really uses: if the result is `NOFORMAT` or an error, install that dependency.
- **Calling.** Arguments are matched by name: the output goes to `solution_str`, `prediction`, `response`,
  `completion`, `content`... and the target to `ground_truth`, `label`, `answer`, `solution`... TRL-style batch
  rewards (`completions`, a list of chat messages) are called with one completion. A class is instantiated and
  called (open-instruct verifiers). `?k=v` fixes other arguments (values are JSON when they parse as JSON).
- **Verdict.** Taken from a `score`/`reward`/`acc` key, a `.score` attribute, or the first item of a
  `(correct, prediction)` pair. A function with no target argument is treated as an **extractor** (a postprocessor or
  answer parser): its result is compared to the target as text or as a number.
- **Commands** can take the output as an argument too: `cmd:python verify.py {target} "$(cat)"`.
- **`--frame '#### {a}'`** tries the task's own output format first. Discovery keeps the first three formats a
  grader reads; a grader that reads the whole text "reads" `ANSWER: 18` and a bare `18` too, so its own `####`
  format may not make the cut. Without `--frame`, Prime's GSM8K check showed only minor flags; with it, the bold
  final answer.

**Shot at (Nov 26), no per-grader code** (latest `main` of each; every flag checked by hand and against the
project's tracker):

| Grader | Result |
|---|---|
| veRL `math_dapo` (default for math/AIME data) | bold, full stop, whole-line bold, draft credit: already reported (veRL #8449, open PR #8450) |
| veRL `gsm8k` strict | bold final answer skipped, so a withdrawn draft is rewarded: fixed in [verl-project/verl#8814](https://github.com/verl-project/verl/pull/8814) |
| SkyRL `gsm8k` env (a copy of an older veRL scorer) | the **first** `#### N` is scored, so a withdrawn draft is rewarded and the correction gets 0, even without formatting; same formatting gaps as veRL. Fix PR prepared |
| SkyRL `aime` env (a copy of an older `math_dapo`) | the markdown gaps veRL has since fixed or is fixing |
| OpenCompass `first_option_postprocess` | `ANSWER: **C**` read as `A` (from "Answer"): already reported (OpenCompass #2725, PR #2726) |
| Prime Intellect `verifiers` `parse_judge_choice` (ReferenceJudge) | the last yes/no word wins: "Yes ... no discrepancies" reads as no. Already reported (#2737, PR #2774) |
| Prime Intellect `verifiers` GSM8K `verify.py` (with `--frame '#### {a}'`) | `#### **18**`, `` #### `18` `` and `#### 18.` score 0: open PR #2840 already changes this grader |
| open-instruct `GSM8KVerifier` | clean (last number, compared as a number) |
| TRL `accuracy_reward` grading | clean apart from the hedge |
| verifiers `verify_boxed_math_answer` | clean |

Not run: open-instruct `MathVerifier`/`StrictMathVerifier` (sympy LaTeX parsing needs `antlr4-python3-runtime==4.11`),
rllm math reward (needs `rllm[rewards]`), Qwen2.5-Math. NeMo-Skills: only its extractor was reachable without a
wrapper (its grader is extractor + `math_equal`).

Lesson from this batch: graders are copied between RL libraries and the copies drift. The SkyRL bug is one veRL fixed
in June 2025; the copy never got the fix.

## Graders that read meaning: negation and dates (Nov 23)

Some checks don't extract an answer; they decide what text *means*: does a sentence claim an
action happened, does a quote support a month. Two rewrite families cover the common ones,
chosen by the target and discovered the same way as formats:

- **Negation** (target is a predicate, e.g. `--target processed`): runs only if the grader gives
  "The request was processed." and "...was not processed." different verdicts. Rewrites that must
  read as the negative: `wasn't`, `hasn't been`, a negation four words back ("has not yet been fully
  processed"), "never", "not yet". Rewrites that must read as the positive: a "no-" compound
  ("No-fee request processed."), a negation in another clause, a negation after the verb.
- **Dates** (target is a month, e.g. `--target 2026-09`): runs only if the grader gives the target
  month and the next month different verdicts. The same month in nine formats (`Sep 2026`,
  `2026-09-15`, `09/2026`, `15/09/2026`, `15.09.2026`, `09/15/2026`, `15 September 2026`,
  `September 15, 2026`, a day-first range) must keep the verdict; the next month must not; and
  words that look like month names ("rates *may* change", "staff will *march*") must not count as
  May or March.

Validated on an open-source agent company's eval harness (findings not yet reported, so not
named here): pointed at two of its deterministic checks with no extra code, the families re-found
both bugs (contractions and distant negation read as claims; `09/2026`, day-first and dotted dates
missed) and both lenient cases ("no-" compounds negate; "may" and "march" count as months). Unit
tests use generic bug-pattern graders and robust twins: the buggy ones are caught, the robust ones
come back clean, and all earlier recall sets still pass (17/17, 3/3).

## A grader outside both frameworks: Math-Verify (Nov 20)

[Math-Verify](https://github.com/huggingface/Math-Verify) (Hugging Face, 0.9.0) checks math
answers for lighteval, the Open LLM Leaderboard and many RL training rewards. It is a plain
library, so it is audited through the `python:` adapter with a three-line wrapper per way it is
used (`examples/graders/math_verify_graders.py`): its default `parse()`, and the accuracy reward
in open-r1's GRPO recipe.

```bash
kernelmind grader-audit --grader python:examples/graders/math_verify_graders.py:default --target 18
kernelmind grader-audit --grader python:examples/graders/math_verify_graders.py:openr1_reward --target '\frac{3}{4}'
```

| Use | Target | Flagged |
|---|---|---|
| default `parse()` | 18 | `ANSWER: (18)` and `` ANSWER: `18` `` parse to nothing (scored wrong); a hedge (`18, though 129 is also plausible`) and a superseded draft are scored right |
| default `parse()` | `\frac{3}{4}` | the hedge |
| open-r1 reward | 18 | nothing (only `\boxed{}` is read, and decoration around the box is handled) |
| open-r1 reward | `\frac{3}{4}` | the hedge |

Re-run on Math-Verify's latest `main` (ba3d3aa) across six answer types (18, -7, 0.25,
`\frac{3}{4}`, `\sqrt{2}`, `2\pi`): the same pattern for every plain number. The superseded-draft
finding has a clear cause: a bold final answer (`ANSWER: **129**`) is extracted as the string
`129**`, which does not parse, so an *earlier* number in the response (a draft answer the model
withdrew) becomes the value. A response that writes 18, says it was wrong, then gives a bold
129 is scored correct for 18. Without an earlier number, `**129**` parses fine. The open-r1
reward (boxed answers only) is not affected.

Found by hand while checking these: two boxed answers, `\boxed{18} or \boxed{129}`, parse as
the number 18129 (the reverse order gives the set {18, 129}). None of these is in Math-Verify's
tracker as of Nov 20. The others are not confirmed as bugs (a hedge taking the first value may be by design).

**Confirmed and fixed upstream (Nov 20).** The bold-answer bug comes from the plain-expression regex
treating `*` as an operator, so `129**` matches as an expression and fails to parse. lighteval carries
its own copy of the same regex: with `any_match` it gives the same false credit, and with `first_match`
(its Inspect `math_scorer`) even a lone `ANSWER: **129**` comes back as the string `129**` and is scored
wrong. The fix in both: a plain expression must end with a digit or a closing parenthesis.

| PR | New tests | Suite |
|---|---|---|
| [huggingface/Math-Verify#103](https://github.com/huggingface/Math-Verify/pull/103) | 15 (10 fail before) | 306 pass |
| [huggingface/lighteval#1522](https://github.com/huggingface/lighteval/pull/1522) | 10 (8 fail before) | 243 pass in `test_extractive_match.py` (PyTorch stubbed) |

Re-auditing the patched Math-Verify: the superseded-draft findings disappear; the others remain.

Running Math-Verify also exposed three weaknesses in the audit itself, now fixed: case changes
were applied to LaTeX (`\Frac`), decorations were put inside `\boxed{}` instead of around it, and a
decimal's trailing zero was written `0.25.0`.

## Limits

- Text graders only. Verifiers that check a container's final state (Terminal-Bench) need
  state rewrites, which `kernelmind audit` covers by hand-built near-miss solutions instead.
- It shows a grader *can* break, not how often; `kernelmind rescore` on real logs measures that.
- For LLM judges it tests how the reply is read, not whether the judgement is right.
- Synthetic samples miss scorers that read sample metadata; point `--log` at a real log for those.
