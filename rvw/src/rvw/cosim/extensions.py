"""C2 vector and hypervisor state. Missing observations are errors."""
import re

from rvw.csr.catalog import address

H_CSR_NAMES = ('sstatus', 'stvec', 'sepc', 'scause', 'stval',
               'mstatus', 'medeleg', 'mideleg', 'mepc', 'mcause', 'mtval',
               'hstatus', 'hedeleg', 'hideleg', 'htval', 'htinst', 'hgatp',
               'vsstatus', 'vstvec', 'vsepc', 'vscause', 'vstval', 'vsatp', 'mtinst', 'mtval2')
H_CSRS = tuple(address(name) for name in H_CSR_NAMES)


def has_extension(isa, letter):
    match = re.match(r"rv(?:32|64)([a-z]+)", isa.lower())
    return bool(match and letter in match[1])


def header_fields(header):
    if "reset_events" in header:
        from .reset_events import ResetReplay
        ResetReplay(header["reset_events"])
    if 'vector_memory' in header and (header['vector_memory'] is not True or not header.get('vector')):
        raise ValueError('vector_memory requires vector capture and true declaration')
    for name, letter in (("vector", "v"), ("hypervisor", "h")):
        if has_extension(header["isa"], letter):
            if header["schema"] != "rvw.rvfi/2" or not header.get(name):
                raise ValueError(f"{letter.upper()} requires C2/2 {name} observations")
        if name in header and header["schema"] != "rvw.rvfi/2":
            raise ValueError(f"{name} requires C2/2")
    if "debug" in header and (header['schema'] != 'rvw.rvfi/2' or header['debug'] is not True):
        raise ValueError('debug requires C2/2 and true declaration')
    if "vector" in header:
        v = header["vector"]
        if not isinstance(v, dict) or set(v) != {"vlen", "elen"}:
            raise ValueError("vector requires vlen and elen")
        for key, low, high in (("vlen", 128, 65536), ("elen", 8, 64)):
            n = v[key]
            if type(n) is not int or not low <= n <= high or n & (n-1):
                raise ValueError(f"unsupported vector {key}")
        if v["elen"] > v["vlen"]:
            raise ValueError("ELEN exceeds VLEN")
    if "hypervisor" in header and header["hypervisor"] is not True:
        raise ValueError("hypervisor must be true")


def state_fields(obj, header):
    from .trace import hexnum
    if ('vector_accesses' in obj) != bool(header.get('vector_memory')):
        raise ValueError('vector memory observations must match header declaration')
    if header.get('vector_memory'):
        accesses = obj['vector_accesses']
        if not isinstance(accesses, list):
            raise ValueError('vector_accesses must be a list')
        for a in accesses:
            if (not isinstance(a, dict) or set(a) != {'kind', 'address', 'size', 'data'}
                    or a['kind'] not in ('read', 'write') or type(a['size']) is not int
                    or a['size'] not in (1, 2, 4, 8)):
                raise ValueError('invalid vector memory access')
            a['address'] = hex(hexnum(a['address'], header['xlen']))
            a['data'] = hex(hexnum(a['data'], a['size'] * 8))
    for name in ("vector", "hypervisor", "debug"):
        if (name in obj) != (name in header):
            raise ValueError(f"{name} state must match header declaration")
    if "debug" in header:
        from .debug_state import validate
        validate(obj['debug'], header['xlen'])
    if "vector" in header:
        v = obj["vector"]
        keys = {"vstart", "vl", "vtype", "vcsr", "vs", "regs"}
        if not isinstance(v, dict) or set(v) != keys:
            raise ValueError("partial vector state")
        for key in keys - {"regs"}:
            v[key] = hexnum(v[key], 3 if key == "vcsr" else 2 if key == "vs" else header["xlen"])
        if not isinstance(v["regs"], list) or len(v["regs"]) != 32:
            raise ValueError("vector state requires all 32 registers, including mask v0")
        v["regs"] = [hexnum(r, header["vector"]["vlen"]) for r in v["regs"]]
    if "hypervisor" in header:
        h = obj["hypervisor"]
        if not isinstance(h, dict) or set(h) != {"virtual", "mode_after", "virtual_after", "csrs", "translations"}:
            raise ValueError("partial hypervisor state")
        if type(h["virtual"]) is not bool or type(h["virtual_after"]) is not bool or type(h["mode_after"]) is not int or h["mode_after"] not in (0, 1, 3):
            raise ValueError("invalid guest/host privilege")
        if (h["virtual"] and obj["mode"] == 3) or (h["virtual_after"] and h["mode_after"] == 3):
            raise ValueError("machine mode cannot be virtual")
        if not isinstance(h["csrs"], dict) or set(h["csrs"]) != {hex(a) for a in H_CSRS}:
            raise ValueError("partial hypervisor CSR state")
        h["csrs"] = {a: hexnum(v, header["xlen"]) for a, v in h["csrs"].items()}
        if not isinstance(h["translations"], list):
            raise ValueError("translations must be a list")
        for t in h["translations"]:
            if not isinstance(t, dict) or set(t) != {"va", "gpa", "pa", "access"} or t["access"] not in ("fetch", "load", "store"):
                raise ValueError("invalid two-stage translation")
            for k in ("va", "gpa", "pa"):
                t[k] = hexnum(t[k], header["xlen"])


def compare_extensions(actual, expected, header):
    diff = {}
    if header.get('vector_memory'):
        if 'vector_accesses' not in expected:
            raise ValueError('reference cannot check ordered vector memory')
        if actual['vector_accesses'] != expected['vector_accesses']:
            diff['vector_accesses'] = dict(expected=expected['vector_accesses'], actual=actual['vector_accesses'])
    elif expected.get('vector_accesses'):
        raise ValueError('trace lacks ordered vector memory capture')
    for name in ("vector", "hypervisor", "debug"):
        if name not in header:
            continue
        if name not in expected:
            raise ValueError(f"reference cannot check {name} state")
        for key, value in actual[name].items():
            if key not in expected[name]:
                raise ValueError(f"reference cannot check {name}.{key}")
            if value != expected[name][key]:
                diff[f"{name}.{key}"] = {"expected": serialize(expected[name][key]), "actual": serialize(value)}
    return diff


def serialize(value):
    if type(value) is int:
        return hex(value)
    if isinstance(value, dict):
        return {k: v if k == "mode_after" else serialize(v) for k, v in value.items()}
    if isinstance(value, list):
        return [serialize(v) for v in value]
    return value


def vector_sources(insn):
    """Integer sources for OP-V and vector memory major opcodes."""
    op, f3 = insn & 127, (insn >> 12) & 7
    rs1, rs2 = (insn >> 15) & 31, (insn >> 20) & 31
    if op == 0x57:
        if f3 == 7:
            if insn >> 30 == 3:  # vsetivli uses an immediate AVL
                return 0, 0
            return rs1, rs2 if insn >> 25 == 0x40 else 0
        return (rs1 if f3 in (4, 6) else 0), 0
    if op in (7, 0x27) and f3 in (0, 5, 6, 7):
        return rs1, rs2 if (insn >> 26) & 3 == 2 else 0
    return None
