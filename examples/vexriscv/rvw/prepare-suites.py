#!/usr/bin/env python3
"""Build the generated suite families that `rvw regress plan` selects for this M-only core.

`features.json` declares RV32IM, machine mode, no PMP and the MSIP/MTIP/MEIP inputs.
The plan selects scheduled WFI wake-up and the single-hart fence and FENCE.I programs.
`selection.json` records what was built and why every other family is not applicable.
"""
import argparse
import importlib.util
import json
import os
from pathlib import Path
import sys


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--out', type=Path, required=True)
    parser.add_argument('--gcc', default='riscv64-unknown-elf-gcc')
    args = parser.parse_args()
    here = Path(__file__).resolve().parent
    root = Path(os.environ.get('RVW_HOME', here.parents[2])).resolve()
    features_path = here / 'features.json'
    features = json.loads(features_path.read_text())
    out = args.out.resolve()
    out.mkdir(parents=True, exist_ok=False)
    from rvw.regress.commands.applicability import plan
    from rvw.privilege.campaign import build
    selection = plan(features_path)
    applicable = {row['name'] for row in selection['suites'] if row['applicable']}
    families = []
    if 'scheduled-wfi-rv32' in applicable:
        source = 'examples/privilege/scheduled-wfi-rv32.json'
        description = out / 'scheduled.json'
        description.write_text(json.dumps(dict(json.loads((root / source).read_text()), isa=features['isa'])) + '\n')
        build(description, out / 'scheduled', args.gcc)
        families.append(dict(family='scheduled', source=source))
    names = [n for n in ('lrsc', 'amo', 'amo-fault', 'fence', 'fence-i') if f'{n}-rv32' in applicable]
    if names:
        tests = root / 'RiscvSim/tests/ordering'
        sys.path.insert(0, str(tests))
        spec = importlib.util.spec_from_file_location('ordering_run', tests / 'run.py')
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        previous = sys.argv
        try:
            sys.argv = ['ordering', '--out', str(out / 'ordering'), '--xlen', '32', '--seeds', '1', '--gcc', args.gcc]
            for name in names:
                sys.argv += ['--suite', name]
            code = module.main()
        finally:
            sys.argv = previous
        if code:
            return code
        families.append(dict(family='ordering', suites=names))
    (out / 'selection.json').write_text(json.dumps(dict(features=features_path.name, families=families,
        not_applicable=[dict(name=r['name'], reason=r['reason']) for r in selection['suites'] if not r['applicable']],
        evidence='selection only; no DUT execution'), indent=2) + '\n')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
