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


def test_json_error_and_unknown_kind(tmp_path,capsys):
    from rvw.cli import main
    assert main(['checks','generate','--all','--json','--project',str(tmp_path/'missing')])==2
    assert json.loads(capsys.readouterr().out)['status']=='error'
