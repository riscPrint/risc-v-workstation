"""`rvw.sec-case/1` adapter for a core bound with `rvw.sec-core/1`.

python -m rvw.sec.core_adapter --binding core.json --template case.S REQUEST OUT

It renders the case program into the project template, builds the ELF, makes the Spike
reference trace with `rvw cosim generate`, runs the native RTL harness and writes
`response.json`. Observations come only from the RTL run.
"""
import argparse
import json
import os
from pathlib import Path
import shutil
import sys
from . import rtl
from . import probe_events
from .common import native

CHANNELS = ('cycles', 'retire_cycles', 'dbus_trace', 'ibus_trace', 'dbus_addresses', 'bus_timing',
            'bus_handshakes', 'branch_events', 'cache_events', 'tlb_events', 'probe_events', 'probe_counters')


def render(template, request, xlen=32):
    if xlen not in (32, 64):
        raise ValueError("XLEN must be 32 or 64")
    secret, public = request['secret'], request.get('public', {})
    lines, data = [], []
    for source in (public.get('registers', {}), secret if isinstance(secret, dict) else {}):
        for k, v in source.items():
            if k.startswith('@'):
                data += [f'.globl {k[1:]}', '.balign 4', f'{k[1:]}:'] + [f'.word {int(w)}' for w in (v if isinstance(v, list) else [v])]
            else:
                # Fixed length for every value: the public instruction stream must not depend on it.
                if xlen == 64:
                    # Fixed byte construction retains all bits and has constant length.
                    value = int(v) & ((1 << 64) - 1)
                    lines.append(f'addi {k}, x0, {(value >> 56) & 255}')
                    for shift in range(48, -1, -8):
                        lines += [f'slli {k}, {k}, 8', f'addi {k}, {k}, {(value >> shift) & 255}']
                    continue
                v = int(v) & 0xffffffff
                hi, lo = (v + 0x800) >> 12 & 0xfffff, (v & 0xfff) - ((v & 0x800) << 1)
                lines += [f'lui {k}, {hi}', f'addi {k}, {k}, {lo}']
    if not isinstance(secret, dict):
        raise ValueError('secret must map registers or @data labels to values')
    text = Path(template).read_text()
    for marker, body in (('# RVW_SETUP', lines), ('# RVW_PROGRAM', request['program']), ('# RVW_DATA', data)):
        if marker not in text:
            raise ValueError(f'template lacks {marker}')
        text = text.replace(marker, '\n'.join('  '+x if not x.endswith(':') and not x.startswith('.') else x for x in body))
    return text


def compile_elf(source, out, binding):
    prefix = os.environ.get('RISCV_PREFIX', 'riscv64-unknown-elf-')
    gcc = shutil.which(prefix+'gcc') or shutil.which(prefix+'gcc', path='/opt/homebrew/opt/riscv-gnu-toolchain/bin')
    if not gcc:
        raise ValueError('RISC-V GCC not found; set RISCV_PREFIX or PATH')
    link = binding['_dir']/binding.get('link', '../programs/link.ld')
    elf = out/'case.elf'
    march = binding.get('march', 'rv32im_zicsr')
    abi = 'lp64' if march.lower().startswith('rv64') else 'ilp32'
    native([gcc, f'-march={march}', f'-mabi={abi}', '-nostdlib', '-T', str(link),
            str(source), '-o', str(elf)], out)
    return elf


def reference(elf, out, binding):
    rvw = Path(sys.executable).parent/'rvw'
    path = out/'reference.jsonl'
    native([str(rvw), 'cosim', 'generate', '--elf', str(elf), '--core', binding.get('name', 'core'),
            '--platform', str(binding['platform']), '--out', str(path), '--json'], out, timeout=120)
    return path


def window(result, start_pc):
    rows = rtl.cut(result)
    if start_pc is None:
        return rows, 0
    start = int(start_pc, 0) if isinstance(start_pc, str) else start_pc
    for i, r in enumerate(rows):
        if r['pc'] == start:
            return rows[i:], r['cycle']
    raise ValueError('contract start PC was not retired by the RTL')


def side_channel(event):
    """A cache event without its line or word contents. Contents are architectural data, not a
    side channel, and the fetched lines hold the secret setup immediates."""
    if event['kind'] == 'cache':
        event.pop('data', None)
    return event


