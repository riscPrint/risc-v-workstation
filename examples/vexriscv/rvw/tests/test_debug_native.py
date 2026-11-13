"""Debug Module checks against VexRiscv RTL through the generic DMI endpoint (needs VEXRISCV and native tools)."""
import os
from pathlib import Path

import pytest

from rvw.common.proc import run_group
from rvw.debug import profile, suite

EXAMPLE = Path(__file__).resolve().parents[1]
pytestmark = pytest.mark.skipif(not os.environ.get('VEXRISCV'), reason='VEXRISCV checkout not set')


def test_dmi_endpoint_runs_compliance_checks(tmp_path):
    built = run_group([str(EXAMPLE / 'debug/build.sh')], capture=True, text=True, timeout=60)
    assert built.returncode == 0, built.stderr
    prof = profile.load(EXAMPLE / 'debug/profile-dmi.toml')
    prof['transport']['command'] = [str(tmp_path / 'out') if c.endswith('/out/debug-dmi') else c
                                    for c in prof['transport']['command']]
    ids = ['dm.version', 'dm.halt', 'abs.gpr_roundtrip', 'dbg.step', 'trig.execute_matches', 'abs.transfer_none',
           'trig.load_address']
    entries = suite.run(prof, ids=ids, log=tmp_path / 'adapter.log')
    got = {e['id']: e['status'] for e in entries}
    assert {got[i] for i in ids[:5]} == {'pass'}, got
    assert got['abs.transfer_none'] == 'fail'      # DM checks aarsize without a transfer
    assert got['trig.load_address'] == 'unsupported'  # execute-only triggers
