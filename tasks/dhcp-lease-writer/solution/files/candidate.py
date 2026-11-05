"""Contract-authored reference: remove managed lines, append current values."""
import json
import sys
from rules import MANAGED, parse, request_values


def handle(request):
    original = request.get('config') if isinstance(request, dict) else None
    try:
        values = request_values(request)
        if values is None:
            return {'ok': True, 'config': original}
        nodes = parse(original or '')
        kept = [line for line, key, _ in nodes if key not in MANAGED]
        if original is None:
            kept.append('TYPE=Ethernet')
        kept.extend(key + '=' + value for key, value in values.items())
        return {'ok': True, 'config': '\n'.join(kept) + '\n'}
    except (ValueError, TypeError):
        return {'ok': False, 'config': original}


if __name__ == '__main__':
    print(json.dumps(handle(json.load(sys.stdin))))
