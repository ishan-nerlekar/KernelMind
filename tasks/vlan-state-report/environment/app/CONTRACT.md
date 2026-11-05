# Snapshot VLAN state contract (version 1)

Repair `candidate.py` so each SSID reports DVA state from its current AP configuration. The starter incorrectly overlooks global VLAN support. This is an original synchronous Python exercise inspired by a configuration-to-state reporting defect. It models no forwarding, authentication, hardware, timing or normative OpenConfig behavior.

## Interface and shape

Python standard library only. `candidate.handle(request)` returns a JSON-compatible response without mutating request. CLI: `python3 candidate.py < example.json`. Read exactly one UTF-8 JSON document through EOF; emit exactly one JSON document, no diagnostics on stdout, exit 0 for both valid and invalid requests. Whitespace and JSON object key ordering do not matter. Duplicate object keys, non-finite numbers, malformed JSON, trailing documents and structurally invalid inputs return exactly `{"error":"invalid_input"}`. No partial snapshot is returned on error.

A request is an object with required `aps` array (empty allowed). Each AP is an object with required nonempty string `id`, optional `global_vlans` array and optional `ssids` array. AP ids must be unique. Each SSID is an object with required nonempty string `name`, optional `config` object and optional `state` object. SSID names must be unique within each AP; reuse across APs is allowed. Names and ids are exact, case-sensitive strings with no trimming; strings containing only whitespace are invalid.

Missing or null `global_vlans` and `ssids` mean no records; empty arrays mean the same. Missing or null `config` means no configured feature. Empty config object means the same. Missing or null `config.dva` means disabled; a present non-null value must be a JSON Boolean (0, 1 and strings are invalid). Missing, null or empty `config.vlans` means no local VLAN support. Otherwise it must be an array of integer VLAN ids in 1..4094 inclusive; Boolean, floating-point and string ids are invalid. Duplicated local ids are allowed and equivalent for support.

A global mapping is an object with fields `name` (nonblank string) and `vlan_id` (integer in 1..4094, excluding Boolean). A missing or null required field makes a mapping incomplete and unusable. A provided non-null field with an invalid value rejects the entire request, even in an incomplete record or on an AP without SSIDs. Non-object records reject the request. Complete mappings with the same name and same id are allowed and equivalent for support. Complete mappings with the same name and different ids reject the entire request. Different names may map to the same id. Incomplete records do not participate in conflicts.

Missing or null SSID state means an empty state object for reporting; a present non-null state must be an object. Incoming `state.dva` is opaque stale data of any JSON type and is always overwritten. Unrecognized fields at every level are opaque JSON values and must be preserved, including nulls and nested structures. All known fields are validated even if the feature is disabled.

## Derivation and output

**Synthetic project decision:** any usable global mapping applies to every enabled SSID on that AP, with no SSID reference required. This is not a universal rule inferred from the incident.

For each SSID, reported `state.dva` is a Boolean: configured `dva` is exactly true AND (its local `config.vlans` is nonempty OR its own AP has at least one complete usable global mapping). Explicit false always stays false. Another AP can never supply support. Both sources together are an OR with no precedence. Neither source means false.

Success is exactly `{"snapshot": <a deep copy of request>}` with only each SSID's `state` object created/replaced as necessary and `state.dva` set. Preserve every other field, all configuration, null versus absent containers, all list ordering and duplicate records. Object key order and formatting have no meaning. Arrays are never sorted or deduplicated. Reordering APs, SSIDs or mappings reorders only those arrays and does not change per-identity derivation. Repeating an equivalent request produces an equivalent response. Feeding a successful snapshot back in is idempotent. Every invocation derives from that invocation's configuration; successive snapshots adding or removing support must overwrite stale state. No cache or retained operational state is part of this contract.

## Submission boundary

Submit `candidate.py` and adjacent `rules.py` (the supplied helper may be edited). Those are the only staged Python files. Keep `handle` available and the documented CLI working. Local execution runs trusted development code; independent evaluation runs submissions through a pinned protected runner. No network or third-party packages are needed.
