# What breaks in the graders behind AI evals and RL rewards

*Ishan Nerlekar · November 2026 · tool: [KernelMind](../README.md) `grader-audit` and `audit`*

Every benchmark score and every RL reward passes through a grader: a regex, a normaliser, an LLM judge or a test
suite that turns a model's output into a verdict. If the grader misreads a correct answer, the model is scored as
wrong; if it accepts a wrong one, the model is credited for it. Training pays for the misreading too. I built a tool
that points at any grader and checks whether its verdict survives rewrites that keep the answer's meaning, then
pointed it at the graders of 15 evaluation and RL libraries.

**As of November 26, 2026:**

- **36 issues and 12 open pull requests** filed in 9 projects (Inspect, inspect_evals, Terminal-Bench 2 and 4,
  Hugging Face Math-Verify and lighteval, veRL, SkyRL, GitNexus), from these audits by hand and with the tool. Every
  finding was reproduced on the project's current code and checked against its tracker before filing. No PR is merged
  yet; the oldest are three weeks old. veRL's maintainers closed both veRL PRs (#8814, #8859) without comment, the same
  day they closed many other outside PRs.
- **No per-grader code.** The tool works out which output formats a grader reads, so one command audits an Inspect
  scorer, an lm-evaluation-harness task, a function in an RL library or a command-line script.
- **It finds known bugs it was not told about:** 17/17 hand-confirmed Inspect findings and 3/3 lm-eval bugs that other
  people reported. A scorer known to be fixed comes back clean.

## Five patterns

**1. The draft answer gets the credit.** Models write an answer, notice a mistake and write a different final answer.
Several graders score the first one, or skip a formatted final answer and fall back to the draft:

