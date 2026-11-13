"""Test composed test-master generation and its evidence boundaries."""
import json
from pathlib import Path
import pytest
from rvw.uvm.scaffold import generate
from rvw.soc.compose import compose

pytestmark = pytest.mark.fast
ROOT = Path(__file__).resolve().parents[2]
SOURCE = ROOT/'SpinalSoc/examples/vex/compose.json'
MAP = SOURCE.with_name('soc.json')


def test_composed_profile_has_ral_and_all_peripheral_probes(tmp_path):
    original = SOURCE.read_bytes()
    result = generate(out=tmp_path/'bench',composition=SOURCE,soc=MAP)
    text = Path(result['scala']).read_text()
    assert 'VerificationCore' in text and 'BusIngress(core.bus)' in text
    assert 'val core_stimulus = core.io.stimulus.toIo()' in text
    for name in ('uart','clint','plic','finisher'):
        assert f'val {name}_probe = out(' in text
    generated = (tmp_path/'bench/test_composed.py').read_text()
    compile(generated,'test_composed.py','exec')
    assert 'RegisterModel' in generated and 'SocRegisterEnvironment' in generated
    assert 'SOC_UNEXERCISED_BUS' in generated
    from rvw.soc.model import load
    config = json.loads((tmp_path/'bench/bindings.json').read_text())
    assert load(tmp_path/'bench'/config['map'])['name'] == load(MAP)['name']
    assert result['checks'] == 17
    assert SOURCE.read_bytes() == original


def test_composition_cannot_ignore_a_different_selected_map(tmp_path):
    value = json.loads(MAP.read_text())
    value['name'] = 'different'
    other = tmp_path/'other.json'
    other.write_text(json.dumps(value))
    with pytest.raises(ValueError,match='differs'):
        generate(out=tmp_path/'bench',composition=SOURCE,soc=other)
    assert not (tmp_path/'bench').exists()


def test_existing_database_interface_still_requires_soc(tmp_path):
    with pytest.raises(ValueError,match='db and soc'):
        generate(db=tmp_path/'design.db',out=tmp_path/'bench')


def test_core_export_names_are_checked(tmp_path):
    value = json.loads(SOURCE.read_text())
    value['map'] = str(MAP)
    value['core']['exports'] = ['bus']
    spec = tmp_path/'compose.json'
    spec.write_text(json.dumps(value))
    with pytest.raises(ValueError,match='exported core port'):
        compose(spec,tmp_path/'composition')


def test_soc_verify_runs_the_composition_consumer(tmp_path,monkeypatch):
    from rvw.soc import uvm_run
    from rvw.soc.verify import verify
    (tmp_path/'cp.txt').write_text('private-classpath')
    manifest=tmp_path/'verify.json'
    manifest.write_text(json.dumps(dict(schema='rvw.soc-verify/1',checks={
        'uvm':dict(composition=str(SOURCE),classpath_file='cp.txt')})))
    called=[]
    def run(source,out,classpath,**kwargs):
        called.append((source,classpath,kwargs['expected_map']))
        return dict(status='pass',generated=True,ran=True,checks=17)
    monkeypatch.setattr(uvm_run,'run',run)
    result=verify(MAP,tmp_path/'out',manifest)
    row=next(r for r in result['checks'] if r['kind']=='uvm')
    assert row['generated'] and row['ran'] and row['result']=='pass'
    assert called==[(str(SOURCE),'private-classpath',MAP)]
    assert result['status']=='inconclusive'


def test_passing_simulator_without_checker_counts_stays_inconclusive(tmp_path,monkeypatch):
    from types import SimpleNamespace
    from rvw.soc import uvm_run
    from rvw.sim import cocotb
    out=tmp_path/'bench'
    def process(command,**kwargs):
        if 'verification.VerificationGenerate' in command:
            rtl=Path(command[-1]);rtl.mkdir()
            (rtl/'VerificationSoc.v').write_text('module VerificationSoc; endmodule\n')
        return SimpleNamespace(returncode=0,timed_out=False)
    monkeypatch.setattr(uvm_run,'run_group',process)
    monkeypatch.setattr(cocotb,'run',lambda *a,**kw:dict(tests=[dict(status='pass')]))
    report=uvm_run.run(SOURCE,out,'classpath')
    assert report['ran'] and report['status']=='inconclusive'
