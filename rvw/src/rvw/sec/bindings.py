"""Automatic flow-tracking bindings: memory regions from the SoC map, CSRs from the catalog.

A policy can name `{"soc_region": NAME}` (optionally `register`, or `offset` and `size`)
in `memory_regions`, and CSR names in `csrs`. Regions resolve through the project's
`rvw.soc/1` map. A CSR name is checked against the pinned CSR catalog and resolved to
the one design netname that stores it. A binding `csr_signals` map overrides the search.
No match, or more than one, is an error that lists the candidates.
"""
import re
from rvw.formal.csr_catalog import catalog


def memory(policy, soc_path):
    """Replace `soc_region` entries with base/size entries."""
    entries = []
    regions = None
    for entry in policy.get('memory_regions', []):
        if 'soc_region' not in entry:
            entries.append(entry); continue
        if regions is None:
            if not soc_path:
                raise ValueError('soc_region needs a SoC map (--soc or binding "soc")')
            from rvw.soc.model import load
            regions = {r['name']: r for r in load(soc_path)['regions']}
        r = regions.get(entry['soc_region'])
        if r is None:
            raise ValueError(f'SoC map has no region {entry["soc_region"]}; regions: {", ".join(sorted(regions))}')
        if 'register' in entry:
            reg = [x for x in r['registers'] if x['name'] == entry['register']]
            if len(reg) != 1:
                raise ValueError(f'region {r["name"]} has no register {entry["register"]}')
            base = r['base'] + int(str(reg[0]['offset']), 0); size = max(4, int(reg[0]['width'])//8)
        else:
            base = r['base'] + int(str(entry.get('offset', 0)), 0)
            size = int(str(entry.get('size', r['size'] - int(str(entry.get('offset', 0)), 0))), 0)
            if base + size > r['base'] + r['size']:
                raise ValueError('secret window exceeds its SoC region')
        entries.append(dict(base=hex(base), size=hex(size), soc_region=r['name'], **({'register': entry['register']}
                                                                                      if 'register' in entry else {})))
    return entries


def csr_name(name):
    """A catalog CSR name, from a name or a numeric address."""
    regs = catalog()['registers']
    if isinstance(name, int) or re.fullmatch(r'0x[0-9a-fA-F]+|\d+', str(name)):
        address = int(str(name), 0)
        found = [n for n, r in regs.items() if r.get('definition', {}).get('address') == address]
        if len(found) != 1:
            raise ValueError(f'CSR address {address:#x} is not one catalog CSR')
        return found[0]
    if name not in regs:
        raise ValueError(f'{name} is not in the pinned CSR catalog')
    return name


def csr_signals(names, netnames, overrides=None, registers=(), ports=()):
    """Map CSR names to the design netnames that store them."""
    overrides = overrides or {}
    out = {}
    for raw in names:
        name = csr_name(raw)
        if name in overrides:
            if overrides[name] not in netnames:
                raise ValueError(f'csr_signals names {overrides[name]}, which is not in the design')
            out[name] = overrides[name]; continue
        pattern = re.compile(r'(^|_)'+re.escape(name)+r'(_value)?$', re.I)
        found = sorted(n for n in netnames if not n.startswith('$') and '\\' not in n and pattern.search(n))
        if len(found) > 1:
            # Storage beats copies of it: prefer flop outputs, then internal names over ports.
            for keep in (lambda n: n in registers, lambda n: n not in ports):
                if len([n for n in found if keep(n)]) >= 1:
                    found = [n for n in found if keep(n)]
        if len(found) != 1:
            raise ValueError(f'CSR {name}: {"no storage signal" if not found else "ambiguous signals " + ", ".join(found[:8])}; '
                             'declare it in the binding csr_signals map')
        out[name] = found[0]
    return out
