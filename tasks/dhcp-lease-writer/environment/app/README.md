# DHCP lease configuration writer

Repair this writer so lease updates satisfy [CONTRACT.md](CONTRACT.md) while preserving unrelated configuration. Configuration is represented as text; there is no network or real configuration-file mutation.

Files: `candidate.py` is the CLI entry point, `rules.py` provides syntax and request validation, and `example.json` is a sample request. You may change the Python files and their internal functions; preserve the public CLI. Only Python standard library dependencies are permitted. Evaluation stages `candidate.py` and optional `rules.py`; keep your solution self-contained in those files.

Run `python3 candidate.py < example.json`. Supply one well-formed JSON value on stdin; stdout must be exactly one response object with `ok` and `config` keys, then exit zero. See the contract for request validation, configuration grammar, optional values, errors and no-update behavior. `config: null` represents a missing file; `config: ""` represents an existing empty file.
