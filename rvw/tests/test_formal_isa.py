import json
import pytest
from rvw.formal.isa import bounded_rows, run, table

pytestmark = pytest.mark.fast


def test_bounded_scope_and_vacuity():
    suite = dict(bounded_depth=30, tests=[
        dict(id='add', status='pass', formal_settings={'cycles':[20]}),
        dict(id='and', status='pass', inconclusive='cover not reached'),
        dict(id='sub', status='fail'), dict(id='lui', status='timeout')])
    rows = bounded_rows(suite)
    assert [r['status'] for r in rows] == ['bounded','inconclusive','failed','inconclusive']
    assert rows[0]['depth'] == 20
    assert 'bounded 20' in table(dict(rows=rows))


def test_missing_bindings_never_sign_off(tmp_path):
    result = run(None, tmp_path/'out', 1, 'external')
    assert result['status'] == 'inconclusive'
    assert all(r['status'] == 'unsupported' for r in result['rows'])
    assert json.loads((tmp_path/'out/result.json').read_text()) == result


def test_run_existing_kit(tmp_path, monkeypatch):
    import rvw.formal.riscv as bounded
    def fake(cfg, out, *args):
        out.mkdir()
        (out/'results.json').write_text(json.dumps(dict(bounded_depth=20, tests=[dict(id='add',status='pass')])) )
    monkeypatch.setattr(bounded, 'run', fake)
    monkeypatch.setattr(bounded, 'resolve_config', lambda cfg: cfg)
    result = run({'checks':['add']}, tmp_path/'out', 1, 'external')
    assert result['rows'][0]['status'] == 'bounded'
    assert result['status'] == 'inconclusive'


def test_discovery():
    from rvw.cli import build_parser
    from rvw.formal.commands.isa import mcp_tools
    args = build_parser().parse_args(['formal','isa','--out','out'])
    assert not args.unbounded
    assert mcp_tools()[0].name == 'formal_isa'


def test_mcp_returns_inconclusive(tmp_path):
    from rvw.formal.commands.isa import mcp_run
    run(None, tmp_path/'out', 1, 'external')
    class Job:
        def run(self, argv): return 3
    assert mcp_run(Job(), out=str(tmp_path/'out'))['status'] == 'inconclusive'


def test_missing_isa_checks_and_channels_are_explicit(tmp_path):
    from rvw.formal.isa import missing_checks
    (tmp_path/'insns').mkdir()
    (tmp_path/'insns/isa_rv32i.txt').write_text('add\nsub\n# comment\n')
    rows=missing_checks(dict(root=tmp_path,isa='rv32i',nret=2,checks=['insn_add_ch0','cover']))
    names={r['check'] for r in rows}
    assert {'insn_add_ch1','insn_sub_ch0','insn_sub_ch1','reg_ch1'}<=names
    assert 'insn_add_ch0' not in names
    assert all(r['status']=='unsupported' for r in rows)


def test_missing_inventory_cannot_silently_qualify(tmp_path):
    from rvw.formal.isa import missing_checks
    assert missing_checks(dict(root=tmp_path,isa='rv32i'))[0]['status']=='unsupported'
