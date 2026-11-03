"""Portfolio disagreement and finite bounded-search rules."""
from argparse import Namespace
import json

from rvw.formal.common import final_status
from rvw.formal.search import depth_search


def test_disagreement_is_error():
    text = ("engine_0: Status returned by engine: PASS\n"
            "engine_1: Status returned by engine: FAIL\nDONE (PASS, rc=0)")
    assert final_status(0, text, 1) == "error"


def test_timeout_cannot_use_a_pass():
    assert final_status(124, "DONE (PASS, rc=0)", 1) == "timeout"


def test_depth_search_is_finite_and_bounded(tmp_path, monkeypatch):
    from rvw.formal import cli
    def run(name, args):
        out = __import__('pathlib').Path(args.out)
        out.mkdir()
        (out / 'result.json').write_text(json.dumps({"status": "pass"}))
    monkeypatch.setattr(cli, '_flow', run)
    args = Namespace(out=tmp_path / 'search', depth=4, max_depth=10, budget=10,
                     timeout=None, json=False)
    assert depth_search(args) == 1
    result = json.loads((args.out / 'result.json').read_text())
    assert [a['depth'] for a in result['attempts']] == [4, 8, 10]
    assert result['status'] == 'inconclusive'
    assert result['max_bounded_pass'] == 10


def test_depth_search_stops_at_failure(tmp_path, monkeypatch):
    from rvw.formal import cli
    def run(name, args):
        out = __import__('pathlib').Path(args.out)
        out.mkdir()
        (out / 'result.json').write_text(json.dumps({"status": "fail"}))
    monkeypatch.setattr(cli, '_flow', run)
    args = Namespace(out=tmp_path / 'search', depth=4, max_depth=64, budget=10,
                     timeout=None, json=False)
    depth_search(args)
    result = json.loads((args.out / 'result.json').read_text())
    assert len(result['attempts']) == 1
    assert result['status'] == 'fail'


def test_cut_width_is_checked(tmp_path, monkeypatch):
    from rvw.formal import cuts
    def run(cmd, cwd, log, timeout):
        (cwd / 'cut-model.json').write_text(json.dumps({'modules': {'rvw_formal_top': {
            'netnames': {'dut.count': {'bits': [1, 2, 3, 4]}}}}}))
        return 0, 0
    monkeypatch.setattr(cuts.common, 'run', run)
    args = Namespace(cut=['count:4'], clock='clk', timeout=1)
    script, records = cuts.commands(args, tmp_path, [])
    assert 'cutpoint rvw_formal_top/w:dut.count' in script
    assert records[0]['width'] == 4
    args.cut = ['count:3']
    import pytest
    with pytest.raises(ValueError, match='width mismatch'):
        cuts.commands(args, tmp_path, [])


def test_constant_cut_is_refused(tmp_path, monkeypatch):
    from rvw.formal import cuts
    def run(cmd, cwd, log, timeout):
        (cwd / 'cut-model.json').write_text(json.dumps({'modules': {'rvw_formal_top': {
            'netnames': {'dut.count': {'bits': ['0']}}}}}))
        return 0, 0
    monkeypatch.setattr(cuts.common, 'run', run)
    import pytest
    with pytest.raises(ValueError, match='constant or aliased'):
        cuts.commands(Namespace(cut=['count:1'], clock='clk', timeout=1), tmp_path, [])
