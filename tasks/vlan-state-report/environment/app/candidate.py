"""Report SSID feature state from the current configuration snapshot."""
from rules import ERROR, main, validated


def handle(request):
    try:
        snapshot = validated(request)
    except (ValueError, RecursionError):
        return ERROR.copy()
    for ap in snapshot['aps']:
        for ssid in (ap.get('ssids') or []):
            config = ssid.get('config') or {}
            support = bool(config.get('vlans'))
            ssid['state'] = dict(ssid.get('state') or {})
            ssid['state']['dva'] = config.get('dva') is True and support
    return {'snapshot': snapshot}


if __name__ == '__main__':
    main(handle)
