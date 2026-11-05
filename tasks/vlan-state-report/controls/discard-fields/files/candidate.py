"""Report SSID feature state from the current configuration snapshot."""
from rules import ERROR, global_support, main, validated


def handle(request):
    try:
        snapshot = validated(request)
    except (ValueError, RecursionError):
        return ERROR.copy()
    for ap in snapshot['aps']:
        for ssid in (ap.get('ssids') or []):
            config = ssid.get('config') or {}
            support = bool(config.get('vlans')) or global_support(ap)
            ssid['state'] = dict(ssid.get('state') or {})
            ssid['state']['dva'] = config.get('dva') is True and support
    return {'snapshot': {'aps': [{'id': ap['id'], 'ssids': [{'name': s['name'], 'state': s['state']} for s in (ap.get('ssids') or [])]} for ap in snapshot['aps']]}}


if __name__ == '__main__':
    main(handle)
