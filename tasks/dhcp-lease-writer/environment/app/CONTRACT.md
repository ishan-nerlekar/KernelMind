# DHCP metadata writer contract v1

This entire contract is a synthetic specification. Familiar field names and the metadata rewrite mechanism are incident-derived; grammar, defaults and API semantics are newly chosen. No networking occurs.

## Public interface

Run `python3 candidate.py`. Read one UTF-8 JSON value from stdin, write exactly one JSON object to stdout, exit zero. The trusted driver supplies well-formed JSON (duplicate JSON object keys and nonfinite numbers are outside scope). The CLI is the stable API; internal functions may change. No dependencies beyond Python standard library. No disk side effects are required: `config` represents file contents, null represents an absent file.

Request object has required `config` and `update`, optional `interface` and `lease`, and no other keys. `config` is null or a string of at most 16384 characters containing only printable ASCII, tab and LF. `update` is a JSON boolean. Invalid envelope or update request: return `{"ok":false,"config":original}`; original is the supplied config value, or null if there is no object/config field. Preserve it even when it has an invalid type. Error wording is not part of the API; response has exactly `ok` and `config` keys.

When update=false, return `{"ok":true,"config":original}` exactly, including null and missing terminal newline. Do not parse configuration or validate optional interface/lease fields. Envelope validation still applies. No-update means no creation or normalization.

When update=true, `interface` and `lease` are required. Interface is a string matching `[A-Za-z][A-Za-z0-9_.-]{0,31}`. Lease is an object with required `address`, `netmask`, `seconds` and optional `gateway`, `dns`, `domain`; reject all other keys. Address is canonical dotted-decimal IPv4 (four octets 0–255, no leading zeroes). Netmask is a canonical contiguous dotted-decimal IPv4 mask, including 0.0.0.0 and 255.255.255.255. Seconds is a string matching `[1-9][0-9]{0,8}`. No network reachability, subnet membership, unicast or lease-expiration checks are required. Gateway/dns must be canonical IPv4 strings or empty. Domain is empty or `[A-Za-z0-9][A-Za-z0-9.-]{0,62}`. Missing optional values and empty strings both mean remove that managed field, even if previously populated. Null optional values are invalid.

## Configuration subset

Sectionless, case-sensitive assignments only. Sections are unsupported. Nonempty file is LF-delimited; final LF optional. Each line is blank (spaces/tabs allowed), a comment (first non-space/tab character is #), or an assignment. Assignment: spaces/tabs, key `[A-Za-z][A-Za-z0-9_]*`, spaces/tabs, `=`, spaces/tabs, value, spaces/tabs. Unquoted value is zero or more `[A-Za-z0-9_./:-]` characters. Double-quoted value may contain printable ASCII including spaces, # and =; a backslash must be followed by either a backslash or a double quote, decoding to that character. No other escapes are allowed. Single quotes, inline comments, controls inside values, extra tokens, bare keys and section headers are malformed. Empty unquoted or quoted values are supported. A # inside a quoted value is data. Reject a malformed existing configuration on an update, returning original unchanged. Validate all lines, including managed lines being replaced. Empty string is a valid existing empty file. No shell expansion or general INI semantics.

## Managed assignments

The only managed keys are listed below. Exact key matching: case variants, prefixes/suffixes and names containing a managed name are unrelated. All assignments to these keys belong to this component; all old instances must be removed on every update. Unrelated duplicate assignments remain as separate original lines; no effective-value interpretation is needed. Comments never count as assignments.

| Field | Historical evidence (safe summary) | Synthetic behaviour | Every update? |
|---|---|---|---|
| BOOTPROTO | Mode restored by historical writer change | exactly one value dhcp | yes |
| DEVICE | Writer emits interface identity | interface | yes |
| IPADDR | Writer emits leased address | lease.address | yes |
| SUBNET | Writer emits subnet mask | lease.netmask | yes |
| LeaseTime | Writer and regression use lease duration | lease.seconds | yes |
| GATEWAY | Writer emits gateway | lease.gateway if nonempty | no |
| PrimaryDNS | Writer emits primary resolver | lease.dns if nonempty | no |
| DNSPrefix | Writer emits domain prefix | lease.domain if nonempty | no |

No other historical field is a managed key in this exercise.

On successful update return `{"ok":true,"config":text}`. Text must follow this grammar, contain exactly one assignment with the correct decoded value for each mandatory field, exactly one for each present nonempty optional, and zero for missing/empty optionals. No stale or duplicate managed assignments. Preserve every unrelated line, blank line and comment exactly in its original relative order and multiplicity, excluding its LF terminator. A formerly unterminated line may gain LF. Managed fields may appear anywhere among preserved lines, in any order, using any supported quoting/spacing. Their formatting and ordering are insignificant. Output need not have terminal LF. It may not add unrelated lines or comments.

For an absent file only, insert the unrelated default line `TYPE=Ethernet` exactly once. No other defaults. An existing empty file gets no defaults. If TYPE already occurs in an existing file, preserve it and every duplicate unchanged. Output can exceed input length after adding managed assignments; all evaluation chains remain within the request limit.

Repeated updates must obey the same invariants. Same lease means semantically identical managed values and preserved lines; byte-for-byte idempotence is not required. Different leases fully replace prior values, including clearing optional fields. No-update after update returns precisely the previous text.

## Observable invariants and exclusions

Exact: envelope/error/no-update responses; managed multiplicity and decoded values; preserved unrelated line sequence; absent-file default. Flexible: managed order, supported quoting/spacing, final LF, semantic rather than byte repetition. These rules are complete without a reference implementation.

No DHCP renewal triggering, packet exchange, real filesystem atomicity, AP firmware, synchronization delivery, receiver publication, RF reporting, original failing job or original production environment is tested. A passing development run says nothing about difficulty, novelty or agent capability.
