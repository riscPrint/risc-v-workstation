"""Strict IP-XACT 1685-2014 memoryMap subset. Never discard unknown semantics."""
from pathlib import Path
from xml.etree import ElementTree as ET
from .model import dumps, load, number

NS = 'http://www.accellera.org/XMLSchema/IPXACT/1685-2014'


def import_ipxact(source, template, out):
    """Replace register lists in existing MMIO regions, matched by addressBlock name."""
    obj = load(template)
    root = ET.fromstring(Path(source).read_text())
    def tag(e):
        if not e.tag.startswith('{' + NS + '}'):
            raise ValueError('requires IP-XACT 1685-2014 namespace')
        return e.tag.split('}', 1)[1]
    def children(e, allowed):
        result = {}
        if e.attrib:
            raise ValueError('unsupported IP-XACT attributes')
        for c in e:
            name = tag(c)
            if name not in allowed:
                raise ValueError('unsupported IP-XACT element: ' + name)
            result.setdefault(name, []).append(c)
        return result
    def one(d, name):
        values = d.get(name, [])
        if len(values) != 1 or len(values[0]) or values[0].attrib:
            raise ValueError('requires one scalar ' + name)
        return values[0].text.strip()
    if tag(root) != 'memoryMap':
        raise ValueError('requires standalone memoryMap')
    top = children(root, {'name', 'addressUnitBits', 'addressBlock'})
    one(top, 'name')
    if number(one(top, 'addressUnitBits')) != 8:
        raise ValueError('only byte addressing is supported')
    seen = set()
    for block in top.get('addressBlock', []):
        b = children(block, {'name', 'baseAddress', 'range', 'width', 'usage', 'register'})
        name = one(b, 'name')
        matches = [r for r in obj['regions'] if r['name'] == name and r['kind'] == 'mmio']
        if len(matches) != 1 or name in seen:
            raise ValueError('addressBlock must name one distinct template MMIO region')
        seen.add(name)
        region = matches[0]
        if number(one(b, 'baseAddress')) != region['base'] or number(one(b, 'range')) != region['size']:
            raise ValueError('addressBlock bounds differ from template')
        width = number(one(b, 'width'))
        if width not in (8, 16, 32, 64) or one(b, 'usage') != 'register':
            raise ValueError('unsupported addressBlock width or usage')
        regs = []
        for elem in b.get('register', []):
            g = children(elem, {'name', 'addressOffset', 'size', 'access', 'field'})
            access = one(g, 'access')
            if access not in ('read-only', 'write-only', 'read-write'):
                raise ValueError('unsupported register access')
            fields = g.get('field', [])
            if len(fields) != 1:
                raise ValueError('requires one full-register field')
            f = children(fields[0], {'name', 'bitOffset', 'bitWidth', 'resets', 'access', 'readAction', 'modifiedWriteValue'})
            one(f, 'name')
            if number(one(f, 'bitOffset')) != 0 or number(one(f, 'bitWidth')) != number(one(g, 'size')):
                raise ValueError('partial fields are unsupported')
            if 'access' in f and one(f, 'access') != access:
                raise ValueError('field access differs from register')
            reset = None
            if 'resets' in f:
                if len(f['resets']) != 1:
                    raise ValueError('duplicate resets')
                resets = children(f['resets'][0], {'reset'})
                if len(resets.get('reset', [])) != 1:
                    raise ValueError('duplicate reset')
                rs = children(resets['reset'][0], {'value', 'mask'})
                reset = number(one(rs, 'value'))
                if number(one(rs, 'mask')) != (1 << number(one(g, 'size'))) - 1:
                    raise ValueError('partial reset masks are unsupported')
            read = one(f, 'readAction') if 'readAction' in f else 'none'
            write = one(f, 'modifiedWriteValue') if 'modifiedWriteValue' in f else 'normal'
            if read not in ('none', 'clear') or write not in ('normal', 'oneToClear'):
                raise ValueError('unsupported register side effect')
            regs.append(dict(name=one(g, 'name'), offset=number(one(g, 'addressOffset')),
                             width=number(one(g, 'size')), access={'read-only':'r', 'write-only':'w', 'read-write':'rw'}[access],
                             reset=reset, read_action=read, write_action='one_to_clear' if write == 'oneToClear' else 'normal'))
        region['registers'] = regs
    if not seen:
        raise ValueError('no addressBlocks')
    # Reuse all map validation, including interrupt references, before replacing output.
    import tempfile
    with tempfile.TemporaryDirectory() as tmp:
        check = Path(tmp) / 'map.json'
        check.write_text(dumps(obj))
        load(check)
    Path(out).write_text(dumps(obj))
    return sorted(seen)
