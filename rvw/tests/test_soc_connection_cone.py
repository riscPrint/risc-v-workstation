"""Connection cones keep wiring and remove unrelated implementation state."""
from types import SimpleNamespace
import pytest
from rvw.soc.connection_cone import abstract_modules

pytestmark = pytest.mark.fast


class Database:
    top = 'Soc'
    def resolve_one(self, name):
        return SimpleNamespace(component_id=2 if name=='source' else 3, direction='out' if name=='source' else 'in')
    def component(self, identifier):
        return {1:dict(module='Soc',parent_id=None),2:dict(module='Timer',parent_id=1),
                3:dict(module='Cpu',parent_id=1)}[identifier]


def test_cut_preserves_ancestor_wiring(tmp_path):
    rtl = tmp_path/'design.v'
    rtl.write_text('''module Soc(input clk, output irq);
Timer timer(.clk(clk), .irq(irq));
endmodule
module Timer(input clk, output irq);
reg [31:0] count; assign irq = count[31];
endmodule
module Cpu(input irq);
reg [31:0] registers [0:31];
endmodule
''')
    files, removed = abstract_modules(Database(),dict(source='source',destination='destination'),[rtl],tmp_path)
    text = __import__('pathlib').Path(files[0]).read_text()
    assert 'Timer timer(.clk(clk), .irq(irq));' in text
    assert 'count' not in text and 'registers' not in text
    assert removed == ['Cpu','Timer']
    assert 'module Timer (input clk, output irq);' in text


def test_legacy_ports_are_explicitly_unsupported(tmp_path):
    rtl=tmp_path/'legacy.v'
    rtl.write_text('module Timer(clk, irq);\ninput clk; output irq;\nendmodule\n')
    with pytest.raises(ValueError,match='ANSI'):
        abstract_modules(Database(),dict(source='source',destination='destination'),[rtl],tmp_path)


def test_cdc_reports_findings_and_declared_library_gaps():
    from rvw.soc.cdc_report import summarize
    report = dict(registers=4,clock_count=2,
                  findings=[dict(rule='cdc.unsynchronized',library='BufferCC')],
                  crossings=[dict(kind='sync_2ff',library=dict(class_name='BufferCC'))])
    row = summarize(report,['BufferCC'])
    assert row['status']=='findings' and row['protected']==1
    row = summarize(report,['MissingSynchronizer'])
    assert row['status']=='inconclusive' and 'MissingSynchronizer' in row['reason']


def test_vip_generates_one_test_per_mmio_bus(tmp_path):
    import json
    from pathlib import Path
    from rvw.uvm.composed import generate
    from rvw.soc.vip_bench import generate as vip
    root = Path(__file__).resolve().parents[2]
    directory = tmp_path/'benches'
    generate(root/'SpinalSoc/examples/vex/compose.json',directory,directory/'rtl/VerificationSoc.v')
    groups = vip(directory)
    assert set(groups)=={'uart','clint','plic','finisher'}
    assert all(groups.values())
    assert json.loads((directory/'bindings.json').read_text())['bus_tests']==groups
    text = (directory/'test_composed.py').read_text()
    compile(text,'test_composed.py','exec')
    assert '@pyuvm.test()' not in text
    assert "@cocotb.test(name='bus_'+bus_name)" in text


@pytest.mark.parametrize('checks,status,expected',[(31,'pass','pass'),(1,'pass','inconclusive'),(31,'fail','fail')])
def test_protocol_bound_requires_all_binds(tmp_path,monkeypatch,checks,status,expected):
    import json
    from pathlib import Path
    from rvw.soc import protocol_proof
    def run(command,**kwargs):
        if 'formal' in command:
            directory = Path(command[command.index('--out')+1])
            directory.mkdir()
            (directory/'result.json').write_text(json.dumps(dict(status=status,assertions=checks,proof_kind='bounded')))
        return SimpleNamespace(returncode=1 if status=='fail' and 'formal' in command else 0,timed_out=False)
    monkeypatch.setattr(protocol_proof,'run_group',run)
    root = Path(__file__).resolve().parents[2]
    result = protocol_proof.prove(root/'SpinalSoc/examples/vex/soc.json',tmp_path/'proof','classpath')
    assert result['status']==expected


@pytest.mark.parametrize('structural,expected',[('findings','findings'),('protected','pass'),('inconclusive','inconclusive')])
def test_structural_findings_are_distinct_from_missing_consumers(tmp_path,monkeypatch,structural,expected):
    import importlib
    from pathlib import Path
    module = importlib.import_module('rvw.soc.verify')
    def generated(source,out,settings):
        out.mkdir()
        (out/'map.json').write_bytes(source.read_bytes())
        return [dict(kind=kind,generated=True,ran=True,result=structural if kind=='cdc_rdc' else 'pass') for kind in module.KINDS]
    monkeypatch.setattr(module,'generate',generated)
    root = Path(__file__).resolve().parents[2]
    result = module.verify(root/'SpinalSoc/examples/vex/soc.json',tmp_path/'out')
    assert result['status']==expected


def test_no_reset_hazard_is_not_counted_as_protection():
    from rvw.soc.cdc_report import summarize
    row = summarize(dict(registers=4,clock_count=2,rdc=dict(crossings=[dict(status='no_hazard')])))
    assert row['protected']==0 and row['no_reset_hazard']==1
    assert row['status']=='inconclusive'


def test_cli_preserves_findings_exit(tmp_path,monkeypatch,capsys):
    from rvw.cli import main
    from rvw.soc.commands import verify
    monkeypatch.setattr(verify,'verify',lambda *a:dict(status='findings',checks=[]))
    assert main(['soc','verify','unused.json','--out',str(tmp_path/'out'),'--json'])==3
    assert 'findings' in capsys.readouterr().out
