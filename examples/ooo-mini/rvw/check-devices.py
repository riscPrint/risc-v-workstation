#!/usr/bin/env python3
"""Run the RV32 device tests and PLIC socket lockstep with fresh outputs."""
import argparse
import json
import os
from pathlib import Path
import subprocess

from rvw.common.capture import Capture
from rvw.cosim.checker import check
from rvw.cosim.platform import Platform
from rvw.cosim.spike import Spike, capture_shim
from rvw.regress.commands.suite_cosim import matched
from rvw.results import load_run


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--out', type=Path, required=True)
    parser.add_argument('--library', type=Path, help='Use an existing device library.')
    args = parser.parse_args()
    out = args.out.resolve()
    out.mkdir(parents=True, exist_ok=False)
    home = Path(os.environ['RVW_HOME']).resolve()
    project = Path(__file__).resolve().parent.parent
    rvw = home / 'rvw/.venv/bin/rvw'
    env = dict(os.environ)
    env.setdefault('RVW_SBT_LOCK', 'sbt-ooomini2')
    env.setdefault('RVW_OOO_LOCK', 'ooo-mini-ooomini2')

    def run(name, command, extra=None):
        with (out / f'{name}.log').open('w') as log:
            subprocess.run(['nice', '-n', '10', *map(str, command)], env=env | (extra or {}),
                           stdout=log, stderr=subprocess.STDOUT, check=True)

    library = args.library.resolve() if args.library else out / 'devices/libdevices.dylib'
    if not args.library:
        run('device-build', [home/'scripts/with-lock.sh', env['RVW_SBT_LOCK'],
                            home/'rvw/.venv/bin/python', home/'RiscvSim/scripts/build-devices.py',
                            '--out', library.parent])
    assert library.is_file(), library
    env['RVW_DEVICE_LIBRARY'] = str(library)
    for kind in ('clint', 'plic'):
        run(f'plan-{kind}', [rvw, '--project', project, 'regress', 'plan', '--features',
                            project/f'rvw/features-{kind}.json', '--json'])
    run('clint-build', [rvw, 'regress', 'privilege', 'build',
                       home/'examples/privilege/spike-wfi-rv32.json', '--out', out/'clint-elfs', '--json'])
    plic_elf = out / 'plic-precise.elf'
    run('plic-build', [os.environ.get('RISCV_GCC', 'riscv64-unknown-elf-gcc'),
                      '-march=rv32im_zicsr', '-mabi=ilp32', '-nostdlib',
                      '-T', project/'rvw/link.ld', project/'rvw/plic-precise.S', '-o', plic_elf])
    rows = [dict(elf=str(elf), out=str(out/'clint-runs'/elf.stem),
                 **{'rvfi-trace': True, 'probes': True, 'seed': 17, 'max-cycles': 30000})
            for elf in sorted((out/'clint-elfs').glob('*.elf'))]
    assert len(rows) == 4
    manifest = out/'clint-jobs.jsonl'
    manifest.write_text(''.join(json.dumps(row)+'\n' for row in rows))
    run('clint-run', [project/'rvw/run.sh', 'run-many', '--manifest', manifest,
                      '--jobs', '2', '--wall-timeout', '115', '--json'],
        {'OOO_MINI_DEVICE_MAP': str(project/'rvw/devices/clint-map.json')})
    plic_run = out/'plic-run'
    plic_env = {'OOO_MINI_DEVICE_MAP': str(project/'rvw/devices/plic-map.json')}
    run('plic-run', [project/'rvw/run.sh', 'run', '--elf', plic_elf, '--out', plic_run,
                     '--rvfi-trace', '--probes', '--seed', '17', '--max-cycles', '5000',
                     '--wall-timeout', '115', '--json'], plic_env)
    rows.append(dict(elf=str(plic_elf), out=str(plic_run)))
    for row in rows:
        run_dir = Path(row['out'])
        c1 = load_run(run_dir/'result.json')
        monitors = json.loads((run_dir/'checks-run.json').read_text())
        assert c1.status == 'pass' and monitors['fired'] == 0
        plic = run_dir == plic_run
        capture = Capture(run_dir/'reference-inputs')
        platform = Platform.load('ooo-mini', capture.file(project/f"rvw/platform-{'plic' if plic else 'clint'}.json").copy)
        shim = capture_shim(capture, home/'Cosim/build/librvw_spike.so')
        model = Spike(platform, capture.file(Path(row['elf'])).copy, shim=shim)
        sync = () if plic else ('irq', 'mmio')
        try:
            report = check(capture.file(run_dir/'rvfi.jsonl').copy, model, platform, sync=sync)
        finally:
            model.close()
        (run_dir/'comparison.json').write_text(json.dumps(report))
        (capture.root/'receipt.json').write_text(json.dumps(capture.record()))
        assert matched(report, c1, sync), (run_dir, report['status'])
        print(json.dumps(dict(test=Path(row['elf']).stem, status=report['status'],
                              cycles=c1.cycles, retirements=c1.instret,
                              synchronized=report.get('synchronized'), monitor_firings=monitors['fired'])), flush=True)
    run('live-plic', [rvw, '--project', project, 'cosim', 'live', '--lockstep', '--strict',
                      '--elf', plic_elf, '--platform', project/'rvw/platform-plic.json',
                      '--out', out/'live-plic', '--timeout', '240', '--json',
                      '--simulator', project/'rvw/run.sh', 'run', '--elf', '{elf}', '--out', '{out}/dut',
                      '--rvfi-trace', '--probes', '--seed', '17', '--max-cycles', '5000',
                      '--wall-timeout', '115', '--json'], plic_env)
    report = json.loads((out/'live-plic.log').read_text())
    assert report['status'] == 'match' and report['trace_complete'] and report['synchronized'] == 0
    assert report['mode'] == 'lockstep' and report['external_interrupt_evidence']['status'] == 'checked'
    live_c1 = load_run(out/'live-plic/dut/result.json')
    live_checks = json.loads((out/'live-plic/dut/checks-run.json').read_text())
    assert live_c1.status == 'pass' and live_c1.details['socket_lockstep'] and live_checks['fired'] == 0
    print(json.dumps(dict(test='live-plic', status=report['status'], synchronized=report['synchronized'])))


if __name__ == '__main__':
    main()
