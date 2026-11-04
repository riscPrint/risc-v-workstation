#!/usr/bin/env python3
"""Run one native install case. Save measured results outside the source tree."""
import argparse
import json
import os
from pathlib import Path
import platform
import shlex
import shutil
import signal
import subprocess
import sys
import time
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'rvw/src'))
from rvw.common.proc import run_group  # noqa: E402

CASES = {
    'core': [], 'sim': ['--with-sim'], 'gcc': ['--with-riscv-gcc'],
    'cosim': ['--with-cosim'], 'formal': ['--with-formal'],
    'gem5': ['--with-gem5'],
    'quickstart': ['--with-sim', '--with-riscv-gcc', '--with-cosim'],
    'all': ['--all'],
}
VEX = 'baf7dc82f855eddaf5b0a20a6802c526f127e38a'
TESTS = 'd7e86f701b929b5d801f8cda1a4871ab05f452bb'


class Runner:
    def __init__(self, out, case, timeout, cold_scala):
        self.out, self.timeout = out, timeout
        self.env = dict(os.environ)
        for name in ('RVW_HOME', 'RVW_PROJECT', 'RVW_CORE', 'VEXRISCV',
                     'SPINAL_BOOM', 'RVW_LOCKS_HELD', 'PYTHONPATH', 'VIRTUAL_ENV'):
            self.env.pop(name, None)
        self.env['RVW_LOCK_PYTHON'] = sys.executable
        self.env['CARGO_BUILD_JOBS'] = '2'
        self.repo = out / 'workstation'
        self.report = dict(schema='rvw.install-check/1', case=case,
                           flags=CASES[case], host=platform.platform(),
                           machine=platform.machine(),
                           host_scope='existing host; clean-host status requires external evidence',
                           cold_scala=cold_scala, status='inconclusive', steps=[])
        if Path('/etc/os-release').exists():
            self.report['os_release'] = Path('/etc/os-release').read_text()
        self.save()

    def save(self):
        temp = self.out / 'report.tmp'
        temp.write_text(json.dumps(self.report, indent=2) + '\n')
        temp.replace(self.out / 'report.json')

    def run(self, name, command, cwd=None, lock=None):
        command = [str(x) for x in command]
        if lock:
            command = [str(self.repo / 'scripts/with-lock.sh'), lock,
                       'nice', '-n', '10', *command]
        row = dict(name=name, command=command, cwd=str(cwd or self.out),
                   status='inconclusive', log=f'{len(self.report["steps"]):02d}-{name}.log')
        self.report['steps'].append(row)
        self.save()
        print(f'{name}: {shlex.join(command)}', flush=True)
        start = time.monotonic()
        with (self.out / row['log']).open('w') as log:
            result = run_group(command, cwd=cwd or self.out, env=self.env,
                               timeout=self.timeout, stdout=log, stderr=subprocess.STDOUT)
        row.update(returncode=result.returncode, timed_out=result.timed_out,
                   seconds=round(time.monotonic() - start, 3),
                   status='pass' if result.returncode == 0 else 'error')
        self.save()
        if result.returncode:
            raise RuntimeError(f'{name} failed; see {row["log"]}')
        return self.out / row['log']

    def clone(self, name, url, pin, target):
        self.run(f'{name}-clone', ['git', 'clone', '--no-checkout', url, target])
        self.run(f'{name}-pin', ['git', '-C', target, 'checkout', '--detach', pin])

    def load_env(self):
        # Read only the generated environment, without interpreting shell output.
        keys = ('PATH', 'JAVA_HOME', 'SPIKE_PREFIX', 'RVW_HOME', 'RVW_PYTHON',
                'RVW_LOCK_PYTHON', 'RVW_GEM5', 'RVW_SLANG', 'RVW_SAIL', 'VERILATOR_ROOT')
        code = 'import json,os; print(json.dumps({k:os.environ[k] for k in ' + repr(keys) + ' if k in os.environ}))'
        log = self.run('environment', ['bash', '-c', 'source "$1"; "$2" -c "$3"',
                                       'bash', self.repo / 'env.sh', sys.executable, code])
        self.env.update(json.loads(log.read_text()))
        self.env['RVW_LOCK_PYTHON'] = str(self.repo / 'rvw/.venv/bin/python')

    def check_json(self, path, predicate):
        if not predicate(json.loads(path.read_text())):
            raise RuntimeError(f'Incomplete or unsuccessful runtime evidence: {path}')

    def check_junit(self, path):
        suites = ET.parse(path).getroot()
        cases = list(suites.iter('testcase'))
        if not cases or any(c.find(tag) is not None for c in cases
                            for tag in ('skipped', 'failure', 'error')):
            raise RuntimeError(f'Native tests did not all run and pass: {path}')
        self.report['native_tests'] = dict(passed=len(cases), skipped=0)
        self.save()

    def execute(self, case, cold_scala):
        revision = subprocess.check_output(['git', '-C', ROOT, 'rev-parse', 'HEAD'], text=True).strip()
        self.report['revision'] = revision
        self.clone('workstation', str(ROOT), revision, self.repo)
        flags = CASES[case]
        install = [self.repo / 'scripts/install.sh']
        self.run('install', [*install, '--yes', *flags], lock='suite')
        self.load_env()
        self.run('check', [*install, '--check', *flags])
        rvw = self.repo / 'rvw/.venv/bin/rvw'
        # These are harness dependencies, installed only AFTER the exact flag check.
        sim = case in ('sim', 'cosim', 'quickstart', 'all')
        gcc = sim or case in ('gcc', 'gem5')
        if (sim and case not in ('quickstart', 'all')) or case == 'gem5':
            extra = ['--with-riscv-gcc'] + (['--with-sim'] if sim else [])
            self.run('harness-tools', [*install, '--yes', *extra], lock='suite')
            self.load_env()
        if gcc:
            tests = self.out / 'riscv-tests'
            self.clone('tests', 'https://github.com/riscv-software-src/riscv-tests.git', TESTS, tests)
            self.run('tests-submodules', ['git', '-C', tests, 'submodule', 'update', '--init', '--recursive'])
            build = self.out / 'isa'
            build.mkdir()
            self.run('gcc-elf', ['make', '-j2', '-f', tests / 'isa/Makefile',
                                f'src_dir={tests}/isa', 'XLEN=32',
                                'RISCV_PREFIX=riscv64-unknown-elf-', 'rv32ui-p-add'], cwd=build, lock='suite')
            self.run('gcc-elf-header', ['riscv64-unknown-elf-readelf', '-h', build / 'rv32ui-p-add'])
        if sim:
            vex = self.out / 'vexriscv'
            self.clone('vex', 'https://github.com/SpinalHDL/VexRiscv.git', VEX, vex)
            shutil.copy2(self.repo / 'examples/vexriscv/rvw.toml', vex / 'rvw.toml')
            shutil.copytree(self.repo / 'examples/vexriscv/rvw', vex / 'rvw')
            self.env['RISCV_TESTS_SOURCE'] = str(tests)
            self.run('vex-elf', [vex / 'rvw/build-tests.sh'], lock='suite')
            if cold_scala:
                cache = self.out / 'scala-cache'
                self.env.update(COURSIER_CACHE=str(cache / 'coursier'),
                                SBT_OPTS=f'-Dsbt.boot.directory={cache}/boot -Dsbt.global.base={cache}/global -Dsbt.ivy.home={cache}/ivy')
            self.run('scala-fetch', ['sbt', '-batch', '-J-XX:ActiveProcessorCount=2',
                                     '-Dsbt.offline=false', 'root/update', 'root/compile'], cwd=vex / 'rvw', lock='sbt')
            run = self.out / 'vex-smoke'
            self.run('vex-offline-smoke', [vex / 'rvw/run.sh', 'run', '--elf',
                     vex / 'rvw/out/programs/smoke', '--out', run, '--seed', '1',
                     '--mem-latency', '0', '--max-cycles', '10000', '--rvfi-trace', '--json'], cwd=vex)
            self.check_json(run / 'result.json', lambda r: r.get('status') == 'pass'
                            and not r.get('why_inconclusive') and r.get('artifacts', {}).get('rvfi_trace'))
            if case in ('cosim', 'quickstart', 'all'):
                log = self.run('cosim-smoke', [rvw, '--project', vex / 'rvw.toml',
                    'cosim', 'check', '--elf', vex / 'rvw/out/programs/smoke',
                    '--trace', run / 'rvfi.jsonl', '--json'], cwd=vex)
                self.check_json(log, lambda r: r.get('status') == 'match'
                                and r.get('trace_complete') is True and r.get('end_status') == 'pass')
        if case in ('cosim', 'quickstart', 'all'):
            self.run('reference-test-setup', ['uv', 'sync', '--locked', '--extra', 'dev',
                     '--extra', 'mcp', '--project', self.repo / 'rvw'], lock='suite')
            junit = self.out / 'reference-tests.xml'
            self.run('reference-tests', [self.repo / 'rvw/.venv/bin/python', '-m', 'pytest',
                     self.repo / 'rvw/tests/cosim' / 'test_reference_mmu.py',
                     self.repo / 'rvw/tests/cosim' / 'test_platform_policy.py',
                     '-q', f'--junitxml={junit}'], lock='suite')
            self.check_junit(junit)
        if case in ('formal', 'all'):
            design = self.out / 'counter.v'
            design.write_text('module counter(input clk, input reset);\n'
                'reg [3:0] count;\nalways @(posedge clk) begin\n'
                'if (reset) count <= 0; else count <= count + 1;\n'
                'if (!reset) assert(count < 15);\nend\nendmodule\n')
            result = self.out / 'formal'
            self.run('formal-bmc', [rvw, 'formal', 'bmc', '--verilog', design,
                     '--top', 'counter', '--depth', '8', '--timeout', '60',
                     '--out', result, '--json'], lock='suite')
            self.check_json(result / 'result.json', lambda r: r.get('status') == 'pass')
        if case in ('gem5', 'all'):
            project = self.out / 'arch-project'
            project.mkdir()
            shutil.copy2(self.repo / 'examples/boom/arch/large.json', project / 'core.json')
            (project / 'rvw.toml').write_text('[project]\nschema="rvw.project/1"\n'
                '[core]\nname="install-smoke"\n[arch]\ndescription="core.json"\n'
                f'sources={json.dumps(str(tests / "benchmarks"))}\nbenchmarks="bench"\n')
            self.run('arch-build', [rvw, '--project', project / 'rvw.toml',
                                  'arch', 'build', '--bench', 'median', '--json'], cwd=project, lock='gem5')
            log = self.run('arch-run', [rvw, '--project', project / 'rvw.toml',
                           'arch', 'run', '--bench', 'median', '--out', self.out / 'model',
                           '--timeout', '600', '--json'], cwd=project, lock='gem5')
            self.check_json(log, lambda r: len(r.get('benchmarks', [])) == 1
                            and all(b.get('status') == 'pass' for b in r['benchmarks']))
        self.report['status'] = 'pass'
        self.save()


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--case', choices=CASES, default='quickstart')
    p.add_argument('--out', type=Path, required=True, help='new output directory outside the checkout')
    p.add_argument('--timeout', type=float, default=21600, help='seconds per step, including lock wait')
    p.add_argument('--cold-scala', action='store_true', help='fetch into a new Scala cache before offline startup')
    args = p.parse_args()
    if args.timeout <= 0 or not args.timeout < float('inf'):
        p.error('--timeout must be positive and finite')
    out = args.out.resolve()
    if out == ROOT or ROOT in out.parents:
        p.error('--out must be outside the checkout')
    if args.cold_scala and args.case not in ('sim', 'cosim', 'quickstart', 'all'):
        p.error('--cold-scala needs a simulation case')
    # Do not call an edited working tree a check of its committed revision.
    if subprocess.check_output(['git', '-C', ROOT, 'status', '--porcelain']):
        p.error('commit source changes before qualification')
    out.mkdir(parents=True, exist_ok=False)
    runner = Runner(out, args.case, args.timeout, args.cold_scala)
    def interrupted(signum, frame):
        raise InterruptedError(f'qualification interrupted by signal {signum}')
    for sig in (signal.SIGTERM, signal.SIGHUP):
        signal.signal(sig, interrupted)
    try:
        runner.execute(args.case, args.cold_scala)
    except (OSError, ValueError, RuntimeError, KeyboardInterrupt) as exc:
        runner.report.update(status='error', error=str(exc))
        runner.save()
        print(str(exc), file=sys.stderr)
        return 1
    print(f'Case passed on this host. Clean-host qualification is separate. Report: {out / "report.json"}')
    return 0


if __name__ == '__main__':
    sys.exit(main())
