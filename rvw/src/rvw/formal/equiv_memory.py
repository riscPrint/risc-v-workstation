"""Exact finite-memory lowering for closed equivalence obligations."""
import hashlib
import json
from . import common


def aliases(module):
    """Give mapped RAM state legal inventory names without changing any bit."""
    count = 0
    for name, cell in module['cells'].items():
        if cell['type'] not in common._SYNCHRONOUS_STATE:
            continue
        bits = cell['connections']['Q']
        alias = 'rvw_memory_state_' + hashlib.sha256(name.encode()).hexdigest()[:20]
        if alias in module['netnames']:
            raise ValueError('memory inventory alias collision')
        module['netnames'][alias] = {'hide_name':0, 'bits':bits, 'attributes':{}}
        count += len(bits)
    # RTLIL derives public names from spelling, so hide_name does not survive
    # a write/read round trip. Remove only debug aliases, never cell bits.
    for name in list(module['netnames']):
        if not common.is_hier(name):
            alias = 'rvw_memory_net_' + hashlib.sha256(name.encode()).hexdigest()[:20]
            if alias in module['netnames']:
                raise ValueError('memory net alias collision')
            module['netnames'][alias] = {**module['netnames'].pop(name), 'hide_name':0}
    return count


def lower(model, top, directory, snapshot, budget):
    script = directory/'memory-map.ys'
    source = directory/'memory-map.json'
    target = directory/'memory-map.il'
    script.write_text(f'read_rtlil {model}\nhierarchy -check -top {top}\nflatten\nmemory_collect\nmemory_map -formal\nwrite_json {source}\n')
    rc, _ = common.run(['yosys','-Q','-s',str(script)], directory, directory/'memory-map.log',budget())
    if rc:
        raise ValueError('exact memory mapping failed')
    design = json.loads(source.read_text())
    module = design['modules'][top]
    if any(cell['type'].startswith('$mem') for cell in module['cells'].values()):
        raise ValueError('unmapped memory remains')
    bits = aliases(module)
    source.write_text(json.dumps(design)+'\n')
    script.write_text(f'read_json {source}\nwrite_rtlil {target}\n')
    rc, _ = common.run(['yosys','-Q','-s',str(script)], directory,directory/'memory-export.log',budget())
    if rc:
        raise ValueError('mapped memory export failed')
    for path in (source,script,target):
        snapshot.seal(path)
    return target, {'backend':'yosys memory_map -formal','state_bits':bits,
                    'semantics':'exact finite RTL storage; independent initial values; no memory equality assumptions'}