def observe(result, names, start_pc=None, probe=None, mode=None):
    rows, origin = window(result, start_pc)
    if mode is not None:
        # Only the observer privilege's retirements are visible to it.
        rows = [r for r in rows if r.get('mode') == mode]
        origin = rows[0]['cycle'] if rows else origin
    end = rows[-1]['cycle'] if rows else origin
    bus = [e for e in result['bus'] if origin <= e['cycle'] <= end]
    obs = {}
    for name in names:
        if name == 'cycles':
            obs[name] = end-origin
        elif name == 'retire_cycles':
            obs[name] = [b['cycle']-a['cycle'] for a, b in zip(rows, rows[1:])]
        elif name in ('dbus_trace', 'ibus_trace'):
            kind = name.split('_')[0]
            obs[name] = [[e['cycle']-origin, e['address'], e['write']] for e in bus if e['bus'] == kind]
        elif name == 'dbus_addresses':
            obs[name] = [[e['address'], e['write']] for e in bus if e['bus'] == 'dbus']
        elif name == 'bus_timing':
            obs[name] = [[e['cycle']-origin, e['bus']] for e in bus]
        elif name == 'bus_handshakes':
            # Cycle-accurate request and response edges of every bus.
            edges = [[e['cycle']-origin, e['bus'], 'cmd'] for e in bus] + \
                    [[e['cycle']-origin, e['bus'], 'rsp'] for e in result.get('responses', []) if origin <= e['cycle'] <= end]
            obs[name] = sorted(edges)
        elif name in ('branch_events', 'cache_events', 'tlb_events', 'probe_events', 'probe_counters'):
            if not result.get('probe_sites'):
                raise ValueError(f'{name} needs probe sites in the RTL (SpinalProbes wires or binding events)')
            events = [e for e in probe_events.collect(result) if origin <= e['cycle'] <= end]
            if name == 'probe_counters':
                totals = {}
                for e in events:
                    if e['kind'] == 'counter':
                        totals[e['name']] = totals.get(e['name'], 0)+e.get('inc', 1)
                obs[name] = totals
                continue
            kind = {'branch_events': 'branch', 'cache_events': 'cache', 'tlb_events': 'tlb'}.get(name)
            obs[name] = [side_channel(dict(e, cycle=e['cycle']-origin)) for e in events
                         if (e['kind'] == kind if kind else e['kind'] != 'counter')]
        else:
            raise ValueError(f'unknown observation channel {name}; choose from {", ".join(CHANNELS)}')
    return obs


def run_case(binding_path, template, request_path, out, work=None):
    out = Path(out); request = json.loads(Path(request_path).read_text())
    binding = rtl.load(binding_path)
    work = Path(work or os.environ.get('RVW_SEC_WORK') or Path.home()/'.cache/rvw/sec')
    source = out/'case.S'
    source.write_text(render(template, request))
    elf = compile_elf(source, out, binding)
    ref = reference(elf, out, binding)
    exe = rtl.build(binding, work)
    result = rtl.simulate(binding, exe, elf, out/'rtl')
    status = rtl.c2(result, out/'rtl.jsonl', elf, binding, binding.get('isa', 'rv32im'))
    probe = None
    observations = observe(result, request.get('observations', ['cycles']), request.get('contract_start_pc'), probe,
                           request.get('observer_mode'))
    commit = binding['retire']
    keys = (['pc', 'insn'] + (['mode'] if commit.get('mode') else [])) if commit['kind'] == 'commit' else None
    response = dict(complete=status == 'pass', reset_complete=True, reference_c2='reference.jsonl',
                    rtl_c2='rtl.jsonl', observations=observations, rtl_status=status,
                    cycles=result['cycles'], core=binding.get('name'), rtl_identity=result['rtl_identity'])
    if keys:
        response['c2_keys'] = keys
    (out/'response.json').write_text(json.dumps(response, indent=2)+'\n')
    return response


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--binding', required=True); p.add_argument('--template', required=True)
    p.add_argument('--work'); p.add_argument('request'); p.add_argument('out')
    a = p.parse_args(argv)
    try:
        run_case(a.binding, a.template, a.request, a.out, a.work)
    except (ValueError, OSError) as exc:
        print(json.dumps(dict(status='error', error=str(exc),
                              hint='Supply readable binding, template and request files. Set RVW_SEC_RTL to the generated RTL root named by the binding.')),
              file=sys.stderr)
        return 2
    return 0


if __name__ == '__main__':
    sys.exit(main())
