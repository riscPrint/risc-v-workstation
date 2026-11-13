"""Generated RTL style is counted advice; functional warnings stay active."""
import copy
import json
from pathlib import Path
import pytest
from lint_builder import Builder
from rvw.lint import native
from rvw.lint.cli import report

pytestmark = pytest.mark.fast


@pytest.mark.parametrize('spinal', [False, True])
def test_database_provenance_controls_style_summary(tmp_path, monkeypatch, spinal):
    source = Path(__file__).parent / 'fixtures/lint/generated_advice.v'
    b = Builder(tmp_path / 'd.db')
    if spinal:
        b.c.execute("INSERT INTO meta VALUES('spinalhdl','test')")
    b.c.execute('INSERT INTO rtl_files VALUES(?)', (str(source),))
    db = b.done()
    fs = native.parse('verible', f'{source}:2:3: use always_comb [always-comb]\n'
                      f'{source}:3:3: use always_comb [always-comb]\n'
                      f'{source}:4:3: missing default [case-missing-default]')
    monkeypatch.setattr(native, 'run', lambda *a: dict(status='completed', findings=copy.deepcopy(fs)))
    p = tmp_path / 'settings.json'
    p.write_text(json.dumps(dict(schema='rvw.lint-settings/1', config='c', top='Top',
                                db=str(db), files=[str(source)], backends=['verible'])))
    r = report(p)['backends']['verible']
    advice = [f for f in r['findings'] if f['rule'] == 'verible.always-comb']
    assert len(advice) == (1 if spinal else 2)
    assert advice[0]['severity'] == ('info' if spinal else 'warning')
    if spinal:
        assert advice[0]['count'] == len(advice[0]['members']) == 2
    assert next(f for f in r['findings'] if f['rule'] == 'verible.case-missing-default')['severity'] == 'warning'


def test_functional_warnings_and_errors_keep_their_severity():
    source = str(Path(__file__).parent / 'fixtures/lint/generated_advice.v')
    fs = native.parse('verilator', f'%Warning-UNUSEDSIGNAL: {source}:1:2: unused field\n'
                      f'%Warning-WIDTHTRUNC: {source}:2:2: drops bits\n'
                      f'%Error: {source}:3:2: syntax error')
    result = native.summarize_generated(dict(status='inconclusive', findings=fs), [source])
    levels = {f['rule']: f['severity'] for f in result['findings']}
    assert levels == {'verilator.UNUSEDSIGNAL': 'info', 'verilator.WIDTHTRUNC': 'warning', 'verilator.ERROR': 'error'}
    assert result['status'] == 'inconclusive'
