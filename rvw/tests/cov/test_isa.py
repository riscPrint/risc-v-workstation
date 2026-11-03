import json
import pytest
from rvw.cov.isa import check_manifest, load_manifest


def manifest(tmp_path):
    data = {'schema': 'rvw.isa/1', 'isa': 'rv32im', 'extensions': {
        'i': {'version': None}, 'm': {'version': '2.0', 'requires': ['i']}},
        'options': {}, 'consumers': {'compiler': 'rv32im'}}
    path = tmp_path / 'isa.json'
    path.write_text(json.dumps(data))
    return path, data


def test_declarations(tmp_path):
    path, data = manifest(tmp_path)
    assert check_manifest(path)['status'] == 'inconclusive'
    data['consumers']['compiler'] = 'rv64im'
    path.write_text(json.dumps(data))
    with pytest.raises(ValueError, match='contradicts'):
        load_manifest(path)
    data['consumers'] = {}
    data['extensions']['m']['requires'] = ['f']
    path.write_text(json.dumps(data))
    with pytest.raises(ValueError, match='required'):
        load_manifest(path)
