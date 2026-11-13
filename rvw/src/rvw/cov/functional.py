"""Architectural observations from C2 traces, with data-only cover groups."""
from collections import Counter
from hashlib import sha256
from itertools import product
import json
from pathlib import Path

from rvw.common import riscv
from . import captured


def number(value):
    return int(value, 0) if isinstance(value, str) else int(value)


def decode(insn, xlen=64):
    """Decoded instruction as functional coverage records it (shared decoder: rvw.common.riscv)."""
    return riscv.decode(insn, xlen).as_dict()


DEFAULT = {"groups": [
    {"name": "class_mode", "fields": ["class", "mode"],
     "domains": [["alu", "load", "store", "branch", "jump", "multiply", "divide", "atomic", "csr", "system", "fence", "float"], ["U", "S", "M"]]},
    {"name": "mnemonic_mode", "fields": ["mnemonic", "mode"]},
    {"name": "trap_cause_mode", "fields": ["cause", "mode"], "when": {"event": "trap", "interrupt": False}},
    {"name": "interrupt_cause_mode", "fields": ["cause", "mode"], "when": {"event": "trap", "interrupt": True}},
    {"name": "handler_entry", "fields": ["mode"], "when": {"intr": True}, "domains": [["U", "S", "M"]]},
    {"name": "memory", "fields": ["access", "bytes", "alignment"], "when": {"event": "memory"},
     "domains": [["read", "write"], [1, 2, 4, 8], ["aligned", "misaligned"]]},
    {"name": "csr", "fields": ["csr", "csr_access", "mode"], "when": {"class": "csr"}},
    {"name": "branch", "fields": ["branch_taken", "mode"], "when": {"class": "branch"},
     "domains": [[True, False], ["U", "S", "M"]]},
    {"name": "rd_x0", "fields": ["rd_x0", "class"]},
    {"name": "dependency", "fields": ["back_to_back", "class"]},
]}


def matches(obs, condition):
    for field, expected in condition.items():
        value = obs.get(field)
        if isinstance(expected, dict):
            if set(expected) - {'in', 'min', 'max', 'mask', 'equals'}:
                raise ValueError(f'unsupported predicate: {expected}')
            if 'in' in expected and value not in expected['in']:
                return False
            if 'min' in expected and (value is None or value < expected['min']):
                return False
            if 'max' in expected and (value is None or value > expected['max']):
                return False
            if 'mask' in expected and (value is None or number(value) & number(expected['mask']) != number(expected['equals'])):
                return False
        elif value != expected:
            return False
    return True


def alignment(address, mask, size, xlen, aligned_mem):
    """`aligned`, `misaligned`, `noncontiguous-mask` or `undetermined` for one memory access.
    `aligned_mem` is the platform's RVFI address convention: True, `mem_addr` is the XLEN/8-aligned
    word and the mask's lowest set bit is the active-lane offset (riscv-formal ALIGNED_MEM); False,
    `mem_addr` is the byte address and masks start at bit 0; None, unknown. The access address is
    `mem_addr` plus the lane offset. A mask whose lanes cannot be placed is `undetermined`, never
    counted as aligned."""
    low = (mask & -mask).bit_length() - 1
    if size & (size - 1) or mask >> low != (1 << size) - 1:
        return 'noncontiguous-mask'
    word = xlen // 8
    if low and not aligned_mem:
        # A lane-shifted mask: the ALIGNED_MEM form, which a byte-address trace never uses, and an
        # unknown convention cannot place.
        return 'undetermined'
    if aligned_mem and (address % word or low + size > word):
        return 'undetermined'
    return 'aligned' if (address + low) % size == 0 else 'misaligned'


# The previous instruction's destination could not be read (round 14): the next instruction's
# `back_to_back` is this value, not True or False.
UNDETERMINED = 'undetermined'


def fp_destination(insn, info):
    """The FP register an instruction with an FP destination (`dest_bank` 'f') writes, from its
    encoding, or None for a form not listed. C2's `rd` is RVFI's integer write (0 for an FP write),
    so it never names an FP destination (round 14: every FP result was taken as f0)."""
    if info['length'] == 4:
        return (insn >> 7) & 31
    if info['mnemonic'] in ('c.fld', 'c.flw'):
        return 8 + ((insn >> 2) & 7)
    if info['mnemonic'] in ('c.fldsp', 'c.flwsp'):
        return (insn >> 7) & 31
    return None


