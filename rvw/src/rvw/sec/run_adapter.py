"""`rvw.sec-case/1` adapter through a project's own C1 run adapter.

python -m rvw.sec.run_adapter --binding run.json --template case.S REQUEST OUT

For cores that the native harness cannot drive (write-back caches, no RVFI, native refill
buses), the project's C1 adapter already owns the buses, the C2 trace and the probes. This
adapter renders the case like `core_adapter`, makes the Spike reference, then runs
`ADAPTER run --elf ELF --out DIR --rvfi-trace --probes --json` and reads `rvfi.jsonl` and
`probe-events.jsonl`. Observations: `cycles`, `retire_cycles`, the probe channels, and
`probe_counters` (whole-run totals: the C1 stream keeps counter totals only). Bus traces
are not available through C1 and are an error.
"""
import argparse
import json
import os
from pathlib import Path
import sys
from rvw.cosim.elf import Elf
from rvw.probes.events import read as read_probes
from . import core_adapter
from .common import native

SCHEMA = 'rvw.sec-run/1'
BUS_CHANNELS = ('dbus_trace', 'ibus_trace', 'dbus_addresses', 'bus_timing', 'bus_handshakes')


def load(path):
    """`rvw.sec-run/1`: name, adapter (argv, relative to the file), platform, optional config,
    run_args, link, march, isa, timeout."""
    path = Path(path).resolve()
    b = json.loads(path.read_text())
    if b.get('schema') != SCHEMA:
        raise ValueError(f'run binding schema must be {SCHEMA}')
    if not isinstance(b.get('adapter'), list) or not b['adapter'] or not b.get('platform'):
        raise ValueError('run binding needs an adapter argv list and a platform')
    def where(p, *, command=False):
        text = os.path.expandvars(p)
        if '$' in text:
            raise ValueError(f'unset environment variable in {p}')
        q = Path(text)
        if command and '/' not in text and not (path.parent/q).is_file():
            return text
        return str(q if q.is_absolute() else (path.parent/q).resolve())
    b['adapter'] = [where(b['adapter'][0], command=True)] + list(b['adapter'][1:])
    b['platform'] = where(b['platform'])
    b['_dir'] = path.parent
    return b


def run_argv(binding, elf, out):
    argv = list(binding['adapter']) + ['run', '--elf', str(elf), '--out', str(out), '--rvfi-trace', '--probes', '--json']
    if binding.get('config'):
        argv += ['--config', binding['config']]
    return argv + [str(a) for a in binding.get('run_args', [])]


def cut_trace(source, path, tohost):
    """Copy a C2 trace up to and including the first store to `tohost`, then its end event.
    The C1 run stops some cycles after that store, so later commits can follow it; the
    reference stops there."""
    lines = Path(source).read_text().splitlines()
    kept, end = lines[:1], None
    for line in lines[1:]:
        r = json.loads(line)
        if 'event' in r:
            if r['event'] == 'end':
                end = line
            elif end is None:
                kept.append(line)
            continue
        if end is None:
            kept.append(line)
            if r.get('mem_wmask') and int(r.get('mem_addr', '0x0'), 16) == tohost:
                end = ''
    last = [x for x in lines if '"event": "end"' in x or '"event":"end"' in x]
    Path(path).write_text('\n'.join(kept + last[-1:])+'\n')


def result_from_run(folder, elf):
    """The C1 run as the dict that `core_adapter.observe` reads."""
    folder = Path(folder)
    trace = folder/'cut.jsonl' if (folder/'cut.jsonl').exists() else folder/'rvfi.jsonl'
    rows = [json.loads(x) for x in trace.read_text().splitlines()[1:] if x.strip()]
    retired = []
    for r in rows:
        if 'event' in r:
            continue
        retired.append(dict(cycle=int(r['cycle']), pc=int(r['pc'], 16), insn=int(r['insn'], 16),
                            mode=r.get('mode'), mem_addr=int(r.get('mem_addr', '0x0'), 16),
                            mem_rmask=r.get('mem_rmask', 0), mem_wmask=r.get('mem_wmask', 0)))
    result = dict(retired=retired, bus=[], responses=[], done=None,
                  tohost_address=Elf(elf).symbols.get('tohost'), probe_sites=[], probe_rows=[], counters={})
    events = folder/'probe-events.jsonl'
    if events.exists():
        stream = read_probes(events)
        result['probe_sites'] = [dict(id=p.id, kind=p.kind, name=p.name, fields=[[n, w, n] for n, w in p.fields])
                                 for p in stream.probes]
        result['probe_rows'] = [(c, i, v) for c, i, v in stream.rows if stream.probes[i].kind != 'counter']
        result['counters'] = stream.counters
    return result


def observe(result, names, start_pc=None, mode=None):
    if bad := [n for n in names if n in BUS_CHANNELS]:
        raise ValueError(f'{", ".join(bad)} need the native harness; a C1 run gives no bus trace')
    obs = core_adapter.observe(result, [n for n in names if n != 'probe_counters'], start_pc, None, mode)
    if 'probe_counters' in names:
        if not result['probe_sites']:
            raise ValueError('probe_counters needs probe sites in the run')
        obs['probe_counters'] = dict(result['counters'])
    return {n: obs[n] for n in names}


def run_case(binding_path, template, request_path, out):
    out = Path(out); request = json.loads(Path(request_path).read_text())
    binding = load(binding_path)
    source = out/'case.S'
    source.write_text(core_adapter.render(template, request))
    elf = core_adapter.compile_elf(source, out, binding)
    core_adapter.reference(elf, out, binding)
    folder = out/'rtl'
    log = native(run_argv(binding, elf, folder), binding['_dir'], timeout=binding.get('timeout', 900))
    (out/'run.log').write_text(log)
    c1 = json.loads((folder/'result.json').read_text())
    status = c1.get('status')
    cut_trace(folder/'rvfi.jsonl', folder/'cut.jsonl', Elf(elf).symbols.get('tohost'))
    result = result_from_run(folder, elf)
    observations = observe(result, request.get('observations', ['cycles']), request.get('contract_start_pc'),
                           request.get('observer_mode'))
    response = dict(complete=status == 'pass', reset_complete=True, reference_c2='reference.jsonl',
                    rtl_c2='rtl/cut.jsonl', observations=observations, rtl_status=status,
                    cycles=c1.get('cycles'), core=binding.get('name'), rtl_identity=c1.get('rtl_sha256'))
    (out/'response.json').write_text(json.dumps(response, indent=2)+'\n')
    return response


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--binding', required=True); p.add_argument('--template', required=True)
    p.add_argument('request'); p.add_argument('out')
    a = p.parse_args(argv)
    run_case(a.binding, a.template, a.request, a.out)
    return 0


if __name__ == '__main__':
    sys.exit(main())
