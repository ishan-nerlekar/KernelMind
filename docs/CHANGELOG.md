# Changelog

Every change to a task after any leaderboard model has run on it, with the reason. Tier calibration
probes (SPEC.md rule 3) are logged here too.

| Date | Task | Change | Reason | Runs affected |
|---|---|---|---|---|
| 2026-11-05 | dhcp-lease-writer, vlan-state-report | Ported from v1 | v2 format | none |
| 2026-11-05 | lease-renew-gateway, ssid-dva-global-vlans, radio-monitor-capability, peer-timeout-flap, neigh-roam-flush, rate-counter-wrap, seq-wraparound, config-override-precedence, frame-partial-read | Added (generated from taskgen/) | First Tier 2/3 tasks on apnet | none |
| 2026-11-05 | 8 Go tasks above | Tier 2 → Tier 1 | Both calibration probes solved all 8 (docs/CALIBRATION.md) | probe-luna, probe-haiku (probes only) |
| 2026-11-05 | bgp-extended-message | Added (incident-transplant: capability-gating pattern as new RFC 8654 code in GoBGP) | Hard-task rules: evidence only from the peer, feature spread over 5 files | none |
| 2026-11-05 | bgp-rtr-no-data, bgp-extended-message | Tier 2 → Tier 1 | Both probes solved (docs/CALIBRATION.md) | probe4, probe5 (probes only) |
| 2026-11-05 | bgp-legacy-missing-routes | Added (incident-transplant: unchecked-precondition pattern; decoy experiment) | Symptom greps into correct extended-message code; fault is the order of tagging vs. packing | none |
| 2026-11-05 | bgp-legacy-missing-routes | Tier 2 → Tier 1 | Both probes solved (docs/CALIBRATION.md) | probe6 (probes only) |
| 2026-11-05 | all generated Go tasks | Dockerfile normalizes file timestamps | mtimes revealed which files a task changed (`ls -lt`) | none (before any leaderboard run) |
| 2026-11-05 | bgp-legacy-missing-routes | Egress tags wired from gobgpd's config file to the server (`SetEgressTags`) | The API round trip dropped the new config field, so the evidence described a setting that couldn't take effect | probe6 (probes only) |
| 2026-11-05 | bgp-agg-incident | Added (Tier 3 experiment: two faults, live reproduction, no collected logs) | Tests whether agents verify the whole symptom is gone, not just the first one | none |
| 2026-11-06 | bgp-agg-incident | Tier 3 → Tier 1; repro.sh stops leftover processes by recorded PID | Both probes solved; interrupted repro runs left port 179 held | probe7 (probes only) |
