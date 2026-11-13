"""Information-flow tracking on a whole core in the native harness.

The core RTL becomes a Yosys gate netlist with a Boolean taint shadow (`ift.shadow`).
The harness RAM keeps a taint mask per word: loads return it, stores write the stored
data's taint. A policy names secret memory regions (by ELF symbol or address), secret
registers (netnames such as a CSR), and sinks (bus address, data and handshake outputs).
"""
import hashlib
import json
from pathlib import Path
from rvw.cosim.elf import Elf
from . import rtl
from .common import native, publish
from .ift import shadow


def regions(policy, elf, binding):
    """Per-word taint masks from the policy's memory regions."""
    e = Elf(elf)
    words = {}
    for region in policy.get('memory_regions', []):
        if 'symbol' in region:
            if region['symbol'] not in e.symbols:
                raise ValueError(f'secret symbol {region["symbol"]} is not in the ELF')
            base = e.symbols[region['symbol']]
        else:
            base = rtl.number(region['base'])
        size = rtl.number(region['size'])
        if base % 4 or size % 4 or size <= 0:
            raise ValueError('secret memory regions must be word aligned')
        if base < binding['ram_base'] or base+size > binding['ram_base']+binding['ram_size']:
            raise ValueError('secret memory region outside binding RAM')
        for a in range(base, base+size, 4):
            words[(a-binding['ram_base'])//4] = rtl.number(region.get('mask', 0xffffffff))
    return words


# X constants become 0, like the two-state Verilator run. Async resets become synchronous;
# the harness holds reset for several clock cycles, so the sampled behavior is the same.
FLOW = ('proc; async2sync; flatten; delete t:$scopeinfo; memory_map; opt; techmap; opt; simplemap; dffunmap; setundef -zero -undriven; '
        'opt_clean; write_json mapped.json')


def netlist(binding, work):
    """Gate-level JSON of the core, cached by RTL content."""
    text = ''.join(p.read_text() for p in binding['rtl'])
    key = hashlib.sha256((text+FLOW).encode()).hexdigest()[:20]
    folder = Path(work)/f'netlist-{key}'
    if not (folder/'mapped.json').exists():
        folder.mkdir(parents=True, exist_ok=True)
        files = ' '.join(f'"{p}"' for p in binding['rtl'])
        native(['yosys', '-q', '-p', f'read_verilog -sv {files}; hierarchy -check -top {binding["top"]}; '+FLOW],
               folder, timeout=900)
    design = json.loads((folder/'mapped.json').read_text())
    return design


def _run(binding_path, policy_path, elf, out, mode='precise', work=None, soc=None):
    out = Path(out).resolve(); out.mkdir(parents=True, exist_ok=False)
    binding = rtl.load(binding_path)
    policy = json.loads(Path(policy_path).read_text())
    (out/'policy.json').write_text(json.dumps(policy, indent=2))
    import os
    work = Path(work or os.environ.get('RVW_SEC_WORK') or Path.home()/'.cache/rvw/sec')
    sinks = policy.get('sinks', [])
    if not sinks or any('signal' not in s for s in sinks):
        raise ValueError('policy needs sinks with a signal name')
    progress(out, 'netlist', mode=mode)
    design = netlist(binding, work)
    top = binding['top']
    mod = design['modules'][top]
    for s in sinks:
        for name in (s['signal'], s.get('when')):
            if name and (name not in mod['ports'] or mod['ports'][name]['direction'] != 'output'):
                raise ValueError(f'sink {name} must be a top-level output port')
    from . import bindings
    policy['memory_regions'] = bindings.memory(policy, soc or binding.get('soc'))
    q = {c['connections']['Q'][0] for c in mod['cells'].values() if c['type'] == '$_DFF_P_'}
    flops = {n for n, d in mod['netnames'].items() if d['bits'] and all(b in q for b in d['bits'])}
    csrs = bindings.csr_signals(policy.get('csrs', []), mod['netnames'], binding.get('csr_signals'), flops, set(mod['ports']))
    sources = list(policy.get('sources', [])) + [n for n in csrs.values() if n not in policy.get('sources', [])]
    words = regions(policy, elf, binding)
    shadow_policy = dict(clock=binding['clock'], reset=binding['reset'], sources=sources,
                         sinks=[s['signal'] for s in sinks], allow_memory_sources=bool(words))
    progress(out, 'shadow', cells=len(mod['cells']), ports=len(mod['ports']), mode=mode)
    text, prefix = shadow(design, top, shadow_policy, mode)
    widths = {n: (p['direction'], len(p['bits'])) for n, p in mod['ports'].items()}
    progress(out, 'compile', cells=len(mod['cells']), shadow_bytes=len(text.encode()), mode=mode)
    exe = rtl.build(binding, work, ift=(prefix, [(s['signal'], s.get('when')) for s in sinks], widths),
                    shadow_text=text)
    progress(out, 'simulate', max_cycles=binding.get('max_cycles',100000), mode=mode)
    result = rtl.simulate(binding, exe, elf, out/'rtl', taint_words=words)
    status = rtl.c2(result, out/'rtl.jsonl', elf, binding, binding.get('isa', 'rv32im'))
    retired = rtl.cut(result)
    # Without a retirement port in the shadow netlist, the tohost store bounds the window.
    end = retired[-1]['cycle'] if retired else max(result['done'] or 0, 0)
    findings = {}
    for hit in result['sinks']:
        if hit['cycle'] > end:
            continue  # after the tohost store retires
        s = sinks[hit['sink']]['signal']
        f = findings.setdefault(s, dict(sink=s, when=sinks[hit['sink']].get('when'), first_cycle=hit['cycle'], cycles=0))
        f['cycles'] += 1
    for f in findings.values():
        # The last retirement at or before the first tainted sink sample.
        before = [r for r in retired if r['cycle'] <= f['first_cycle']]
        f['last_retired_pc'] = hex(before[-1]['pc']) if before else None
    complete = status == 'pass' and end > 0
    return publish(out, 'ift-core', sorted(findings.values(), key=lambda f: f['first_cycle']), complete,
                   mode=mode, core=binding.get('name'), elf=str(elf), rtl_status=status,
                   secret_words=len(words), sources=sources, csrs=csrs, memory_regions=policy['memory_regions'],
                   tainted_memory=dict(words=len(result['tainted_words']),
                                       propagated=[[hex(binding['ram_base']+4*i), hex(m)]
                                                   for i, m in result['tainted_words'] if i not in words][:64]),
                   checked_cycles=end,
                   path_kind='dynamic Boolean taint at top-level sinks; no source-level provenance')


def progress(out, phase, **cost):
    import sys
    record = dict(phase=phase, **cost)
    (Path(out)/'progress.json').write_text(json.dumps(record, indent=2)+'\n')
    print('security flow: '+json.dumps(record), file=sys.stderr, flush=True)


def run(binding_path, policy_path, elf, out, mode='precise', work=None, soc=None, timeout=110):
    import time
    from .budget import limit, BudgetExpired
    if not 0 < timeout <= 120:
        raise ValueError('flow timeout must be greater than zero and at most 120 seconds')
    started = time.monotonic()
    try:
        with limit(timeout):
            return _run(binding_path, policy_path, elf, out, mode, work, soc)
    except BudgetExpired as exc:
        path = Path(out)/'progress.json'
        partial = json.loads(path.read_text()) if path.exists() else {}
        return publish(out, 'ift-core', [], False, reason=str(exc), partial=partial,
                       elapsed_s=time.monotonic()-started, timeout_s=timeout,
                       cost_estimate=dict(**partial, note='Cell and byte counts describe preparation cost; runtime is not predicted.'),
                       action='Inspect progress.json. Reuse the work cache; shorten the program or review the declared memory region. No flow verdict was earned.')
