import re
from datetime import datetime

def to_underscore(name):
    s1 = re.sub('(.)([A-Z][a-z]+)', r'\1_\2', name)
    return re.sub('([a-z0-9])([A-Z])', r'\1_\2', s1).lower()

def uncamelize(d):
    drop = []

    for k, v in d.items():
        u = to_underscore(k)
        if u != k and u not in d:
            d[u] = v
            drop.append(k)

    for k in drop:
        del d[k]

    return d

def as_bool(v):
    if v == 0 or v is False:
        return False
    return True

def as_datetime(v):
    if isinstance(v, int):
        return datetime.fromtimestamp(v)

def process_person_info(parent, person_info, addresses):
    from mailstream.lib.contextIO import Contact
    contacts = {}
    to_addrs = []
    to_contacts = []
    from_addr = None
    from_contact = None

    for info in addresses['to']:
        person_info[info.get('email')].setdefault('name', info.get('name'))
        to_addrs.append(info.get('email'))

    info = addresses['from']
    person_info[info.get('email')].setdefault('name', info.get('name'))
    from_addr = info.get('email')

    for addr, d in person_info.items():
        info = {
            'email': addr,
            'thumbnail': d.get('thumbnail'),
            'name': d.get('name')
        }
        c = Contact(parent, info)
        contacts.setdefault(addr, c)

        if addr in to_addrs:
            to_contacts.append(c)
            to_addrs.remove(addr)

        elif addr == from_addr:
            from_contact = c

    return contacts, to_contacts, from_contact
