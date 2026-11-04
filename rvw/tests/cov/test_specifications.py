import json
from hashlib import sha256
import pytest
from .test_isa import source
from rvw.cov.isa import spec_diff


def pinned(root, text):
    root.mkdir()
    path = source(root)
    data = json.loads(path.read_text())
    for kind in ('isa', 'profile', 'debug', 'platform'):
        (root / f'{kind}.txt').write_text(text)
        rows = {'schema': 'rvw.spec-obligations/1', 'obligations': [
            {'id': 'rule', 'text': text, 'checkers': [kind], 'tests': ['test.py', 'missing.py']}]}
        raw = json.dumps(rows)
        (root / f'{kind}-obligations.json').write_text(raw)
        data.setdefault('specifications', {})[kind] = {
            'kind': kind, 'revision': '1', 'path': f'{kind}.txt',
            'sha256': sha256(text.encode()).hexdigest(),
            'obligations': {'path': f'{kind}-obligations.json', 'sha256': sha256(raw.encode()).hexdigest()}}
    (root / 'test.py').write_text('assert True')
    path.write_text(json.dumps(data))
    return path


def test_semantic_changes_and_missing_tests(tmp_path):
    a, b = tmp_path / 'a', tmp_path / 'b'
    old, new = pinned(a, 'Must use rule A.'), pinned(b, 'Must use rule B.')
    report = spec_diff(old, new, a, b)
    assert report['adoption_required']
    obs = report['obligations']
    assert len(obs['changed']) == 4
    assert len(obs['missing_tests']) == 4
    assert len(obs['present_tests']) == 4
    assert obs['affected_checkers'] == ['debug', 'isa', 'platform', 'profile']
    assert (b / 'isa.txt').read_text() == 'Must use rule B.'
    assert not spec_diff(new, new, b, b)['adoption_required']


@pytest.mark.parametrize('file', ['isa.txt', 'isa-obligations.json'])
def test_changed_pins_fail(tmp_path, file):
    path = pinned(tmp_path / 'a', 'Rule.')
    (path.parent / file).write_text('changed')
    with pytest.raises(ValueError, match='hash mismatch'):
        spec_diff(path, path, path.parent, path.parent)


def test_unbound_semantic_text_fails(tmp_path):
    path = pinned(tmp_path / 'a', 'Rule.')
    raw = path.read_text()
    ledger = path.parent / 'debug-obligations.json'
    rows = json.loads(ledger.read_text())
    rows['obligations'][0]['text'] = 'Invented rule.'
    ledger.write_text(json.dumps(rows))
    data = json.loads(raw)
    data['specifications']['debug']['obligations']['sha256'] = sha256(ledger.read_bytes()).hexdigest()
    path.write_text(json.dumps(data))
    with pytest.raises(ValueError, match='unsupported obligation'):
        spec_diff(path, path, path.parent, path.parent)


def test_unchanged_obligations_still_check_test_presence(tmp_path):
    path = pinned(tmp_path / 'a', 'Rule.')
    result = spec_diff(path, path, path.parent, path.parent)
    assert len(result['obligations']['missing_tests']) == 4
    (path.parent / 'test.py').unlink()
    result = spec_diff(path, path, path.parent, path.parent)
    assert len(result['obligations']['missing_tests']) == 8


def test_empty_test_list_and_removed_obligations(tmp_path):
    a, b = tmp_path / 'a', tmp_path / 'b'
    old, new = pinned(a, 'Rule A.'), pinned(b, 'Rule B.')
    data = json.loads(new.read_text())
    del data['specifications']['debug']
    rows_path = b / 'isa-obligations.json'
    rows = json.loads(rows_path.read_text())
    rows['obligations'][0]['tests'] = []
    rows_path.write_text(json.dumps(rows))
    data['specifications']['isa']['obligations']['sha256'] = sha256(rows_path.read_bytes()).hexdigest()
    new.write_text(json.dumps(data))
    result = spec_diff(old, new, a, b)
    assert 'debug:rule' in result['obligations']['removed']
    assert {'obligation': 'isa:rule', 'test': None} in result['obligations']['missing_tests']
