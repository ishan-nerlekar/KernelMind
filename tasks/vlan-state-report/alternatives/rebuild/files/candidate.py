"""Alternative: build a set of eligible (AP id, SSID name) identities first."""
from rules import ERROR, main, validated


def handle(request):
    try:
        snapshot = validated(request)
    except (ValueError, RecursionError):
        return ERROR.copy()
    globally_ready = {ap['id'] for ap in snapshot['aps']
                      for item in (ap.get('global_vlans') or [])
                      if item.get('name') is not None and item.get('vlan_id') is not None}
    ready = set()
    for ap in snapshot['aps']:
        for ssid in (ap.get('ssids') or []):
            config = ssid.get('config') or {}
            if config.get('dva') is True:
                if config.get('vlans') or ap['id'] in globally_ready:
                    ready.add((ap['id'], ssid['name']))
    for ap in snapshot['aps']:
        for ssid in (ap.get('ssids') or []):
            ssid['state'] = {**(ssid.get('state') or {}),
                             'dva': (ap['id'], ssid['name']) in ready}
    return {'snapshot': snapshot}


if __name__ == '__main__':
    main(handle)
