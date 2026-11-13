"""Project-owned CSR model and independent artifact generation.

The interface is a completed architectural transaction, not a decoder bus.
"""
from __future__ import annotations
import json
import re
from pathlib import Path

MODES = {'U': 0, 'S': 1, 'M': 3}
POLICIES = {'RW', 'RO', 'WARL', 'WLRL', 'WPRI'}


def integer(v):
    return int(v, 0) if isinstance(v, str) else int(v)


def load(path):
    obj = json.loads(Path(path).read_text())
    if obj.get('schema') == 'rvw.csr-selection/1':
        from .csr_catalog import materialize
        obj = materialize(obj)
    if obj.get('schema') != 'rvw.csr/1' or obj.get('xlen') not in (32, 64):
        raise ValueError('expected rvw.csr/1 and xlen 32 or 64')
    if not obj.get('csrs'):
        raise ValueError('declare at least one CSR')
    width = obj['xlen']
    seen = set()
    names = set()
    for csr in obj['csrs']:
        if set(csr) - {'name', 'address', 'reset', 'privilege', 'present', 'read_only', 'fields', 'assembly_safe', 'reset_known'}:
            raise ValueError('unsupported CSR attribute')
        name = csr['name']
        if not re.fullmatch(r'[A-Za-z_][A-Za-z0-9_]*', name) or name in names:
            raise ValueError('invalid or duplicate CSR name')
        names.add(name)
        csr['address'] = integer(csr['address'])
        if not 0 <= csr['address'] < 4096 or csr['address'] in seen:
            raise ValueError('invalid or duplicate CSR address')
        seen.add(csr['address'])
        csr['reset'] = integer(csr['reset'])
        if not 0 <= csr['reset'] < 1 << width or csr['privilege'] not in MODES:
            raise ValueError('invalid reset or privilege')
        used = 0
        for field in csr.get('fields', []):
            if set(field) - {'name', 'lsb', 'width', 'access', 'legal', 'legalize', 'effect'}:
                raise ValueError('unsupported field attribute')
            lo, bits = field['lsb'], field['width']
            if lo < 0 or bits < 1 or lo + bits > width:
                raise ValueError('invalid field range')
            mask = ((1 << bits)-1) << lo
            if used & mask:
                raise ValueError('overlapping fields')
            used |= mask
            access = field['access']
            if set(access) != set(MODES) or any(p not in POLICIES for p in access.values()):
                raise ValueError('declare U/S/M field access')
            field['legal'] = [integer(x) for x in field.get('legal', [])]
            field['legalize'] = {integer(k): integer(v) for k, v in field.get('legalize', {}).items()}
            if any(not 0 <= v < 1 << bits for v in field['legal']):
                raise ValueError('legal value exceeds field')
            if {'WARL', 'WLRL'} & set(access.values()):
                if not field['legal'] or ((csr['reset'] >> lo) & ((1 << bits)-1)) not in field['legal']:
                    raise ValueError('legal values must include reset')
            if any(k < 0 or k >= 1 << bits or v not in field['legal'] for k, v in field['legalize'].items()):
                raise ValueError('invalid legalization table')
            if field.get('effect', 'none') not in ('none', 'w1c', 'read_clear'):
                raise ValueError('unsupported field side effect')
        if type(csr.get('reset_known', True)) is not bool:
            raise ValueError('reset_known must be boolean')
        if not csr.get('reset_known', True):
            if csr['privilege'] != 'M' or used != (1 << width)-1 or csr.get('read_only') or csr['address'] >> 10 == 3 or any(
                f['access']['M'] != 'RW' or f.get('effect', 'none') != 'none'
                for f in csr.get('fields', [])):
                raise ValueError('unknown reset requires full-width ordinary M-mode writes')
    return obj


