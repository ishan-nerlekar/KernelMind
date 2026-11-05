import json, sys
r = json.load(sys.stdin)
print(json.dumps({'ok': True, 'config': r.get('config') if isinstance(r, dict) else None}))
