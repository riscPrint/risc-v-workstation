#!/usr/bin/env python3
"""Build the bounded RV64 supervisor campaigns from their shared generators."""
import argparse
import importlib.util
import json
from pathlib import Path
import sys


def mmu_selection(root):
    from rvw.regress.mmu import load
    rows = load(root / 'examples/mmu/matrix.json')
    selected = []
    excluded = []
    for row in rows:
        reason = ('satp mode is not Sv39' if row.get('mode') != 'sv39' else
                  'hardware A/D updates are not implemented' if row.get('ad_mode') == 'hardware' else None)
        if reason:
            excluded.append(dict(id=row['id'], reason=reason))
        else:
            selected.append(row)
    return selected, excluded


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--out', type=Path, required=True)
    parser.add_argument('--gcc', default='riscv64-unknown-elf-gcc')
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[3]
    out = args.out.resolve()
    out.mkdir(parents=True, exist_ok=False)
    from rvw.regress.mmu import build as mmu_build
    from rvw.privilege.campaign import build as privilege_build
    selected, excluded = mmu_selection(root)
    description = out / 'mmu.json'
    description.write_text(json.dumps(dict(schema='rvw.mmu/1', scenarios=selected), indent=2) + '\n')
    mmu_build(description, out / 'mmu', args.gcc)
    privilege_build(root / 'examples/privilege/controls.json', out / 'privilege', args.gcc)
    pmp_description = out / 'pmp.json'
    pmp_description.write_text(json.dumps(dict(schema='rvw.privilege/1', kind='pmp',
        pmp=dict(entries=8, granularity_bytes=16))) + '\n')
    privilege_build(pmp_description, out / 'pmp', args.gcc)
    privilege_build(root / 'examples/privilege/scheduled-wfi.json', out / 'scheduled', args.gcc)
    from rvw.regress.mmu import load
    faults = load(root / 'examples/mmu/fault-walks.json')
    fault_description = out / 'faultwalk.json'
    fault_description.write_text(json.dumps(dict(schema='rvw.mmu/1',
        scenarios=[row for row in faults if row.get('mode') == 'sv39'])) + '\n')
    mmu_build(fault_description, out / 'faultwalk', args.gcc)
    ordering = root / 'RiscvSim/tests/ordering'
    sys.path.insert(0, str(ordering))
    spec = importlib.util.spec_from_file_location('ordering_run', ordering / 'run.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    # Keep the existing compiler and Spike self-check runner unchanged.
    previous = sys.argv
    try:
        sys.argv = ['ordering', '--out', str(out / 'ordering'), '--xlen', '64', '--seeds', '1', '--gcc', args.gcc]
        for name in ('lrsc', 'amo', 'amo-fault', 'fence', 'fence-i'):
            sys.argv += ['--suite', name]
        code = module.main()
        if code:
            return code
    finally:
        sys.argv = previous
    (out / 'selection.json').write_text(json.dumps(dict(mmu_generated=len(selected) + len(excluded),
        mmu_applicable=len(selected), excluded=excluded), indent=2) + '\n')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
