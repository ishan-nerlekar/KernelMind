import json, sys
r = json.load(sys.stdin)
print(json.dumps({'ok': False, 'config': r.get('config') if isinstance(r, dict) else None}))
