"""Development alternative: ordered document nodes filled at existing slots."""
import json
import sys
from rules import MANAGED, parse, request_values


class Document:
    def __init__(self, text):
        self.nodes = [{'raw': raw, 'key': key} for raw, key, _ in parse(text)]

    def update(self, values):
        pending = dict(values)
        output = []
        for node in self.nodes:
            key = node['key']
            if key not in MANAGED:
                output.append(node['raw'])
            elif key in pending:
                output.append(key + '=' + json.dumps(pending.pop(key)))
        for key in sorted(pending):
            output.insert(0, key + '=' + json.dumps(pending[key]))
        return '\n'.join(output)


def handle(request):
    original = request.get('config') if isinstance(request, dict) else None
    try:
        values = request_values(request)
        if values is None:
            return {'ok': True, 'config': original}
        document = Document('TYPE=Ethernet\n' if original is None else original)
        return {'ok': True, 'config': document.update(values)}
    except (ValueError, TypeError):
        return {'ok': False, 'config': original}


if __name__ == '__main__':
    print(json.dumps(handle(json.load(sys.stdin))))
