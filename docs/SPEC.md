# KernelMind spec (v2.0, Nov 8, 2026)

## What it measures

**Can a coding agent go from a symptom to the root cause and a correct, non-breaking fix in a
networked system?** A symptom is what an on-call engineer sees: a bug report, logs, a wrong value
in an API, a hang. A fix is correct when hidden tests for the reported behavior pass *and* the
system's existing behavior is unchanged.

Out of scope: writing new features, performance tuning, real hardware, and anything needing
internet access during the attempt.

## Task anatomy

Every task has: a container with a buildable codebase; `instruction.md` with the symptom only (never
the fix, the file or the function); hidden tests (symptom checks plus the full regression suite);
a reference fix; at least one alternative valid fix where the fix space allows; at least three
plausible wrong fixes, each pinned to the check it must fail; and metadata (tier, root cause, origin,
files and lines touched, human solve time where measured).

## Tiers

| Tier | Codebase | Agent must | Target share | Target best-model pass@1 |
|---|---|---|---|---|
| 1 Localized | One small module, explicit contract | Repair one function to match the contract | ~20% | 70–90% |
| 2 Diagnose | Multi-package Go system, 5–15k lines | Find the faulty component from a report and logs; fix without regressions | ~55% | 25–50% |
| 3 Investigate | Same system running as several processes | Reproduce the failure (timing, concurrency, partial failure), isolate it, fix | ~25% | 5–25% |

## Root causes and planned tasks

One task per root cause at minimum; a root cause never appears in more than three tasks.
Origin: **A** = pattern from a production incident (original code), **O** = original, **H** = held out.
From Nov 5 the main public set is `incident-transplant`: a real production incident's causal chain, symptoms and evidence,
re-implemented as new feature code inside GoBGP, so the scenario is unique and the buggy code can't be recalled from
upstream. `upstream-mutation` tasks (bugs planted in existing public code) are kept for calibration only.

| # | Root cause | Origin | Tier 1 (ported) | Tier 2/3 task in the Go system |
|---|---|---|---|---|
| 1 | Stale state on update | A | dhcp-lease-writer | T2: lease renewal refreshes address but keeps old gateway in the state store |
| 2 | Configured vs operational state | A | vlan-state-report | T2: state API ignores AP-wide VLAN config |
| 3 | Capability gating | A | monitor-vap-config | T2: radio mode applied to hardware that lacks the capability |
| 4 | Failure vs absence | A | peer-stats | T2: stats timeout treated as peer gone; neighbor flaps |
| 5 | Occupancy / counting | A | ipv6-cache-capacity | T2: neighbor cache admits past capacity after a flush |
| 6 | Unchecked precondition | A | ipv6-probe-preflight | T3: health probe uses link MTU, not path MTU; fails only across the tunnel |
| 7 | Message framing | A | acs-command-delivery | T3: control channel breaks on partial TCP reads under load |
| 8 | Rule precedence | A | afc-eligibility | T2: per-SSID override loses to global default |
| 9 | Data race | O | – | T3: concurrent map writes crash the controller under load |
| 10 | Lock-order deadlock | O | – | T3: config push and stats poll deadlock when they coincide |
| 11 | Lost wakeup | O | – | T3: non-blocking channel send drops a reconfigure signal |
| 12 | Time units | O | – | T2: renewal timer computed in ms where seconds expected |
| 13 | Non-idempotent retry | O | – | T3: retried config push is applied twice |
| 14 | Resource leak | O | – | T3: connection leak until file descriptors run out |
| 15 | Sequence-number wraparound | O | – | T2: update ordering breaks when a 16-bit sequence wraps |
| 16 | Byte order | O | – | T2: TLV length decoded little-endian |
| 17 | Boundary / off-by-one parsing | O | – | T2: last TLV in a packet silently dropped |
| 18 | Cache invalidation | O | – | T2: ARP cache not invalidated on interface flap |
| 19 | Swallowed error | O | – | T2: write error ignored; state reports success |
| 20 | Counter overflow | O | – | T2: rate goes negative when a 32-bit counter wraps |
| 21 | Partial failure without rollback | O | – | T3: failed multi-step apply leaves half-applied config |
| 22 | Identity resolution | H | held-out (private) | – |

Target: about 7 Tier 1, 18 Tier 2 and 8 Tier 3 tasks (~33), covering at least 20 root causes.

## Splits

- **Public:** all original-code tasks. No proprietary source, logs, bug IDs or names of internal systems.
- **Private held-out:** the held-out incident family, plus any task built from real proprietary code. Run
  by us, reported only as aggregate scores, never published. A large gap between public and private
  scores is a contamination warning.
- Tasks from the same incident family always share a split.

## Admission rules

1. Passes `kernelmind validate` (starter fails on the intended check; valid fixes pass; wrong fixes
   fail on their pinned checks) under Docker, 3 times in a row for Tier 3 (no flakiness).
2. Manual review: the instruction alone is enough to find the bug; no leaks.
3. **Tier calibration, not selection.** A task's tier is set by one probe run with
   `claude-haiku-5-5` and `gpt-6-luna`, which are excluded from the leaderboard. A task is never
   dropped or hardened *because a leaderboard model solved it*: that would bias the benchmark
   against those models. Tasks are dropped only if invalid.
4. Any change after a leaderboard run is logged in `docs/CHANGELOG.md` with its reason.

## Scoring

Primary: pass@1 (mean over attempts and tasks) with a 95% bootstrap CI over tasks, overall and per
tier. Also reported: pass@2, cost per attempt and per solved task, median time and steps.
Infrastructure errors and spending-cap stops are excluded and counted separately. Same scaffold,
prompt and limits for every model.
