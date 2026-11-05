"""Validation for the documented synthetic configuration subset."""
import ipaddress
import json
import re

MANAGED = {'BOOTPROTO', 'DEVICE', 'IPADDR', 'SUBNET', 'LeaseTime',
           'GATEWAY', 'PrimaryDNS', 'DNSPrefix'}
ASSIGN = re.compile(r'[ \t]*([A-Za-z][A-Za-z0-9_]*)[ \t]*=[ \t]*("(?:[^"\\\x00-\x1f]|\\["\\])*"|[A-Za-z0-9_./:-]*)[ \t]*')


def lines(text):
    if not text:
        return []
    parts = text.split('\n')
    return parts[:-1] if parts[-1] == '' else parts


def parse(text):
    nodes = []
    for line in lines(text):
        key = value = None
        if line.strip(' \t') and not line.lstrip(' \t').startswith('#'):
            match = ASSIGN.fullmatch(line)
            if not match:
                raise ValueError('configuration syntax')
            key, value = match.groups()
            if value.startswith('"'):
                value = json.loads(value)
        nodes.append((line, key, value))
    return nodes


def ipv4(value):
    if not isinstance(value, str) or str(ipaddress.IPv4Address(value)) != value:
        raise ValueError('IPv4')
    return value


def request_values(req):
    if not isinstance(req, dict) or not {'config', 'update'} <= req.keys() or req.keys() - {'config', 'update', 'interface', 'lease'}:
        raise ValueError('envelope')
    text = req['config']
    if text is not None and (not isinstance(text, str) or len(text) > 16384 or any(c not in '\t\n' and not ' ' <= c <= '~' for c in text)):
        raise ValueError('config')
    if type(req['update']) is not bool:
        raise ValueError('update')
    if not req['update']:
        return None
    name, lease = req.get('interface'), req.get('lease')
    if not isinstance(name, str) or not re.fullmatch(r'[A-Za-z][A-Za-z0-9_.-]{0,31}', name):
        raise ValueError('interface')
    if not isinstance(lease, dict) or not {'address', 'netmask', 'seconds'} <= lease.keys() or lease.keys() - {'address', 'netmask', 'seconds', 'gateway', 'dns', 'domain'}:
        raise ValueError('lease')
    address, mask = ipv4(lease['address']), ipv4(lease['netmask'])
    inverted = int(ipaddress.IPv4Address(mask)) ^ 0xffffffff
    if inverted & (inverted + 1):
        raise ValueError('noncontiguous netmask')
    if not isinstance(lease['seconds'], str) or not re.fullmatch(r'[1-9][0-9]{0,8}', lease['seconds']):
        raise ValueError('seconds')
    values = dict(BOOTPROTO='dhcp', DEVICE=name, IPADDR=address, SUBNET=mask, LeaseTime=lease['seconds'])
    for source, target in [('gateway', 'GATEWAY'), ('dns', 'PrimaryDNS'), ('domain', 'DNSPrefix')]:
        value = lease.get(source, '')
        if not isinstance(value, str):
            raise ValueError('optional type')
        if value:
            if source == 'domain':
                if not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9.-]{0,62}', value):
                    raise ValueError('domain')
            else:
                ipv4(value)
            values[target] = value
    return values
