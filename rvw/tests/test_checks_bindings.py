import json
from pathlib import Path
from rvw.checks.bindings import generate
from test_checks_streams import inputs


def test_bound_stream_entry(tmp_path):
    db,report=inputs(tmp_path)
    (tmp_path/'report.json').write_text(json.dumps(report))
    (tmp_path/'contracts.json').write_text(json.dumps({'tx':dict(stable=True)}))
    result=generate('streams',dict(database=db.name,report='report.json',contracts='contracts.json'),tmp_path,tmp_path/'out')
    assert result['status']=='generated'
    assert result['instances'][0]['target']=='Top'


def test_bound_power_entry(tmp_path):
    root=Path(__file__).resolve().parents[2]
    result=generate('power',dict(source=str(root/'SpinalChecks/upf/isolation.upf'),
        bindings=str(root/'SpinalChecks/upf/bindings.json')),tmp_path,tmp_path/'out')
    assert result['status']=='generated' and all(r['status']=='generated' for r in result['instances'])
    assert (tmp_path/'out/binds.sv').is_file()


def test_all_command_binds_streams_and_power(tmp_path,capsys):
    from rvw.cli import main
    db,report=inputs(tmp_path)
    root=Path(__file__).resolve().parents[2]
    (tmp_path/'rvw.toml').write_text('[core]\nname="fixture"\n')
    (tmp_path/'report.json').write_text(json.dumps(report))
    (tmp_path/'contracts.json').write_text(json.dumps({'tx':dict(stable=True)}))
    spec=dict(schema='rvw.check-generation/1',streams=dict(database=db.name,report='report.json',contracts='contracts.json'),
        power=dict(source=str(root/'SpinalChecks/upf/isolation.upf'),bindings=str(root/'SpinalChecks/upf/bindings.json')))
    (tmp_path/'checks.generate.json').write_text(json.dumps(spec))
    assert main(['checks','generate','--all','--json','--project',str(tmp_path),'--out','out'])==0
    result=json.loads(capsys.readouterr().out)
    assert result['checks'][0]['status']=='generated'
    assert result['checks'][4]['status']=='generated'
    assert not result['complete']
    assert result['checks'][1]['reason']=='no project data supplied'


def test_json_error_and_unknown_kind(tmp_path,capsys):
    from rvw.cli import main
    assert main(['checks','generate','--all','--json','--project',str(tmp_path/'missing')])==2
    assert json.loads(capsys.readouterr().out)['status']=='error'
