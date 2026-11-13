from rvw.formal import portfolio, engine_doctor


def test_doctor_distinguishes_presence_and_qualification(monkeypatch):
    monkeypatch.setattr(portfolio.shutil, 'which', lambda n: None if n == 'bitwuzla' else '/tools/' + n)
    data = engine_doctor.diagnose()
    missing = data['engines']['smtbmc:bitwuzla']
    assert missing['enabled_features'] == []
    assert missing['missing'] == ['bitwuzla']
    assert missing['qualification'] == 'not_measured'
    present = data['engines']['smtbmc:cvc5']
    assert set(present['enabled_features']) == {'bounded_search', 'unbounded_safety'}
    assert data['status'] == 'pass'


def test_sby_unknown_exit_code():
    assert portfolio.parse_status('sby', 'DONE (UNKNOWN, rc=4)', 4, 'prove') == 'inconclusive'
    assert portfolio.parse_status('sby', 'DONE (PASS, rc=0)', 4, 'prove') == 'error'
    assert portfolio.parse_status('sby', 'DONE (FAIL, rc=2)', 0, 'prove') == 'error'


def test_doctor_cli_and_mcp(tmp_path, capsys):
    from rvw.cli import main
    from rvw.formal.deep_cli import mcp_tools
    assert main(['formal', 'doctor', '--out', str(tmp_path / 'doctor'), '--json']) == 0
    assert 'rvw.formal-doctor/1' in capsys.readouterr().out
    assert 'formal_doctor' in {t.name for t in mcp_tools()}
