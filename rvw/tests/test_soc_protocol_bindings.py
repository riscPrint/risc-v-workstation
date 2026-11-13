import json
from pathlib import Path
import pytest
from rvw.soc.compose import compose

pytestmark = pytest.mark.fast
ROOT=Path(__file__).resolve().parents[2]
SPEC=ROOT/'SpinalSoc/examples/vex/compose.json'


def test_every_port_includes_core_and_legacy_boundary(tmp_path):
    compose(SPEC,tmp_path/'out')
    source=(tmp_path/'out/ComposedSoc.scala').read_text()
    assert 'ProtocolChecks(core.bus)' in source
    assert 'ApbChecks(uart.io.bus)' in source
    manifest=json.loads((tmp_path/'out/composition.json').read_text())
    paths={b['path'] for b in manifest['protocol_bindings']}
    assert {'core.bus','fabricBus','ram.io.bus','uart.io.bus','uart_port'} <= paths
    assert manifest['validation']=='generated_only'


def test_downstream_checks_use_the_destination_clock(tmp_path):
    spec=json.loads(SPEC.read_text());spec['map']=str(SPEC.with_name('soc.json'))
    spec['domains']={'slow':dict(clock_hz=10000000,reset='async_high')}
    spec['devices']['uart']['domain']='slow'
    path=tmp_path/'compose.json';path.write_text(json.dumps(spec))
    compose(path,tmp_path/'out')
    source=(tmp_path/'out/ComposedSoc.scala').read_text()
    assert 'val uart_checks = new ClockingArea(slow_domain) {\n    ApbChecks(uart.io.bus)\n    ApbChecks(uart_port)' in source
    manifest=json.loads((tmp_path/'out/composition.json').read_text())
    rows={b['path']:b['domain'] for b in manifest['protocol_bindings']}
    assert rows['uart.io.bus']==rows['uart_port']=='slow'
    assert rows['uart_crossing']=='default'


def test_verify_emits_native_binds_for_the_selected_composition(tmp_path):
    from rvw.soc.verify import verify
    spec=tmp_path/'verify.json'
    spec.write_text(json.dumps(dict(schema='rvw.soc-verify/1',checks={
        'protocol':dict(composition=str(SPEC))})))
    result=verify(SPEC.with_name('soc.json'),tmp_path/'out',spec)
    row=result['checks'][0]
    assert row['generated'] and not row['ran']
    assert {'core.bus','fabricBus','uart.io.bus','uart_port'} <= {b['path'] for b in row['details']['bindings']}
    assert row['result']=='inconclusive'