def observations(row, xlen, previous, aligned_mem=None):
    mode = {0: 'U', 1: 'S', 3: 'M'}.get(row.get('mode'), 'unknown')
    if 'event' in row:
        if row['event'] == 'trap':
            cause = number(row['cause'])
            return [{**row, "mode": mode, "cause": cause & ((1 << (xlen - 1)) - 1),
                     "interrupt": bool(row.get('intr', cause >> (xlen - 1)))}], None
        # Input-level (`irq`) and end events do not break the instruction-pair window; other events do.
        return [], previous if row['event'] in ('end', 'irq') else None
    insn = number(row['insn'])
    info = decode(insn, xlen)
    rd = row.get('rd', 0)
    obs = {**row, **info, "event": "retire", "mode": mode,
           "rd_x0": rd == 0 and info['dest_bank'] == 'x',
           "back_to_back": UNDETERMINED if previous == UNDETERMINED and info['uses'] else
                           bool(previous and previous != UNDETERMINED and previous in info['uses']
                                and not row.get('trap') and not row.get('intr'))}
    if info['class'] == 'csr':
        csr = insn >> 20
        operand = (insn >> 15) & 31
        f3 = (insn >> 12) & 7
        # Access intent comes from the encoding, not the DUT writeback index.
        encoded_rd = (insn >> 7) & 31
        read = not (f3 in (1, 5) and encoded_rd == 0)
        write = f3 in (1, 5) or operand != 0
        obs.update(csr=f'0x{csr:03x}', csr_access='read_write' if read and write else 'write' if write else 'read')
    if info['class'] == 'branch' and not row.get('trap'):
        if insn & 3 == 3:
            a, b = number(row['rs1_rdata']), number(row['rs2_rdata'])
            signed = lambda v: v - (1 << xlen) if v >> (xlen - 1) else v
            f3 = (insn >> 12) & 7
            obs['branch_taken'] = {0: a == b, 1: a != b, 4: signed(a) < signed(b),
                                   5: signed(a) >= signed(b), 6: a < b, 7: a >= b}.get(f3)
        else:
            # C.BEQZ/C.BNEZ consume RVFI rs1_rdata; target may equal fall-through.
            obs['branch_taken'] = (number(row['rs1_rdata']) == 0) == (info['mnemonic'] == 'c.beqz')
    output = [obs]
    for access, mask_name in [('read', 'mem_rmask'), ('write', 'mem_wmask')]:
        mask = number(row.get(mask_name, 0))
        if not mask:
            continue
        size, address = mask.bit_count(), number(row['mem_addr'])
        output.append({**obs, "event": "memory", "access": access, "bytes": size,
                       "alignment": alignment(address, mask, size, xlen, aligned_mem)})
    if info['dest_bank'] == 'f':
        # The FP destination is the encoding's; an integer write reported by an instruction that
        # writes an FP register contradicts the encoding, so the destination is not known.
        index = fp_destination(insn, info)
        dest = ('f', index) if index is not None and not rd else UNDETERMINED
    else:
        dest = ('x', rd) if rd else None
    if row.get('trap'):
        dest = None
    # Unknown encodings and stores cannot establish a trustworthy producer.
    if info['class'] in ('store', 'branch', 'unknown', 'fence'):
        dest = None
    return output, dest


@captured.command
def trace_platform(header, platform=None):
    """The platform whose RVFI address convention a trace uses: `platform` (a bundled platform name
    or a platform JSON file, as `rvw cosim --platform`), else the bundled platform named by the
    trace header's `core`, else None (convention unknown)."""
    import re
    from rvw.cosim import platform as platform_module
    from rvw.cosim.platform import Platform
    if platform:
        path = Path(platform)
        if path.suffix != '.json' and not path.is_file():
            path = Path(platform_module.__file__).parent / 'configs' / f'{platform}.json'
        found = Platform.load(None, captured.file(path).copy)
    else:
        core = header.get('core')
        if not isinstance(core, str) or not re.fullmatch(r'[A-Za-z0-9_-]+', core):
            return None
        bundled = Path(platform_module.__file__).parent / 'configs' / f'{core}.json'
        if not bundled.is_file():
            return None
        found = Platform.load(None, captured.file(bundled).copy)
    if found.xlen != header.get('xlen'):
        raise ValueError(f'platform {found.name} has XLEN {found.xlen}, the trace {header.get("xlen")}')
    return found


