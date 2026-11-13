"""Opt-in native regression for a mapped fixture with complete stage/retire IDs."""
import json
import os
from pathlib import Path
import pytest
from rvw.common.proc import run_group
from rvw.probes.events import read
from rvw.probes.convert import kanata


@pytest.mark.native_light('Verilator')
def test_terminal_store_is_sampled_before_completion(tmp_path):
    project=os.environ.get('RVW_MAPPED_PROBE_PROJECT')
    if not project:
        pytest.skip('set RVW_MAPPED_PROBE_PROJECT to a mapped smoke fixture with stage/retire probes')
    root=Path(project)
    out=tmp_path/'run'
    with (tmp_path/'run.log').open('w') as log:
        r=run_group(['nice','-n','10',str(root/'rvw/run.sh'),'run','--elf',
                     str(root/'rvw/out/programs/smoke'),'--out',str(out),
                     '--rvfi-trace','--probes','--konata','--json'],cwd=root,
                    stdout=log,stderr=log,timeout=115)
    assert r.returncode==0 and not r.timed_out
    c1=json.loads((out/'result.json').read_text())
    assert c1['status']=='pass' and c1['instret']>0
    assert (out/'konata.log').is_file()
    result=kanata(read(out/'probe-events.jsonl'),tmp_path/'converted.log')
    assert result['retired']==c1['instret']
    assert result['open']==0