| Grader | Response | Scored |
|---|---|---|
| Inspect `multiple_choice` ([#6534](https://github.com/UKGovernmentBEIS/inspect_ai/issues/6534)) | `ANSWER: B` … `**ANSWER: C**` | B |
| Math-Verify `parse()` ([PR #103](https://github.com/huggingface/Math-Verify/pull/103)), same code in lighteval ([PR #1522](https://github.com/huggingface/lighteval/pull/1522)) | `ANSWER: 18` / `Wait, I made an error.` / `ANSWER: **129**` | 18 |
| veRL GSM8K reward ([PR #8814](https://github.com/verl-project/verl/pull/8814), closed without comment) | `#### 18` / `Wait, I made an error.` / `#### **129**` | reward 1 for 18 |
| SkyRL GSM8K env ([PR #2826](https://github.com/skyrl-project/SkyRL/pull/2826)) | `#### 18` / `Wait, I made an error.` / `#### 129` | reward 1 for 18 |

In the last two, an RL run pays full reward for an answer the model withdrew. In Math-Verify, `*` is an operator in
the plain-expression regex, so `129**` matches as an expression, fails to parse, and the earlier number wins.

**2. Ordinary formatting turns a right answer wrong.** `**ANSWER:** C`, `` ANSWER: `C` ``, `ANSWER: (C) Paris`
(Inspect [#6535](https://github.com/UKGovernmentBEIS/inspect_ai/issues/6535)), `#### 18.`, `#### $18`, `ANSWER: Yes.`
(inspect_evals vqa_rad [#2917](https://github.com/UKGovernmentBEIS/inspect_evals/issues/2917)). Real effect, measured
by another contributor on #6535 ([comment](https://github.com/UKGovernmentBEIS/inspect_ai/issues/6535#issuecomment-7093236531)):
on wmdp_bio, a model that wrote `ANSWER: $B` (copying the prompt's `$LETTER`) in 838 of 1,273 replies was logged at
**27.0%** accuracy; reading the `$` as formatting gives **85.3%** on the same replies.

**3. ASCII-only normalisation.** Most QA graders copy SQuAD's normaliser, which removes `string.punctuation`. That
set is ASCII only, so curly quotes and dashes survive: `O’Neill` does not match `O'Neill`, `1914–1918` does not match
`1914-1918` (exact match 0, F1 0.0). Found in Inspect `exact()`/`f1()` (used by inspect_evals squad, drop,
infinite_bench; [#6798](https://github.com/UKGovernmentBEIS/inspect_ai/issues/6798)), veRL's Search-R1 exact match
(the default for its seven `searchR1_*` datasets; [PR #8859](https://github.com/verl-project/verl/pull/8859), closed by a maintainer without comment), SkyRL's
search env ([PR #2827](https://github.com/skyrl-project/SkyRL/pull/2827)) and open-instruct's string verifiers.
How often it can bite, counted on the dev sets ([script](../scripts/typographic_gold_answers.py)): questions where
**every** gold answer contains such a character, so a model that types the ASCII form cannot get exact-match credit:

| Dev set | Questions affected | Typical gold answers |
|---|---|---|
| SQuAD v1.1 | 82 / 10,570 (0.78%) | `24–10`, `1568–1609`, `Cobham–Edmonds thesis` |
| SQuAD v2 (inspect_evals squad) | 40 / 5,928 answerable (0.67%) | `Mexico–United States border`, `£15–100,000` |
| Natural Questions open (Search-R1's NQ) | 23 / 3,610 (0.64%) | `1979–80 season`, `1951–52` |
| HotpotQA distractor | 36 / 7,405 (0.49%) | `13–3`, `Trenton–Mercer Airport` |
| DROP (inspect_evals drop) | 10 / 9,535 (0.10%) | `2004–05` |
| TriviaQA rc.nocontext | 4 / 17,944 (0.02%); 703 (3.9%) have such a character in at least one alias | `Scooby-Doo’s` |

Almost all are en dashes in scores, seasons and ranges. This is a ceiling, not a measured loss: a model that copies
the dash from a given passage (SQuAD) loses nothing, while one answering from memory (NQ, HotpotQA) is likely to type
`-`.

**4. LLM-judge replies misread.** The judge says one thing, the parser reads another:
`<label>NON-COMPLIANCE</label>` read as COMPLIANCE because one word contains the other (coconot
[#2883](https://github.com/UKGovernmentBEIS/inspect_evals/issues/2883)); `{"label": "Unsafe"}` scored as safe because of
the capital letter (sosbench [#2884](https://github.com/UKGovernmentBEIS/inspect_evals/issues/2884)); `"score": "8"` as a
string dropped (writingbench [#2886](https://github.com/UKGovernmentBEIS/inspect_evals/issues/2886)); `## Scores`
instead of the expected header leaves the sample unscored (strong_reject
[#2916](https://github.com/UKGovernmentBEIS/inspect_evals/issues/2916)); the exact verdict word the prompt asks for read
as "not attempted" (simpleqa_verified [#2887](https://github.com/UKGovernmentBEIS/inspect_evals/issues/2887)). The
tool audits these offline: every model call is answered with scripted replies mined from the judge's own prompt.

**5. Copies drift.** RL libraries copy each other's reward functions. SkyRL's GSM8K env is a copy of veRL's scorer
from before veRL switched to the last answer in June 2025 (veRL #1630); the copy never got the fix. SkyRL's AIME env
is likewise an older copy of veRL's `math_dapo`, behind veRL's markdown fixes. A tool that can point at any file finds
the copies quickly.

**Container verifiers too.** The same idea with whole solutions instead of answer rewrites (`kernelmind audit`):
near-miss solutions that each break one requirement of the task. 12 of 26 Terminal-Bench 2.0 tasks accept a solution
that is wrong by the task's own words (a Coq "proof" that assumes the theorem as an axiom, a training step with no
backward pass; [#92–#103](https://github.com/harbor-framework/terminal-bench-2/issues/92)), and 8 Terminal-Bench 4.0
tasks were filed ([#2730–#2737](https://github.com/harbor-framework/terminal-bench/issues/2730)), with test fixes as PRs.
Details: [REPORT.md](REPORT.md).

**Agent benchmarks' hidden tests.** GitNexus grades its own coding-agent benchmark with hidden tests. The `list_repos`
task asks for a filter on the repository name, but every test repository's path contains its name, so a filter on the
path passed. Fix with a new control that requires the path filter to fail:
[PR #4154](https://github.com/abhigyanpatwari/GitNexus/pull/4154).

## How the tool works

```bash
kernelmind grader-audit --grader inspect:inspect_evals/gpqa_diamond --target C --choices "A|B|C|D"
kernelmind grader-audit --grader lmeval:mmlu_pro_biology --target C --choices "A|B|C|D|E|F|G|H|I|J"
kernelmind grader-audit --grader python:verl/verl/utils/reward_score/math_dapo.py:compute_score --target 18
kernelmind grader-audit --grader "cmd:./grade.sh {target}" --target 18
```

1. **Discover the format.** The correct answer and a wrong one are written in about a dozen common output formats.
   A format is *read* when the two get different verdicts. If none is read, the result is `NOFORMAT`, never a guess.
2. **Rewrite.** In each read format: changes that keep the meaning (bold, a full stop, parentheses, backticks, a
   trailing note, `\boxed{}`, `18.0`, curly quotes, an en dash, a negation spelled `wasn't`, a date written
   `15/09/2026`) must keep the verdict. Near misses (a superseded draft, a hedge naming another answer, off by 3, the
   next month) must not get credit.
3. **Judges offline.** For LLM-judge graders every model call is intercepted. Candidate replies come from the judge
   prompt: its verdict words, JSON keys, XML tags and any output template it spells out.
4. **Any grader.** Adapters for Inspect, lm-evaluation-harness, any Python function (loaded from its own source file,
   arguments matched by name) and any command.

Details and every flag per grader: [GRADERS.md](GRADERS.md).

## How much to trust it

- **Recall on known bugs:** 17/17 of my Inspect findings and 3/3 lm-eval bugs reported by others (MMLU-Pro first
  match, Spanish MMLU-Redux, TurkishMMLU), re-found by pointing the tool at the grader and nothing else.
- **Controls:** a scorer hardened after an earlier report (browse_comp) comes back clean. Against my #6535 fix branch,
  GPQA loses exactly the #6535 findings and keeps the #6534 one. open-instruct's GSM8K verifier comes back clean, and
  TRL's accuracy reward is clean apart from a hedge.
- **Caveat:** several rewrite types were added after the first version missed known bugs, so the recall numbers are
  on bugs the tool was tuned against. The fairer test is graders it was never tuned on: Math-Verify, veRL, SkyRL and
  the ASCII-only normalisers were all found that way.
- **Every flag gets a human look** before anything is filed. Some "same meaning" rewrites are fair to reject on a
  task that asks for a strict format; those are not filed.

## Limits

- It shows a grader *can* misread an answer, not how often real models trigger it. Where real outputs were available,
  they were checked (the wmdp_bio numbers above are another contributor's measurement); most findings are not yet
  measured on real runs.
- For LLM judges it tests how the reply is parsed, not whether the judge's judgement is right.
- Text graders only. Container-state verifiers need whole near-miss solutions, which `kernelmind audit` builds per task.

## Reproduce

```bash
git clone https://github.com/ishan-nerlekar/KernelMind && cd KernelMind
pip install -e .                       # plus inspect_ai / inspect_evals / lm-eval for those adapters
python -m kernelmind.cli grader-audit --recall all --logs <make_logs.py output>   # the recall sets
python -m kernelmind.cli grader-sweep inspect --out results/graders/inspect          # every Inspect task, ranked
```