def step(csr, state, txn, width):
    """Independent oracle. Hardware clear precedes hardware set; hardware wins."""
    trap = not csr.get('present', True) or txn['privilege'] < MODES[csr['privilege']]
    mode = next((k for k, v in MODES.items() if v == txn['privilege']), None)
    trap |= mode is None
    if txn['write'] and (csr['address'] >> 10 == 3 or csr.get('read_only', False)):
        trap = True
    result = state
    for f in csr.get('fields', []):
        lo, bits = f['lsb'], f['width']
        mask = (1 << bits)-1
        old = state >> lo & mask
        value = txn['data'] >> lo & mask
        policy = f['access'].get(mode, 'RO')
        new = old
        if not trap:
            if txn['read'] and f.get('effect') == 'read_clear':
                new = 0
            if txn['write'] and policy not in ('RO', 'WPRI'):
                if policy == 'WLRL' and value not in f['legal']:
                    trap = True
                elif policy == 'WARL' and value not in f['legal']:
                    new = f['legalize'].get(value, old)
                else:
                    new = old & ~value if f.get('effect') == 'w1c' else value
        result = (result & ~(mask << lo)) | (new << lo)
    if trap:
        result = state
    result = (result & ~txn.get('hw_clear', 0)) | txn.get('hw_set', 0)
    return trap, result & ((1 << width)-1)


def monitor(obj):
    w = obj['xlen']
    csrs = obj['csrs']
    ports = ', '.join(f'input [{w-1}:0] state_{c["name"]}' for c in csrs)
    lines = [f'module rvw_csr(input clk, reset, valid, rd, wr, input [1:0] privilege,',
             f'input [11:0] address, input [{w-1}:0] data, rdata, hw_set, hw_clear,',
             f'input trap, {ports});', 'reg initialized = 0;',
             'always @(posedge clk) begin', '  if (!initialized) assume(reset);', '  initialized <= 1;', 'end']
    for c in csrs:
        n = c['name']
        lines += [f'reg known_{n} = {int(c.get("reset_known", True))};', f'reg [{w-1}:0] expected_{n}, next_{n};', f'reg denied_{n};', 'always @* begin',
                  f' next_{n} = expected_{n};',
                  f' denied_{n} = {int(not c.get("present", True))} || privilege < 2\'d{MODES[c["privilege"]]} || privilege == 2;',
                  f' if (wr && {int(c.get("read_only", False) or c["address"] >> 10 == 3)}) denied_{n} = 1;']
        # WLRL is a declared reject-illegal project policy.
        for f in c.get('fields', []):
            hi, lo = f['lsb'] + f['width']-1, f['lsb']
            sl = f'[{hi}:{lo}]'
            legal = ' || '.join(f'data{sl} == {f["width"]}\'d{v}' for v in f['legal']) or '1'
            for mode, policy in f['access'].items():
                if policy == 'WLRL':
                    lines += [f' if (wr && privilege == {MODES[mode]} && !({legal})) denied_{n} = 1;']
            if f.get('effect') == 'read_clear':
                lines += [f' if (rd) next_{n}{sl} = 0;']
            for mode, policy in f['access'].items():
                if policy in ('RO', 'WPRI'):
                    continue
                value = f'expected_{n}{sl} & ~data{sl}' if f.get('effect') == 'w1c' else f'data{sl}'
                lines += [f' if (wr && privilege == {MODES[mode]}) begin']
                if policy == 'WARL':
                    lines += [f'   if ({legal}) next_{n}{sl} = {value};', '   else begin',
                              f'     next_{n}{sl} = expected_{n}{sl};']
                    for a, b in f['legalize'].items():
                        lines += [f'     if (data{sl} == {f["width"]}\'d{a}) next_{n}{sl} = {f["width"]}\'d{b};']
                    lines += ['   end']
                else:
                    lines += [f'   next_{n}{sl} = {value};']
                lines += [' end']
        lines += [f' if (denied_{n}) next_{n} = expected_{n};', 'end', 'always @(posedge clk) begin',
                  f' if (reset) begin expected_{n} <= {w}\'d{c["reset"]}; known_{n} <= {int(c.get("reset_known", True))}; end',
                  ' else begin', f'  if (initialized && known_{n}) assert(state_{n} == expected_{n});',
                  f'  if (valid && address == 12\'d{c["address"]}) begin',
                  f'   assert(trap == denied_{n});',
                  f'   if (rd && !denied_{n} && known_{n}) assert(rdata == expected_{n});',
                  f'   if (wr && !denied_{n}) known_{n} <= 1;',
                  f'   expected_{n} <= (next_{n} & ~hw_clear) | hw_set;', '  end', ' end', 'end']
    return '\n'.join(lines + ['endmodule', ''])


