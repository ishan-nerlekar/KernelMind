"""Validation, copying and one-document CLI transport for the synthetic contract."""
import copy
import json
import math
import sys

ERROR = {'error': 'invalid_input'}


def name(value):
    if not isinstance(value, str) or not value.strip():
        raise ValueError('name')


def vlan(value):
    if type(value) is not int or not 1 <= value <= 4094:
        raise ValueError('vlan')


def optional(obj, key, kind):
    value = obj.get(key)
    if value is not None and not isinstance(value, kind):
        raise ValueError(key)
    return value if value is not None else kind()


def finite(value):
    if isinstance(value, float) and not math.isfinite(value):
        raise ValueError('nonfinite')
    if isinstance(value, dict):
        for item in value.values():
            finite(item)
    elif isinstance(value, list):
        for item in value:
            finite(item)


def validated(request):
    """Return an isolated, validated snapshot; incomplete globals remain present."""
    finite(request)
    if not isinstance(request, dict) or not isinstance(request.get('aps'), list):
        raise ValueError('aps')
    ap_ids = set()
    for ap in request['aps']:
        if not isinstance(ap, dict):
            raise ValueError('ap')
        name(ap.get('id'))
        if ap['id'] in ap_ids:
            raise ValueError('duplicate ap')
        ap_ids.add(ap['id'])
        mappings = {}
        for item in optional(ap, 'global_vlans', list):
            if not isinstance(item, dict):
                raise ValueError('mapping')
            if item.get('name') is not None:
                name(item['name'])
            if item.get('vlan_id') is not None:
                vlan(item['vlan_id'])
            if item.get('name') is not None and item.get('vlan_id') is not None:
                key, value = item['name'], item['vlan_id']
                if key in mappings and mappings[key] != value:
                    raise ValueError('conflicting mapping')
                mappings[key] = value
        ssid_names = set()
        for ssid in optional(ap, 'ssids', list):
            if not isinstance(ssid, dict):
                raise ValueError('ssid')
            name(ssid.get('name'))
            if ssid['name'] in ssid_names:
                raise ValueError('duplicate ssid')
            ssid_names.add(ssid['name'])
            config = optional(ssid, 'config', dict)
            if config.get('dva') is not None and type(config['dva']) is not bool:
                raise ValueError('dva')
            for item in optional(config, 'vlans', list):
                vlan(item)
            optional(ssid, 'state', dict)
    return copy.deepcopy(request)


def global_support(ap):
    return any(item.get('name') is not None and item.get('vlan_id') is not None
               for item in (ap.get('global_vlans') or []))


def unique_object(pairs):
    obj = {}
    for key, value in pairs:
        if key in obj:
            raise ValueError('duplicate key')
        obj[key] = value
    return obj


def main(handle):
    try:
        request = json.loads(sys.stdin.buffer.read().decode('utf-8'),
                             object_pairs_hook=unique_object)
        response = handle(request)
    except (ValueError, UnicodeError, RecursionError):
        response = ERROR
    print(json.dumps(response, allow_nan=False))
