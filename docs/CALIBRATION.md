# Calibration log

Tier is set by measurement (SPEC.md rule 3): every new task gets one attempt from each calibration
probe (Claude Haiku 5.5, GPT-6 Luna; both off the leaderboard). If both probes solve it, it is Tier 1.

## 2026-11-05 · first Go batch (8 tasks designed as Tier 2)

| Task | GPT-6 Luna | Claude Haiku 5.5 | Commands used (Luna / Haiku) |
|---|---|---|---|
| config-override-precedence | pass, 41 s | pass, 18 s | 8 / 6 |
| lease-renew-gateway | pass, 41 s | pass, 20 s | 8 / 7 |
| neigh-roam-flush | pass, 71 s | pass, 23 s | 9 / 6 |
| peer-timeout-flap | pass, 81 s | pass, 33 s | 10 / 8 |
| radio-monitor-capability | pass, 72 s | pass, 31 s | 11 / 8 |
| rate-counter-wrap | pass, 39 s | pass, 21 s | 7 / 5 |
| seq-wraparound | pass, 83 s | pass, 33 s | 11 / 9 |
| ssid-dva-global-vlans | pass, 41 s | pass, 29 s | 8 / 8 |

Total cost $0.06. **Result: all 8 relabeled Tier 1.**

**Why they were easy (from the trajectories):** every attempt searched for a word from the report
(`gateway`, `dva`, `monitor`, `isolation`, `neigh`, `rate`, `stale`), opened the one file that matched,
and edited the faulty line. Three properties made that work: report vocabulary equals code
identifiers; a 2,000-line codebase; single-site bugs readable in one file.

**Next:** test hardening levers separately on prototypes (lexical-cue removal, runtime-only
concurrency, multi-hop symptom), measure each with the probes, then build with what works.

## 2026-11-05 · hardening experiments

| Task | Lever | GPT-6 Luna | Claude Haiku 5.5 |
|---|---|---|---|
| x-lease-oblique | A: report in operator language, no code words | pass, 42 s, 11 cmds | pass, 25 s, 9 cmds |
| x-push-lost-update | C: runtime-only concurrency bug | pass, 132 s, 14 cmds | pass, 58 s, 9 cmds |
| frame-partial-read | multi-hop (symptom in controller, cause in agent) | pass, 80 s | pass, 44 s |

Total cost $0.04. **No lever worked on its own.**

**Why:** the models translate operator language into code concepts unaided ("router" → gateway,
"name server" → DNS), and apnet has ~1,300 lines of non-test code, so they read every relevant file
in two or three commands. The concurrency bug was spotted by reading `agent.go` top to bottom; no
reproduction was needed. **The binding constraint is codebase size: when reading everything is
cheap, localization (the hard part of debugging) disappears.**

**Decision:** build Tier 2/3 on a large real networking codebase where reading everything is
impossible, and keep apnet's tasks as Tier 1. Candidate: GoBGP (BGP daemon, ~113k lines of non-test Go).

## 2026-11-05 · first GoBGP tasks (upstream mutations)

| Task | GPT-6 Luna | Claude Haiku 5.5 |
|---|---|---|
| bgp-implicit-withdraw | pass, 126 s, 11 cmds | pass, 962 s, 28 cmds |
| bgp-bestpath-med-order | pass, 152 s, 15 cmds | pass, 116 s, 14 cmds |

Size slowed the probes down (2–16 minutes instead of under 1) but didn't stop them. In a protocol
implementation the operator's vocabulary is the code's vocabulary (`NextHop`, `Withdraw`, `MED`), and
both bugs break textbook BGP rules, so they're obvious once found. Relabeled Tier 1.

**Novelty concern (raised by Ishan):** both bugs are deviations from public upstream code, so a model
can "fix" them by recalling GoBGP rather than by debugging. Tagged `origin = "upstream-mutation"`.

**Decision:** transplant the real production incidents into GoBGP as *new feature code* (origin
`incident-transplant`): the scenario is unique, the buggy code isn't upstream so it can't be recalled,
and the surrounding codebase is large. Evidence (logs, captures) ships with each task. Separately, a
small private set built from the real proprietary code fragments, never published.

## 2026-11-05 · first transplants

| Task | GPT-6 Luna | Claude Haiku 5.5 |
|---|---|---|
| bgp-rtr-no-data | pass, 128 s, 11 cmds | pass, 89 s, 7 cmds |
| bgp-extended-message | pass, 178 s, 18 cmds | pass, 242 s, 12 cmds |

