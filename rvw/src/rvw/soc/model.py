"""Versioned project-owned SoC data and deterministic exports."""
import copy
import json
import re
from pathlib import Path
from xml.etree import ElementTree as ET

from rvw.cosim.platform import Platform, number
from rvw.csr.catalog import load_model, peripheral_registers


def keys(obj, allowed, required=()):
    if not isinstance(obj, dict) or set(obj) - set(allowed) or set(required) - set(obj):
        raise ValueError(f"expected fields {sorted(allowed)}; required {sorted(required)}")


def ident(value):
    if not isinstance(value, str) or not re.fullmatch(r"[a-z][a-z0-9_]*", value):
        raise ValueError("names must match [a-z][a-z0-9_]*")
    return value


def disjoint(items, base, size):
    end = 0
    for item in sorted(items, key=lambda r: r[base]):
        if item[base] < end or item[size] <= 0:
            raise ValueError("overlapping or empty ranges")
        end = item[base] + item[size]


def load(path):
    obj = load_model(path)
    keys(obj, {'schema', 'name', 'address_bits', 'platform', 'regions', 'interrupts'},
         {'schema', 'name', 'address_bits', 'platform', 'regions', 'interrupts'})
    if obj['schema'] != 'rvw.soc/1':
        raise ValueError('unsupported SoC schema')
    ident(obj['name'])
    bits = obj['address_bits']
    if type(bits) is not int or not 1 <= bits <= 64:
        raise ValueError('address_bits must be 1..64')
    if not isinstance(obj['platform'], dict) or {'ram', 'mmio'} & obj['platform'].keys():
        raise ValueError('platform must omit ram and mmio; regions define them')
    if not isinstance(obj['regions'], list) or not obj['regions']:
        raise ValueError('regions must be a non-empty list')
    names = set()
    for r in obj['regions']:
        keys(r, {'name', 'kind', 'base', 'size', 'permissions', 'cacheable', 'registers'},
             {'name', 'kind', 'base', 'size', 'permissions', 'cacheable', 'registers'})
        name = ident(r['name'])
        if name.upper() in names:
            raise ValueError('duplicate region name')
        names.add(name.upper())
        r['base'], r['size'] = number(r['base']), number(r['size'])
        if r['base'] < 0 or r['size'] <= 0 or r['base'] + r['size'] > 1 << bits:
            raise ValueError('region exceeds address width')
        # Every region is one naturally aligned decoder window in this version.
        if r['size'] & (r['size'] - 1) or r['base'] % r['size']:
            raise ValueError('decode window must have aligned power-of-two size')
        if r['kind'] not in ('ram', 'mmio') or r['permissions'] not in ('r', 'rw', 'rx', 'rwx'):
            raise ValueError('invalid region kind or permissions')
        if type(r['cacheable']) is not bool or not isinstance(r['registers'], list):
            raise ValueError('cacheable must be boolean; registers must be a list')
        if r['kind'] == 'ram' and r['registers']:
            raise ValueError('registers require mmio')
        regnames = set()
        for reg in r['registers']:
            keys(reg, {'name', 'offset', 'width', 'access', 'reset', 'read_action', 'write_action'},
                 {'name', 'offset', 'width', 'access', 'reset', 'read_action', 'write_action'})
            rn = ident(reg['name'])
            if rn in regnames:
                raise ValueError('duplicate register name')
            regnames.add(rn)
            reg['offset'] = number(reg['offset'])
            w = reg['width']
            if type(w) is not int or w not in (8, 16, 32, 64):
                raise ValueError('register width must be 8, 16, 32 or 64')
            if reg['offset'] < 0 or reg['offset'] % (w // 8) or reg['offset'] + w // 8 > r['size']:
                raise ValueError('register alignment or bounds invalid')
            if reg['access'] not in ('r', 'w', 'rw') or reg['read_action'] not in ('none', 'clear') or reg['write_action'] not in ('normal', 'one_to_clear'):
                raise ValueError('unsupported register access or side effect')
            if reg['reset'] is not None:
                reg['reset'] = number(reg['reset'])
                if not 0 <= reg['reset'] < 1 << w:
                    raise ValueError('register reset exceeds width')
        disjoint([dict(x, bytes=x['width']//8) for x in r['registers']], 'offset', 'bytes')
    disjoint(obj['regions'], 'base', 'size')
    if not isinstance(obj['interrupts'], list):
        raise ValueError('interrupts must be a list')
    irqnames = set()
    for irq in obj['interrupts']:
        keys(irq, {'name', 'region', 'register', 'cause'}, {'name', 'region', 'register', 'cause'})
        if ident(irq['name']) in irqnames:
            raise ValueError('duplicate interrupt name')
        irqnames.add(irq['name'])
        if type(irq['cause']) is not int or irq['cause'] not in obj['platform'].get('irq_inputs', []):
            raise ValueError('interrupt cause must be a platform irq_input')
        matches = [r for r in obj['regions'] if r['name'] == irq['region']]
        if not matches or irq['register'] not in [g['name'] for g in matches[0]['registers']]:
            raise ValueError('interrupt must reference a declared register')
    return obj


def platform(obj):
    p = copy.deepcopy(obj['platform'])
    for kind in ('ram', 'mmio'):
        p[kind] = [dict(base=hex(r['base']), size=hex(r['size'])) for r in obj['regions'] if r['kind'] == kind]
    return p


def dumps(obj):
    return json.dumps(obj, indent=2, sort_keys=True) + '\n'


def svd(obj):
    def add(parent, name, value):
        ET.SubElement(parent, name).text = str(value)
    root = ET.Element('device', schemaVersion='1.3')
    for k, v in [('name', obj['name']), ('version', '1'), ('description', 'Project register subset'),
                 ('addressUnitBits', 8), ('width', obj['platform']['xlen'])]:
        add(root, k, v)
    peripherals = ET.SubElement(root, 'peripherals')
    for r in obj['regions']:
        if not r['registers']:
            continue
        per = ET.SubElement(peripherals, 'peripheral')
        add(per, 'name', r['name'])
        add(per, 'baseAddress', hex(r['base']))
        regs = ET.SubElement(per, 'registers')
        for g in peripheral_registers(r):
            reg = ET.SubElement(regs, 'register')
            for k, v in [('name', g['name']), ('addressOffset', hex(g['offset'])), ('size', g['width']),
                         ('access', {'r':'read-only', 'w':'write-only', 'rw':'read-write'}[g['access']])]:
                add(reg, k, v)
            if g['reset'] is not None:
                add(reg, 'resetValue', hex(g['reset']))
            if g['write_action'] == 'one_to_clear':
                add(reg, 'modifiedWriteValues', 'oneToClear')
            if g['read_action'] == 'clear':
                add(reg, 'readAction', 'clear')
    ET.indent(root)
    return ET.tostring(root, encoding='unicode') + '\n'


def exact_json(value):
    """Keep large integers exact in simulation readers that use Double."""
    if type(value) is int and abs(value) > 9007199254740991:
        return hex(value)
    if isinstance(value, dict):
        return {k: exact_json(v) for k, v in value.items()}
    if isinstance(value, list):
        return [exact_json(v) for v in value]
    return value


def generate(source, out):
    obj = load(source)
    p = platform(obj)
    # Use the existing consumer to reject settings that Spike/cosim cannot use.
    out = Path(out)
    import tempfile
    with tempfile.TemporaryDirectory() as tmp:
        check = Path(tmp) / 'platform.json'
        check.write_text(dumps(p))
        validated = Platform.load(None, check)
    if validated.reset_pc >= 1 << obj['address_bits'] or not any(
            r['base'] <= validated.reset_pc < r['base'] + r['size'] and 'x' in r['permissions']
            for r in obj['regions']):
        raise ValueError('reset PC must lie in an executable region')
    header = ['/* Generated by rvw soc. */', '#ifndef RVW_SOC_H', '#define RVW_SOC_H', '#include <stdint.h>']
    linker = ['/* Generated by rvw soc. Include with the program section layout. */', 'MEMORY {']
    dts = ['/dts-v1/;', '/ {', '  #address-cells = <2>;', '  #size-cells = <2>;']
    for r in obj['regions']:
        prefix = 'RVW_' + r['name'].upper()
        header += [f'#define {prefix}_BASE UINT64_C({hex(r["base"])})', f'#define {prefix}_SIZE UINT64_C({hex(r["size"])})']
        for g in peripheral_registers(r):
            header += [f'#define {prefix}_{g["name"].upper()}_ADDR UINT64_C({hex(g["address"])})']
        if r['kind'] == 'ram':
            linker += [f'  {r["name"]} ({r["permissions"]}) : ORIGIN = {hex(r["base"])}, LENGTH = {hex(r["size"])}']
            b, s = r['base'], r['size']
            dts += [f'  memory@{b:x} {{', '    device_type = "memory";',
                    f'    reg = <0x{b >> 32:x} 0x{b & 0xffffffff:x} 0x{s >> 32:x} 0x{s & 0xffffffff:x}>;', '  };']
    # No compatible/interrupt-controller bindings are guessed for custom devices.
    dts += ['};']
    linker += ['}']
    header += ['#endif']
    files = {'platform.json': dumps(p), 'soc.h': '\n'.join(header)+'\n', 'memory.ld': '\n'.join(linker)+'\n',
             'soc.dts': '\n'.join(dts)+'\n', 'registers.svd': svd(obj),
             'sim-map.json': dumps(exact_json(dict(schema='rvw.sim-map/1', address_bits=obj['address_bits'], regions=obj['regions'], interrupts=obj['interrupts']))),
             'spike.args': f'--isa={validated.reference_isa or validated.isa}\n--pc={hex(validated.reset_pc)}\n-m' + ','.join(f'{hex(b)}:{hex(s)}' for b,s in validated.ram)+'\n'}
    out.mkdir(parents=True, exist_ok=True)
    for name, content in files.items():
        (out / name).write_text(content)
    return sorted(files)
