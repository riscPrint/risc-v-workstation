from argparse import Namespace
import json
from pathlib import Path

import pytest

from rvw.common.capture import Capture
from rvw.formal import campaign
from rvw.results import load_results, load_verdict


def test_job_captures_files_and_refuses_tasks(tmp_path):
    (tmp_path / 'a.sv').write_text('module a; endmodule')
    capture = Capture(tmp_path / 'inputs')
    text = '[options]\nmode bmc\n[engines]\nbtor pono\n[script]\nprep -top a\n[files]\na.sv\n'
    frozen, mode, engine = campaign._job(text, tmp_path / 'a.sby', capture)
    assert str(capture.file(tmp_path / 'a.sv').copy) in frozen
    assert mode == 'bmc' and engine == 'btor:pono'
    with pytest.raises(ValueError):
        campaign._job('[tasks]\none\n' + text, tmp_path / 'a.sby', capture)


@pytest.mark.parametrize('rc,done,meaning', [(0, 'PASS', 'bounded_pass'), (124, 'PASS', 'timeout'),
                                          (1, 'FAIL', 'counterexample')])
def test_campaign_never_earns_accept(tmp_path, monkeypatch, rc, done, meaning):
    (tmp_path / 'a.sv').write_text('module a; endmodule')
    (tmp_path / 'a.sby').write_text('[options]\nmode bmc\n[engines]\nsmtbmc yices\n'
                                  '[script]\nprep -top a\n[files]\na.sv\n')
    manifest = tmp_path / 'campaign.toml'
    manifest.write_text('[[property]]\nid="one"\nsby="a.sby"\ntop="a"\nconfig="rtl-v1"\n'
                        'requirements=["REQ1"]\nassumptions=[]\n')
    class Tools:
        def __init__(self, *a): self.env = {}
        def command(self, cmd): return cmd
        def verify(self): pass
    monkeypatch.setattr(campaign, 'Toolchain', Tools)
    def execute(cmd, cwd, log, timeout, **kw):
        model = cwd / 'sby' / 'model'
        model.mkdir(parents=True)
        (model / 'design_prep.il').write_text('module \\a\n  cell $assert \\check\n  end\nend\n')
        (model.parent / 'logfile.txt').write_text(f'DONE ({done}, rc={0 if done == "PASS" else rc})')
        log.write_text('log')
        return rc, 0.1
    monkeypatch.setattr(campaign, 'execute', execute)
    out = tmp_path / 'out'
    assert campaign.run(Namespace(manifest=manifest, out=out, timeout=2, json=False)) == 1
    suite = load_results(out)
    assert suite.tests[0].extra['formal_status'] == meaning
    assert not suite.tests[0].conclusive
    assert load_verdict(out).verdict == 'inconclusive'


def test_history_retains_each_configuration(tmp_path, capsys):
    rows = []
    for index in (1, 2):
        directory = tmp_path / str(index)
        directory.mkdir()
        (directory / 'results.json').write_text(json.dumps({
            'schema': 'rvw.results/1', 'suite': 'formal-sby', 'core': 'external',
            'config': 'external', 'run_id': str(index), 'created': f'2026-11-0{index}',
            'tests': [{'id': 'same', 'status': 'pass', 'formal_status': 'bounded_pass',
                       'configuration': f'cfg{index}', 'requirements': ['R1'],
                       'assumptions': [f'A{index}'], 'job_sha256': str(index)}]}))
        rows.append(directory)
    assert campaign.history(Namespace(paths=rows)) == 0
    data = json.loads(capsys.readouterr().out)
    samples = data['properties']['same']
    assert [row['configuration'] for row in samples] == ['cfg1', 'cfg2']
    assert [row['assumptions'] for row in samples] == [['A1'], ['A2']]
