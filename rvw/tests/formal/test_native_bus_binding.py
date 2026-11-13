"""Capture real Spinal buses, generate bindings, and elaborate the bound RTL."""
import json
from pathlib import Path
import shutil
import pytest
from rvw.common.proc import run_group
from rvw.formal.bus_bindings import generate

pytestmark=pytest.mark.slow


def test_native_bus_capture_and_bindings(tmp_path):
    if any(not shutil.which(t) for t in ('sbt','verilator')):pytest.skip('sbt and Verilator required')
    root=Path(__file__).resolve().parents[3]
    capture=tmp_path/'capture'
    r=run_group([str(root/'scripts/with-lock.sh'),f'sbt-{root.name}','nice','-n','10','sbt','-batch',
                 'runMain NativeBusCapture '+json.dumps(str(capture))],
                cwd=root/'SpinalChecks/bus-binding',capture=True,timeout=240)
    (tmp_path/'capture.log').write_text(r.stdout+r.stderr)
    assert r.returncode==0 and not r.timed_out,r.stdout+r.stderr
    initial=generate(capture/'design.db',tmp_path/'unbound',type_report=capture/'checks.json')
    assert initial['status']=='no_checks'
    clocks=tmp_path/'clocks.json'
    clocks.write_text(json.dumps(dict(schema='rvw.bus-clocks/1',instances={
        name:dict(clock='clk',reset='reset') for name in ('axi','lite','apb','tl','child.bus')})))
    out=tmp_path/'bound'
    result=generate(capture/'design.db',out,depth=2,max_beats=4,type_report=capture/'checks.json',clocks=clocks)
    assert result['complete'] is True and len(result['buses'])==5,result
    assert {r['kind'] for r in result['buses']}=={'axi4','axi_lite4','apb','tilelink'}
    for row in result['buses']:
        assert row['status']=='generated' and row['clock_source']=='project'
        assert row['bind_scope']=='unique_module'
        if row['kind']!='apb':assert row['coverage']=='transaction_safety'
    nested=next(r for r in result['buses'] if r['path']=='child.bus')
    assert nested['target_instance']=='NativeBusTop.child' and nested['target']=='NativeBusChild'
    rtl=sorted((capture/'rtl').glob('*.v'))
    assert rtl
    r=run_group(['nice','-n','10','verilator','--lint-only','--assert','--timing','-Wno-fatal','--top-module','NativeBusTop',
                 *map(str,rtl),str(out/'monitors.sv'),str(out/'binds.sv')],capture=True,timeout=60)
    (tmp_path/'bound-lint.log').write_text(r.stdout+r.stderr)
    assert r.returncode==0 and not r.timed_out,r.stdout+r.stderr