def assembly(c, width):
    """One standalone M-mode program. Only opt-in safe CSRs get destructive writes."""
    addr = hex(c['address'])
    lines = ['.option norvc', '.section .text.init', '.globl _start', '_start:',
             'la t0, handler', 'csrw mtvec, t0', 'li s0, 0', 'li s1, 0']
    if not c.get('present', True):
        lines += ['li s1, 1', f'csrr t0, {addr}', 'li t0, 1', 'bne s0, t0, fail']
    else:
        if not c.get('reset_known', True) and c.get('assembly_safe', False):
            lines += [f'li t0, {c["reset"]}', f'csrw {addr}, t0']
        lines += [f'csrr s2, {addr}']
        if c.get('assembly_safe', False):
            _, state = step(c, c['reset'], dict(read=True, write=False, data=0, privilege=3), width)
            lines += [f'li t0, {c["reset"]}', 'bne s2, t0, fail']
            for value in (0, (1 << width)-1, c['reset']):
                trap, state = step(c, state, dict(read=False, write=True, data=value, privilege=3), width)
                lines += [f'li s1, {int(trap)}', 'li s0, 0', f'li t0, {value}', f'csrw {addr}, t0',
                          f'li t0, {int(trap)}', 'bne s0, t0, fail', 'li s1, 0',
                          f'csrr t1, {addr}', f'li t0, {state}', 'bne t1, t0, fail']
                _, state = step(c, state, dict(read=True, write=False, data=0, privilege=3), width)
    lines += ['li t0, 1', 'j finish', 'fail:', 'li t0, 3', 'finish:', 'la t1, tohost',
              'sw t0, 0(t1)', '1: j 1b', '.balign 4', 'handler:', 'beqz s1, fail',
              'csrr t0, mcause', 'li t1, 2', 'bne t0, t1, fail', 'addi s0, s0, 1',
              'csrr t0, mepc', 'addi t0, t0, 4', 'csrw mepc, t0', 'mret',
              '.section .tohost,"aw",@progbits', '.balign 8', '.globl tohost',
              'tohost: .dword 0', '.globl fromhost', 'fromhost: .dword 0', '']
    return '\n'.join(lines)


def generate(path, out):
    obj = load(path)
    out = Path(out)
    out.mkdir(parents=True, exist_ok=False)
    (out/'model.json').write_text(json.dumps(obj, indent=2)+'\n')
    (out/'csr.sv').write_text(monitor(obj))
    if 'binding' in obj:
        binding = obj['binding']
        if not re.fullmatch(r'[A-Za-z_][A-Za-z0-9_]*', binding['top']):
            raise ValueError('invalid binding top')
        sources = [(Path(path).resolve().parent / p).resolve() for p in binding['sources']]
        if not sources or any(not p.is_file() for p in sources):
            raise ValueError('binding sources must exist')
        names = [p.name for p in sources]
        if len(set(names + ['csr.sv'])) != len(names) + 1:
            raise ValueError('binding source basenames must be distinct')
        script = 'read -formal -sv csr.sv ' + ' '.join(names)
        files = '\n'.join(str(p) for p in sources)
        (out/'csr.sby').write_text(
            '[options]\nmode bmc\ndepth 20\n[engines]\nsmtbmc z3\n[script]\n' +
            script + '\nprep -top ' + binding['top'] + '\n[files]\ncsr.sv\n' + files + '\n')
    groups = [{'name': c['name'], 'fields': ['csr', 'csr_access', 'mode'],
               'when': {'class': 'csr', 'csr': f'0x{c["address"]:03x}'},
               'domains': [[f'0x{c["address"]:03x}'], ['read', 'write', 'read_write'], ['U', 'S', 'M']]} for c in obj['csrs']]
    (out/'coverage.json').write_text(json.dumps({'groups': groups}, indent=2)+'\n')
    for c in obj['csrs']:
        (out/(c['name']+'.S')).write_text(assembly(c, obj['xlen']))
    result = {'schema': 'rvw.csr-generation/1', 'status': 'generated',
              'csrs': len(obj['csrs']), 'limitations': [
                  'Bind completed transactions and independent internal state in a project wrapper.',
                  'No solver, compiler, C1 adapter or Spike was run.',
                  'Assembly checks M-mode only; destructive writes require assembly_safe.',
                  'Aliases and autonomous updates outside selected transactions are not supported.']}
    (out/'result.json').write_text(json.dumps(result, indent=2)+'\n')
    return result


def run(args):
    try:
        print(json.dumps(generate(args.model, args.out)))
        return 0
    except (ValueError, KeyError, TypeError, OSError) as exc:
        print(f'CSR generation error: {exc}')
        return 2
