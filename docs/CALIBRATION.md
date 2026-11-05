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
