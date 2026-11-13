#!/usr/bin/env python3
"""Build the generated suite families that `rvw regress plan` selects for one VexiiRiscv profile.

The feature file declares what the core implements. `rvw regress plan` turns it into the
applicable family list. This script builds each applicable family with its shared generator
and keeps only the scenarios that match the declared features. `selection.json` records
generated, applicable and excluded counts with a reason for each exclusion.
"""
import argparse
import importlib.util
import json
import os
from pathlib import Path
import sys


def mmu_rows(root, source, mode, capabilities):
    """Scenarios of one shared MMU description for `mode`, and the excluded ones with reasons."""
    from rvw.regress.mmu import load
    selected, excluded = [], []
    for row in load(root / source):
        reason = ('satp mode is not ' + mode if row.get('mode', 'sv39') != mode else
                  'hardware A/D updates are not implemented' if row.get('ad_mode') == 'hardware' and 'ad:hardware' not in capabilities else
                  'Svade is not declared' if row.get('ad_mode') == 'svade' and 'ad:fault' not in capabilities else None)
        if reason:
            excluded.append(dict(id=row['id'], reason=reason))
        else:
            selected.append(row)
    return selected, excluded


def build_mmu(root, out, name, rows, gcc):
    from rvw.regress.mmu import build
    description = out / f'{name}.json'
    description.write_text(json.dumps(dict(schema='rvw.mmu/1', scenarios=rows), indent=2) + '\n')
    build(description, out / name, gcc)


def ordering(root, out, xlen, names, gcc):
    """Build the ordering programs with the existing compiler and Spike self-check runner."""
    tests = root / 'RiscvSim/tests/ordering'
    sys.path.insert(0, str(tests))
    spec = importlib.util.spec_from_file_location('ordering_run', tests / 'run.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    previous = sys.argv
    try:
        sys.argv = ['ordering', '--out', str(out / 'ordering'), '--xlen', str(xlen), '--seeds', '1', '--gcc', gcc]
        for name in names:
            sys.argv += ['--suite', name]
        return module.main()
    finally:
        sys.argv = previous


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--out', type=Path, required=True)
    parser.add_argument('--features', type=Path, help='feature declaration (default: features64.json)')
    parser.add_argument('--gcc', default='riscv64-unknown-elf-gcc')
    args = parser.parse_args()
    here = Path(__file__).resolve().parent
    root = Path(os.environ.get('RVW_HOME', here.parents[2])).resolve()
    features_path = (args.features or here / 'features64.json').resolve()
    features = json.loads(features_path.read_text())
    out = args.out.resolve()
    out.mkdir(parents=True, exist_ok=False)
    from rvw.regress.commands.applicability import plan
    from rvw.privilege.campaign import build as privilege_build
    selection = plan(features_path)
    capabilities = set(selection['capabilities'])
    xlen = 64 if 'xlen:64' in capabilities else 32
    applicable = {row['name'] for row in selection['suites'] if row['applicable']}
    families = []
    for mode in ('sv32', 'sv39', 'sv48', 'sv57'):
        if f'mmu-{mode}' not in applicable:
            continue
        for name, source in (('mmu', 'examples/mmu/matrix.json'), ('faultwalk', 'examples/mmu/fault-walks.json'),
                             ('mmu-random', 'examples/mmu/random.json')):
            rows, excluded = mmu_rows(root, source, mode, capabilities)
            build_mmu(root, out, name, rows, args.gcc)
            in_mode = [e for e in excluded if not e['reason'].startswith('satp mode')]
            families.append(dict(family=name, source=source, mode=mode, generated=len(rows) + len(excluded),
                                 generated_for_mode=len(rows) + len(in_mode), applicable=len(rows), excluded=in_mode))
    if 'privilege-controls' in applicable:
        privilege_build(root / 'examples/privilege/controls.json', out / 'privilege', args.gcc)
        families.append(dict(family='privilege', source='examples/privilege/controls.json'))
    if 'pmp' in applicable:
        granularity = next((int(c.split(':')[1]) for c in capabilities if c.startswith('pmp-granularity:')), 4)
        description = out / 'pmp.json'
        description.write_text(json.dumps(dict(schema='rvw.privilege/1', kind='pmp',
            pmp=dict(entries=features['pmp_regions'], granularity_bytes=granularity))) + '\n')
        privilege_build(description, out / 'pmp', args.gcc)
        families.append(dict(family='pmp', source='generated', granularity_bytes=granularity))
    scheduled = next((r for r in selection['suites'] if r['applicable'] and r['name'] in ('scheduled-wfi', 'scheduled-wfi-rv32')), None)
    if scheduled:
        config = dict(json.loads((root / scheduled['source']).read_text()), isa=features['isa'])
        if features['privilege_modes'] != 'M':
            config.pop('priv', None)  # S/U present: the standard head clears delegation, PMP and satp
        description = out / 'scheduled.json'
        description.write_text(json.dumps(config) + '\n')
        privilege_build(description, out / 'scheduled', args.gcc)
        families.append(dict(family='scheduled', source=scheduled['source']))
    clint = next((r for r in selection['suites'] if r['applicable'] and r['name'] in ('wfi-clint', 'wfi-clint-rv32')), None)
    if clint:
        config = dict(json.loads((root / clint['source']).read_text()), isa=features['isa'])
        if features['privilege_modes'] != 'M':
            config.pop('priv', None)
        description = out / 'wfi-clint.json'
        description.write_text(json.dumps(config) + '\n')
        privilege_build(description, out / 'wfi-clint', args.gcc)
        families.append(dict(family='wfi-clint', source=clint['source']))
    for name in ('plic', 'plic-delivery'):
        row = next((r for r in selection['suites'] if r['applicable'] and r['name'] == name), None)
        if row:
            # Each program gets an rvw.stimulus/1 file; the adapter serves it through the mailbox.
            description = out / f'{name}.json'
            description.write_text(json.dumps(dict(json.loads((root / row['source']).read_text()), isa=features['isa'])) + '\n')
            privilege_build(description, out / name, args.gcc)
            families.append(dict(family=name, source=row['source']))
    names = [n for n in ('lrsc', 'amo', 'amo-fault', 'fence', 'fence-i', 'zacas', 'cache-block')
             if f'{n}-rv{xlen}' in applicable]
    if names:
        code = ordering(root, out, xlen, names, args.gcc)
        if code:
            return code
        families.append(dict(family='ordering', suites=names))
    not_applicable = [dict(name=r['name'], reason=r['reason']) for r in selection['suites'] if not r['applicable']]
    (out / 'selection.json').write_text(json.dumps(dict(features=features_path.name, xlen=xlen,
        families=families, not_applicable=not_applicable, evidence='selection only; no DUT execution'), indent=2) + '\n')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
