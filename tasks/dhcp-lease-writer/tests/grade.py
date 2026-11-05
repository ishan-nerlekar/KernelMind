"""Hidden verifier for dhcp-lease-writer (ported from KernelMind v1 rc2 grade.py).

Runs the agent's CLI on 87 fixture scenarios (94 executions, some chained so each step
feeds the previous output back in) and checks observable contract behavior only. It never
imports the agent's code and never derives expectations from a reference implementation:
expected managed values are written out explicitly in cases.json.
"""
import json
import os
import string
import subprocess
import sys
from pathlib import Path

APP = Path(os.environ.get("APP_DIR", "/app"))
LOGS = Path(os.environ.get("LOGS_DIR", "/logs/verifier"))
CASES = Path(__file__).with_name("cases.json")

KEYS = {'BOOTPROTO', 'DEVICE', 'IPADDR', 'SUBNET', 'LeaseTime', 'GATEWAY', 'PrimaryDNS', 'DNSPrefix'}
LETTERS = set(string.ascii_letters)
KEYCHARS = LETTERS | set(string.digits + '_')
BARE = KEYCHARS | set('./:-')


class ExecutionFailure(Exception):
    pass


def execute(request):
    """Run the CLI once with a fresh process; it must print one JSON object and exit 0."""
    try:
        p = subprocess.run([sys.executable, "candidate.py"], cwd=APP, input=json.dumps(request),
                           capture_output=True, text=True, timeout=10)
    except subprocess.TimeoutExpired:
        raise ExecutionFailure("timeout")
    if p.returncode != 0:
        raise ExecutionFailure(f"exit {p.returncode}")
    try:
        return json.loads(p.stdout)
    except json.JSONDecodeError:
        raise ExecutionFailure("stdout is not one JSON value")


def inspect_text(text):
    """Independent small scanner; returns managed values per key and the unrelated raw lines."""
    if not isinstance(text, str) or any(c not in '\t\n' and not ' ' <= c <= '~' for c in text):
        raise ValueError('text encoding/type')
    rows = text.split('\n') if text else []
    if rows and rows[-1] == '':
        rows.pop()
    fields, unrelated = {}, []
    for raw in rows:
        row = raw.strip(' \t')
        if not row or row.startswith('#'):
            unrelated.append(raw)
            continue
        if '=' not in row:
            raise ValueError('missing equals')
        left, right = row.split('=', 1)
        key = left.rstrip(' \t')
        if not key or key[0] not in LETTERS or any(c not in KEYCHARS for c in key):
            raise ValueError('key')
        token = right.strip(' \t')
        if token.startswith('"'):
            chars = []
            pos = 1
            while pos < len(token) and token[pos] != '"':
                c = token[pos]
                if c == '\\':
                    pos += 1
                    if pos >= len(token) or token[pos] not in '\\"':
                        raise ValueError('escape')
                    c = token[pos]
                if not ' ' <= c <= '~':
                    raise ValueError('quoted control')
                chars.append(c)
                pos += 1
            if pos != len(token) - 1 or token[pos:pos + 1] != '"':
                raise ValueError('quote or trailing token')
            value = ''.join(chars)
        else:
            if any(c not in BARE for c in token):
                raise ValueError('bare value')
            value = token
        if key in KEYS:
            fields.setdefault(key, []).append(value)
        else:
            unrelated.append(raw)
    return fields, unrelated


def identical(left, right):
    return json.dumps(left, sort_keys=True) == json.dumps(right, sort_keys=True)


def observe(request, response, step):
    """Return failed check names for one execution (empty list = all good)."""
    if not isinstance(response, dict) or set(response) != {'ok', 'config'} or type(response['ok']) is not bool:
        return ['response_shape']
    original = request.get('config') if isinstance(request, dict) else None
    expectation = step['expect']
    if expectation in ('error', 'no_update'):
        expected = {'ok': expectation == 'no_update', 'config': original}
        return [] if identical(response, expected) else [expectation + '_response']
    if response['ok'] is not True:
        return ['unexpected_error']
    try:
        fields, preserved = inspect_text(response['config'])
    except ValueError:
        return ['output_syntax']
    _, prior = inspect_text(original or '')
    if original is None:
        prior.append('TYPE=Ethernet')
    failures = []
    expected = step['managed']
    if fields.get('BOOTPROTO') != ['dhcp']:
        failures.append('mode')
    if set(fields) != set(expected) or any(len(v) != 1 for v in fields.values()):
        failures.append('managed_multiplicity')
    if any(fields.get(k) != [v] for k, v in expected.items()):
        failures.append('managed_values')
    if preserved != prior:
        failures.append('preservation')
    return failures


def main():
    cases = json.loads(CASES.read_text())
    results = []
    for scenario in cases['scenarios']:
        current = cases['configurations'][scenario['config_id']]
        for index, step in enumerate(scenario['steps']):
            request = step['raw_request'] if 'raw_request' in step else {'config': current, **step['request']}
            response = None
            try:
                response = execute(request)
                failures = observe(request, response, step)
            except ExecutionFailure as exc:
                failures = ['candidate_execution']
                print(f"{scenario['id']} step {index + 1}: execution failure: {exc}")
            results.append({'scenario': scenario['id'], 'step': index + 1, 'failures': failures})
            # Chained scenarios feed each output into the next step.
            if isinstance(response, dict) and isinstance(response.get('config'), (str, type(None))):
                current = response['config']
    failed = [r for r in results if r['failures']]
    summary = {'checks_total': len(results), 'checks_passed': len(results) - len(failed),
               'failed_checks': sorted({f for r in failed for f in r['failures']}),
               'failures': failed[:50]}
    LOGS.mkdir(parents=True, exist_ok=True)
    (LOGS / 'results.json').write_text(json.dumps(summary, indent=2))
    print(f"{summary['checks_passed']}/{summary['checks_total']} passed; failed checks: {summary['failed_checks']}")
    return 1 if failed else 0


if __name__ == '__main__':
    sys.exit(main())
