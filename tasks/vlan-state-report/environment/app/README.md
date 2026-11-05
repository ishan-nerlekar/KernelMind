# VLAN state reporting repair

An enabled SSID reports DVA false when VLAN support exists only in its AP's global mappings. Repair the derivation while preserving validation and unrelated data. Read CONTRACT.md for the complete synthetic behavior.

Run with Python 3.12 standard library: `python3 candidate.py < example.json`.
The example must return its input under `snapshot`, preserving everything except `office.state.dva` becomes true. `handle(request)` is also available for local development. Submission consists of candidate.py and rules.py. No source evidence, solutions or hidden tests are included in this workspace.
