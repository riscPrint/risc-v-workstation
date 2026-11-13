"""Render a measured SV CPU/probe qualification matrix. Missing rows stay open."""
import json
import re
from pathlib import Path
from rvw.results import load_results


def generate(cpu_results, probes, out):
    cpu_results,probes,out=map(Path,(cpu_results,probes,out))
    cpu=load_results(cpu_results)
    raw=json.loads(cpu_results.read_text())
    measured=json.loads(probes.read_text())
    engine=raw.get('engine')
    log=cpu_results.parent/'build.log'
    if not engine and log.is_file():
        versions=re.findall(r'Verilator [0-9][^\n]*',log.read_text(errors='replace'))
        engine=versions[-1] if versions else None
    lines=['# SV UVM qualification matrix','',
        'This matrix records the supplied native evidence. It is not full language qualification.',
        '', 'CPU engine: '+(engine or 'not recorded in this C3; inspect build.log')+'.',
        'Probe engine: '+measured.get('engine','not recorded')+'.','',
        '| Test | Runs | Status | Scope or workaround |','|---|---:|---|---|']
    required=('spike_retirements','spike_fault_detection','spike_state_fault_detection','spike_csr_fault_detection')
    scopes={'spike_retirements':'six ADDI/MISA retirements per seed; bounded RTL fixture',
        'spike_fault_detection':'destination corruption must fail',
        'spike_state_fault_detection':'GPR snapshot corruption must fail',
        'spike_csr_fault_detection':'CSR snapshot corruption must fail'}
    for name in required:
        rows=[r for r in cpu.tests if r.id==name]
        status='checked' if rows and all(r.status=='pass' for r in rows) else 'not established'
        lines.append(f'| {name} | {len(rows)} | {status} | {scopes[name]} |')
    for name in ('randc','transition'):
        rows=[r for r in measured.get('probes',[]) if r['feature']==name]
        status=rows[0]['status'] if len(rows)==1 else 'not established'
        if rows and rows[0].get('ignored_feature_warning'):
            status+='; ignored-feature warning'
        workaround=('use pyuvm observed bins and rvw cov functional; do not infer transition coverage from compilation'
                    if name=='transition' else 'qualify the selected constraint expression separately')
        lines.append(f'| SV {name} | {len(rows)} | {status} | {workaround} |')
    lines.extend(['| Accellera HDL backdoor/VPI | 0 | not established | custom qualified backdoor or explicit observation interface |',
        '| VexRiscv SV CPU environment | 0 | not established | use the qualified live pyuvm binding |',
        '', 'The CPU fixture uses pinned Accellera UVM with UVM_NO_DPI and a separate Spike DPI bridge.',
        'The Python coverage path can export observed bins for UCIS round trips.',
        'It does not turn unobserved transitions into covered bins.',
        'Rerun the native CPU example and probes after an engine or source change.', ''])
    with out.open('w') as f: f.write('\n'.join(lines))
    return dict(out=str(out),cpu_rows=len(cpu.tests),probe_rows=len(measured.get('probes',[])))
