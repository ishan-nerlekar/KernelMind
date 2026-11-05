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
