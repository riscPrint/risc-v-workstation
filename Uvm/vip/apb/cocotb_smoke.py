"""Small Verilator cocotb smoke. Needs cocotb 2.0.1 in the rvw environment."""
from rvw.sim.uvm import require_evidence
import argparse
import os
from pathlib import Path
import xml.etree.ElementTree as ET
from cocotb_tools.runner import get_runner


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--out', type=Path, required=True)
    args = parser.parse_args()
    out = args.out.resolve()
    out.mkdir(parents=True, exist_ok=False)
    src = Path(__file__).resolve().parent
    runner = get_runner('verilator')
    runner.build(sources=[src / name for name in ('apb_if.sv', 'fixture.sv', 'cocotb_top.sv')],
                 hdl_toplevel='cocotb_top', build_dir=out / 'build',
                 build_args=['-Wno-fatal'], always=True)
    os.environ['PYTHONPATH'] = str(src) + os.pathsep + os.environ.get('PYTHONPATH', '')
    for seed in (1, 2, 3):
        for buggy in (False, True):
            run = out / f'{seed}-{"buggy" if buggy else "good"}'
            run.mkdir()
            runner.test(hdl_toplevel='cocotb_top', test_module='cocotb_test',
                        test_dir=run, seed=seed,
                        extra_env={'APB_SEED': str(seed), 'APB_BUGGY': '1' if buggy else ''},
                        plusargs=['+buggy'] if buggy else [],
                        results_xml=str(run / 'results.xml'))
            result = ET.parse(run / 'results.xml')
            failures = list(result.iter('failure')) + list(result.iter('error'))
            if buggy:
                require_evidence(failures and 'APB_DATA' in ''.join(ET.tostring(f, encoding='unicode') for f in failures), "missing conformance evidence")
            else:
                require_evidence(not failures, "missing conformance evidence")
    print('APB cocotb: 3 good runs and 3 APB_DATA failures')


if __name__ == '__main__':
    main()
