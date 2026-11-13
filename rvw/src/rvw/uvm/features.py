"""Derive a bounded engine feature table from C3 conformance evidence."""
from rvw.results import load_results

FEATURES = {
 'phases_config_factory_tlm': ('phasing, config DB, factory, TLM', 'none in checked scope'),
 'constrained_random': ('SV constrained random', 'none in checked constraints'),
 'functional_coverage': ('covergroups and crosses', 'portable bitmap for base environment'),
 'ral_frontdoor': ('RAL frontdoor', 'project bus adapter'),
 'interrupt_debug_pins': ('interrupt/debug pin agent', 'project virtual interface'),
 'spike_retirements': ('user Spike DPI', 'separate DPI bridge; Accellera DPI disabled'),
}


def table(path):
    report = load_results(path)
    rows = []
    for test, (name, workaround) in FEATURES.items():
        found = [t for t in report.tests if t.id == test]
        rows.append({'feature': name, 'test': test,
                     'status': 'checked' if found and all(t.status == 'pass' for t in found) else 'not established',
                     'runs': len(found), 'workaround': workaround})
    rows.extend([
        {'feature': 'Accellera HDL backdoor/VPI', 'test': None, 'status': 'not established', 'runs': 0,
         'workaround': 'UVM_NO_DPI; custom uvm_reg_backdoor with project DPI bridge'},
        {'feature': 'full CORE-V-VERIF bench', 'test': None, 'status': 'not established', 'runs': 0,
         'workaround': 'use project adapter and qualify each required feature'},
    ])
    return {'evidence': str(path), 'features': rows}


def markdown(report):
    lines = ['| Feature | Evidence | Status | Runs | Workaround |', '|---|---|---|---:|---|']
    for row in report['features']:
        lines.append('| ' + ' | '.join(str(row[k] or 'none') for k in ('feature','test','status','runs','workaround')) + ' |')
    return '\n'.join(lines) + '\n'