Both probes went log → `grep "4096|message length|extended"` → the new feature file → the wrong
constant. **New feature code is a beacon:** the symptom's vocabulary greps straight into it, and once
there the bug is in plain sight. The surrounding 95k lines never had to be read. Relabeled Tier 1.

**Next experiment (decoy):** the code the symptom greps into is *correct*; the fault is an omission in
shared plumbing that never mentions the symptom's vocabulary, so grep can't find it and the agent has to
follow the data flow.

## 2026-11-05 · decoy experiment

| Task | GPT-6 Luna | Claude Haiku 5.5 |
|---|---|---|
| bgp-legacy-missing-routes | pass, 172 s, 14 cmds | pass, 169 s, 19 cmds |

The decoy (correct extended-message code that the capability evidence points at) cost neither probe
anything. Both read every debug file first, then searched for *every* noun in the evidence at once
(`ExtendedMessage|MaxMessage|LargeCommunity|CreateUpdateMsgFromPaths`), so the tagging code was in
view by command 4–6. Both reasoned out the ordering bug without help; Haiku wrote a reproduction test
first, then restructured the packer (a fix we didn't anticipate, which the hidden tests accepted).

**Conclusion after 6 rounds (16 tasks, ~$0.30 total):** single-fault bugs with static evidence are
solved by the cheapest current models in 2–5 minutes, whatever the codebase size, novelty, missing
text clues, or decoys. They search for every term in the evidence at once, so hiding one route to the
bug doesn't help when another term leads there.

## 2026-11-05 · next experiment: two faults, live reproduction (bgp-agg-incident)

No collected logs. `/app/debug/repro.sh` builds gobgpd from `/app` and runs it against Python stand-ins
for the routers (a minimal BGP speaker that enforces message size limits). Two faults from the earlier
transplants are planted together:

| State | What the repro shows |
|---|---|
| starter | rtr7 resets every few seconds (10,574-byte UPDATE) |
| capability check fixed only | rtr7 stays up but holds 482 of 2,100 routes; nothing on rtr7's side |
| both fixed | rtr7 holds all 2,100 |

Hypothesis: agents stop once the visible symptom (the resets) is gone. Passing needs them to check the
outcome the instruction asks for (every route received) and keep going.

## 2026-11-05/06 · reliability sweep (all 18 tasks × 3 attempts)

| Probe | Attempts | pass@1 | Cost | Median time |
|---|---|---|---|---|
| GPT-6 Luna | 54 | 100% | $0.26 | 68 s |
| Claude Haiku 5.5 | 54 | 100% | $0.29 | 32 s |

108/108. Not one failure, so single-attempt probes weren't hiding variance. The only differences
between the probes are time and cost: on the GoBGP tasks, Luna took 110–280 s and Haiku 80–315 s,
against 15–90 s on apnet. Two transient API errors (a 600 s OpenAI timeout, and an OpenAI prompt
flagged by its usage-policy filter, both on Luna) were retried by LiteLLM and didn't affect results.
The full-suite Docker `validate` didn't run (a shell comment pasted into zsh broke the command); the
sweep did build and run every task image with the timestamp change.

## 2026-11-06 · two faults, live reproduction

Full Docker `validate` on the Mac: all 19 tasks valid (starter fails, every alternative passes, every
control fails on its pinned check).

| Task | GPT-6 Luna | Claude Haiku 5.5 |
|---|---|---|
| bgp-agg-incident | pass, 285 s, 23 cmds, $0.01 | pass, 497 s, 34 cmds, $0.03 |

Both worked like engineers: read the repro, ran it, fixed the capability check, **re-ran it, saw rtr7
still short of routes**, found the tagging bug and verified with the repro again (Luna ran it 2 times,
Haiku 6). Haiku also wrote its own regression test. The hypothesis (agents stop once the visible
symptom is gone) was wrong for these models. Their longest runs so far, but not a failure. Relabeled
Tier 1.

Repro fix: when an agent's command timed out, the stand-ins kept running and held port 179 (Haiku
spent 4 commands killing them). repro.sh now records the PIDs it starts and stops exactly those on the
next run. (A first attempt with `pkill -f` matched the caller's own shell and killed it.)

**Overall after 7 rounds (19 tasks, 116 probe attempts, ~$1):** no task form tried so far separates
the cheapest current models from a perfect score: single bugs, large codebases, novel code, missing text
clues, decoys, two interacting faults, a live system with no logs. Candidate forms from the incident
records, not yet tried: a regression caused by an earlier fix, where reverting it reintroduces the
older bug; recurrence after a fix that covered only one case; the test (not the product) is wrong;
writing a test that actually catches the bug; separating two unrelated failures in one report;
post-mortem from a core dump with no reproduction.
