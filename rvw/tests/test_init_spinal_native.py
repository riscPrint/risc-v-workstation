"""Native init check on a fresh, small Spinal core project."""
import json
import os
from pathlib import Path
import shutil
from rvw.common.proc import run_group

import pytest

ROOT = Path(__file__).resolve().parents[2]
TOOLS = ('java', 'sbt', 'verilator', 'riscv64-unknown-elf-gcc', 'spike')
MISSING = [tool for tool in TOOLS if shutil.which(tool) is None]
pytestmark = pytest.mark.skipif(bool(MISSING), reason='tiny Spinal fixture needs: ' + ', '.join(MISSING))


def test_fresh_spinal_project(tmp_path):
    project = tmp_path / 'core'
    shutil.copytree(Path(__file__).parent / 'fixtures/tiny-spinal', project)
    env = dict(os.environ, RVW_HOME=str(ROOT), RVW_PYTHON=str(ROOT / 'rvw/.venv/bin/python'),
               RVW_LOCK_PYTHON=str(ROOT / 'rvw/.venv/bin/python'),
               RVW_SBT_LOCK=os.environ.get('RVW_SBT_LOCK', 'sbt-' + ROOT.name), RISCVSIM_WORK=str(tmp_path / 'sim'))
    rvw = str(ROOT / 'rvw/.venv/bin/rvw')

    def run(*args, cwd=project):
        result = run_group(list(map(str, args)), cwd=cwd, env=env, capture=True, text=True, timeout=300)
        assert result.returncode == 0, result.stdout + result.stderr
        return result.stdout

    run(rvw, 'init', '--isa', 'rv32i', '--name', 'vex-vexii', '--spinal-top', 'tiny.Top',
        '--sbt-project', 'cpu', '--reset-pc', '0x80000000',
        '--bus', 'mem:valid-ready:valid=valid,ready=ready,address=address,rdata=rdata,wdata=wdata,mask=mask',
        '--rvfi-prefix', 'rvfi_', '--accept-platform-defaults')
    run('git', 'init')
    run('git', 'add', '.')
    run('git', '-c', 'user.name=Native fixture', '-c', 'user.email=fixture@example.invalid',
        'commit', '-m', 'Seed core and project files')
    run(project / 'rvw/build-smoke.sh')
    # Use the actual core's retirement ports. Random bus wait cycles use seed 7.
    run(project / 'rvw/run.sh', 'run', '--elf', project / 'rvw/out/programs/smoke',
        '--out', project / 'rvw/out/seeded', '--seed', '7', '--rvfi-trace', '--json')
    record = json.loads((project / 'rvw/out/seeded/result.json').read_text())
    assert record['status'] == 'pass' and record['instret'] > 0 and not record.get('inconclusive')
    report = json.loads(run(rvw, 'cosim', 'check', '--elf', project / 'rvw/out/programs/smoke',
                           '--trace', project / 'rvw/out/seeded/rvfi.jsonl', '--json'))
    assert report['status'] == 'match' and report.get('trace_complete') is True and report.get('end_status') == 'pass', report
    run(rvw, 'query', 'build', '--config', 'default')
    assert (project / 'rvw/out/design.db').is_file()
    run(rvw, 'query', 'where', 'pc')
