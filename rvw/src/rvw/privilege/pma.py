"""Project-declared physical access boundary probes and bus observations."""
from .programs import HEAD, TAIL
import re


def programs(config):
    rows = []
    for region in config['pma']['regions']:
        if not re.fullmatch(r'[A-Za-z0-9_-]+', region['name']):
            raise ValueError('PMA region name must be a simple identifier')
        base, size = region['base'], region['size']
        widths = region['widths']
        if base < 0 or size < 1 or any(w not in (1, 2, 4, 8) for w in widths):
            raise ValueError('PMA region needs a nonnegative base, positive size and scalar widths')
        for width in (1, 2, 4, 8):
            if width>size:continue
            for edge, address in [('first', base), ('last', base + size - width)]:
                if address % width:
                    continue
                for write in (False, True):
                    if write and not region.get('test_writes', False):
                        continue
                    allowed = width in widths and region['write' if write else 'read']
                    ident = f'pma-{region["name"]}-{edge}-{width}-{int(write)}'
                    op = ('s' if write else 'l') + {1:'b',2:'h',4:'w',8:'d'}[width]
                    if not write and width < 8:
                        op += 'u'
                    value = region.get('value', 0) & ((1 << (width * 8)) - 1)
                    code = HEAD + f''' la t0, handler
 csrw mtvec, t0
 li a0, {address}
 li a1, {value}
access_site:
 {op} a1, 0(a0)
'''
                    if allowed and not write:
                        code += f' li t0, {value}\n bne a1, t0, fail\n'
                    code += (' j pass\n' if allowed else ' j fail\n') + f'''handler:
 csrr t0, mcause
 li t1, {7 if write else 5}
 bne t0, t1, fail
 csrr t0, mepc
 la t1, access_site
 bne t0, t1, fail
 csrr t0, mtval
 li t1, {address}
 bne t0, t1, fail
 {'j fail' if allowed else 'j pass'}
''' + TAIL
                    rows.append(dict(id=ident, assembly=code, family='pma', bins=[ident],
                        pma_expectation=dict(address=address,width=width,write=write,
                            count=region.get('bus_count_allowed' if allowed else 'bus_count_denied'),
                            state=region.get('device_state')),
                        reference_unavailable='Spike CLI does not implement this project PMA map'))
    if not rows:
        raise ValueError('PMA campaign has no probes')
    return rows


def observe(expected, capture):
    if not capture or capture.get('complete') is not True or (expected.get('count') is None and 'transfers' not in expected) or not expected.get('state'):
        return {'status':'inconclusive', 'reason':'need complete independent bus and device state contract'}
    if 'transfers' in expected:
        actual=[{k:t.get(k) for k in ('address','width','write')} for t in capture.get('transfers',[])]
        if actual!=expected['transfers']:
            return {'status':'fail','reason':'PMA probe-window transfer sequence differs'}
        matches=[]
    else:
        matches = [x for x in capture.get('transfers',[]) if x.get('address') == expected['address']]
    if 'transfers' not in expected and (len(matches) != expected['count'] or any(x.get('width') != expected['width'] or x.get('write') != expected['write'] for x in matches)):
        return {'status':'fail','reason':'PMA transfer count or shape differs'}
    for name, value in expected['state'].items():
        actual = capture.get('device_state',{}).get(name)
        if actual is None:
            return {'status':'inconclusive','reason':'missing device state'}
        if actual != value:
            return {'status':'fail','reason':'device state differs'}
    return {'status':'pass','reason':'declared PMA transfer and device observations checked'}
