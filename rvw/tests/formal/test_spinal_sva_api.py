"""Short JVM smoke after the optional locked SpinalChecks Test/compile."""
import os
from pathlib import Path
import shutil
import subprocess

import pytest

from rvw.formal.temporal import lower


@pytest.fixture
def emitted(tmp_path):
    classpath = os.environ.get('RVW_SVA_TEST_CLASSPATH')
    if not classpath:
        pytest.skip('set RVW_SVA_TEST_CLASSPATH after SpinalChecks Test/compile')
    output = tmp_path / 'properties.sv'
    run = subprocess.run(['nice', '-n', '10', 'java', '-cp', classpath,
                          'spinalchecks.SvaEmitSmoke', str(output)], capture_output=True, text=True, timeout=20)
    assert run.returncode == 0, run.stdout + run.stderr
    return output.read_text()


def test_shared_frontend(emitted):
    rtl, rows = lower('module m;\n' + emitted + 'endmodule')
    assert [p['id'] for p in rows] == ['response', 'stable_data']
    assert [p['kind'] for p in rows] == ['assert', 'cover']
    assert rows[0]['horizon'] == 1


@pytest.mark.parametrize('mutant', [False, True])
def test_native_emission(tmp_path, emitted, mutant):
    if not shutil.which('sby') or not shutil.which('yices-smt2'):
        pytest.skip('SBY and Yices required')
    design = ('module m(input clk); wire req=1; wire ack=' + ('0;' if mutant else '1;')
              + ' wire [7:0] data=0; ')
    rtl, _ = lower(design + emitted + 'endmodule')
    (tmp_path / 'm.sv').write_text(rtl)
    (tmp_path / 'job.sby').write_text('''[options]
mode bmc
depth 8
[engines]
smtbmc yices
[script]
read -formal m.sv
prep -top m
[files]
m.sv
''')
    run = subprocess.run(['nice', '-n', '10', 'sby', '-f', 'job.sby'], cwd=tmp_path,
                         capture_output=True, text=True, timeout=30)
    assert (tmp_path / 'job/status').read_text().split()[0] == ('FAIL' if mutant else 'PASS'), run.stdout