@captured.command
def functional(paths, config=None, platform=None, manifest=None, source_root=None, payload_regions=None):
    saved_paths = captured.current().files(Path(p) for p in paths)
    custom = json.loads(captured.read_text(config)) if config else None
    config = json.loads(json.dumps(DEFAULT))
    if custom:
        if custom.get('replace_defaults'):
            config = custom
        else:
            overrides = {g['name']: g for g in custom['groups']}
            config['groups'] = [overrides.pop(g['name'], g) for g in config['groups']] + list(overrides.values())
    if custom and 'sequences' in custom:
        config['sequences'] = custom['sequences']
    if manifest:
        from .isa import plan
        if not source_root:
            raise ValueError('--manifest needs --source-root for pinned opcodes')
        generated = plan(manifest, source_root)
        config['groups'] += generated['groups']
        config['isa_plan'] = generated['isa_plan']
    if payload_regions is not None:
        config['sampling_policy'] = 'payload-pc-v1'
    sequence_settings = config.get('sequences')
    if sequence_settings is not None:
        from .sequence import groups as sequence_groups
        config['groups'] += sequence_groups(sequence_settings)
    groups = config['groups']
    names = [g['name'] for g in groups]
    if len(names) != len(set(names)):
        raise ValueError('duplicate coverage group names')
    fingerprint = sha256(json.dumps(config, sort_keys=True).encode()).hexdigest()
    counters = {name: Counter() for name in names}
    traces, unknown, records, context = {}, Counter(), 0, None
    for item in saved_paths:
        path = item.copy
        if path.suffix == '.json':
            if payload_regions is not None:
                raise ValueError('payload sampling requires raw ELF-bound C2 traces')
            saved = json.loads(path.read_text())
            if saved.get('schema') != 'rvw.functional-coverage/1' or saved['config_sha256'] != fingerprint:
                raise ValueError(f'{path}: incompatible functional coverage plan')
            if traces.keys() & saved['traces'].keys():
                raise ValueError(f'{path}: duplicate trace in functional merge')
            saved_context = {(t['header']['xlen'], t['header']['isa']) for t in saved['traces'].values()}
            if len(saved_context) != 1 or (context is not None and context not in saved_context):
                raise ValueError('cannot merge different XLEN/ISA trace contexts')
            context = next(iter(saved_context))
            traces.update(saved['traces'])
            records += saved['retired']
            unknown.update(saved['unknown_encodings'])
            for name, g in saved['groups'].items():
                for hit in g['hits']:
                    counters[name][json.dumps(hit['bin'], separators=(',', ':'))] += hit['count']
            continue
        with path.open() as stream:
            first = json.loads(next(stream))
            if first.get('schema') != 'rvw.rvfi/1' or first.get('xlen') not in (32, 64):
                raise ValueError(f'{path}: expected C2 RVFI header with xlen 32 or 64')
            if manifest and (first['isa'] != config['isa_plan']['manifest']['isa']
                             or first['xlen'] != int(config['isa_plan']['manifest']['isa'][2:4])):
                raise ValueError('trace ISA contradicts manifest')
            this_context = (first['xlen'], first['isa'])
            if context is not None and this_context != context:
                raise ValueError('cannot merge different XLEN/ISA trace contexts')
            context = this_context
            file_hash = item.sha256
            if file_hash in traces:
                raise ValueError(f'{path}: duplicate trace content')
            region = payload_regions.get(file_hash) if payload_regions is not None else None
            if payload_regions is not None and (not region or region.get('policy') != 'payload-pc-v1'
                    or first.get('elf_sha256') != region.get('elf_sha256')):
                raise ValueError('payload region does not bind the trace ELF')
            plat = trace_platform(first, platform)
            aligned_mem = plat.aligned_mem if plat else None
            traces[file_hash] = {"path": item.resolved, "header": first,
                                 "platform": plat.name if plat else None,
                                 **({'payload_region': region, 'payload_visits': {}} if region is not None else {}),
                                 "address_convention": {True: "aligned_mem", False: "byte", None: "unknown"}[aligned_mem]}
            previous, order = None, -1
            history = []
            from .semantic import Observer
            semantic = Observer()
            for line_no, line in enumerate(stream, 2):
                row = json.loads(line)
                if 'event' not in row:
                    if row['order'] <= order:
                        raise ValueError(f'{path}:{line_no}: non-increasing RVFI order')
                    order = row['order']
                    if region is not None and not any(start <= number(row['pc']) < end for start,end in region['ranges']):
                        previous = None
                        history.clear()
                        semantic = Observer()
                        continue
                    if region is not None:
                        visits = traces[file_hash]['payload_visits']
                        pc = hex(number(row['pc']))
                        visits[pc] = visits.get(pc,0)+1
                    records += 1
                observed, previous = observations(row, first['xlen'], previous, aligned_mem)
                if sequence_settings is not None:
                    from .sequence import observe as observe_sequence
                    if 'event' not in row:
                        observed += observe_sequence(history, row, decode(number(row['insn']), first['xlen']),
                                                     previous, sequence_settings.get('distances', [1, 2, 4]),
                                                     sequence_settings.get('kinds'))
                    elif row['event'] not in ('irq', 'end'):
                        history.clear()
                if 'isa_plan' in config:
                    from .isa import observe_encoding
                    for obs in observed:
                        observe_encoding(obs, config['isa_plan'])
                    observed += semantic.observe(row, observed, config['isa_plan'], first['xlen'])
                for obs in observed:
                    if obs['event'] == 'retire' and obs['mnemonic'] == 'unknown':
                        unknown[row['insn']] += 1
                    for group in groups:
                        # Every instruction-derived group defaults to retire records only.
                        condition = group.get('when', {'event': 'retire'})
                        if 'event' not in condition and obs['event'] != 'retire':
                            continue
                        if matches(obs, condition) and all(f in obs for f in group['fields']):
                            key = json.dumps([obs[f] for f in group['fields']], separators=(',', ':'))
                            counters[group['name']][key] += 1
    result = {}
    for group in groups:
        counter = counters[group['name']]
        bins = group.get('bins', list(product(*group['domains'])) if 'domains' in group else [])
        expected = {json.dumps(list(b), separators=(',', ':')) for b in bins}
        result[group['name']] = {"fields": group['fields'],
            "hits": [{"bin": json.loads(k), "count": v} for k, v in sorted(counter.items())],
            "holes": [json.loads(k) for k in sorted(expected - counter.keys())],
            "expected_bins": len(expected), "observed_bins": len(counter),
            "expected_hit": len(expected & counter.keys())}
        if 'classifications' in group:
            result[group['name']]['classifications'] = [dict(row, count=counter.get(
                json.dumps(row['bin'], separators=(',', ':')), 0)) for row in group['classifications']]
    return {"schema": "rvw.functional-coverage/1", "config": config, "config_sha256": fingerprint,
            "traces": traces, "retired": records, "groups": result,
            "unknown_encodings": dict(unknown),
            "notes": ["Default domains are a coverage plan, not claims of ISA support or reachability.",
                      "C2 trap events without mode retain mode=unknown; mode is not inferred.",
                      "RVFI intr marks trap-handler entry, including synchronous traps; actual interrupt causes use C2 trap events.",
                      "retired counts C2 instruction records, including trap=true records.",
                      "CSR/mnemonic groups without declared bins report observations, not a completeness percentage.",
                      "rd_x0 records RVFI rd=0, which also denotes instructions without a destination.",
                      "dependency: an FP destination is the instruction encoding's rd (C2 rd is the integer write); "
                      "when the trace reports an integer rd for an FP-destination instruction, the next "
                      "instruction's back_to_back is undetermined.",
                      "Memory alignment uses each trace's platform address convention (aligned_mem: mem_addr plus "
                      "the mask's lane offset); a lane-shifted mask under an unknown or byte convention is undetermined."]}
