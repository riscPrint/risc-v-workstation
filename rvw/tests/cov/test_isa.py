import json
import pytest
from .test_functional import decoded_observations_only
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


def source(tmp_path):
    from hashlib import sha256
    path, data = manifest(tmp_path)
    files = {'extensions/rv_i': 'add rd rs1 rs2 31..25=0 14..12=0 6..2=0xc 1..0=3\nsub rd rs1 rs2 31..25=32 14..12=0 6..2=0xc 1..0=3\n',
             'arg_lut.csv': '"rd",11,7\n"rs1",19,15\n"rs2",24,20\n'}
    for name, text in files.items():
        p = tmp_path / name
        p.parent.mkdir(exist_ok=True)
        p.write_text(text)
    data['source'] = {'revision': 'a'*40, 'files': {n: sha256(t.encode()).hexdigest() for n,t in files.items()}}
    path.write_text(json.dumps(data))
    return path


def test_pinned_plan_and_holes(tmp_path):
    from rvw.cov.isa import plan
    from rvw.cov.functional import functional
    path = source(tmp_path)
    trace = tmp_path / 'trace.jsonl'
    trace.write_text('\n'.join(map(json.dumps, [
        {'schema':'rvw.rvfi/1','xlen':32,'isa':'rv32im'},
        {'order':0,'insn':'0x002081b3','rd':3,'mode':3}]))+'\n')
    report = functional([trace], manifest=path, source_root=tmp_path)
    assert report['groups']['isa_instruction']['holes'] == [['sub']]
    assert report['groups']['isa_add_rd']['expected_bins'] == 32
    assert report['groups']['isa_add_rd']['expected_hit'] == 1
    (tmp_path / 'extensions/rv_i').write_text('changed')
    with pytest.raises(ValueError, match='hash mismatch'):
        plan(path, tmp_path)


def test_spec_diff_requires_adoption(tmp_path):
    from rvw.cov.isa import spec_diff
    from hashlib import sha256
    a = tmp_path / 'old'
    b = tmp_path / 'new'
    a.mkdir()
    b.mkdir()
    old, new = source(a), source(b)
    assert spec_diff(old, new, a, b)['status'] == 'unchanged'
    raw = json.loads(new.read_text())
    p = b / 'extensions/rv_i'
    p.write_text(p.read_text().replace('sub rd', 'newop rd'))
    raw['source']['files']['extensions/rv_i'] = sha256(p.read_bytes()).hexdigest()
    raw['source']['revision'] = 'b'*40
    raw['specifications'] = {'debug': {'revision':'1.0', 'sha256':'c'*64}}
    new.write_text(json.dumps(raw))
    report = spec_diff(old, new, a, b)
    assert report['adoption_required']
    assert report['status'] == 'inconclusive'
    assert report['instructions']['added'] == ['newop']
    assert report['instructions']['removed'] == ['sub']
    assert 'debug' in report['declarations']['specifications']['after']


def test_same_name_pseudo_alias_is_not_a_second_instruction():
    from rvw.cov.isa import opcode_records
    rows = opcode_records({'extensions/rv_i':
        'jalr rd rs1 imm12 14..12=0 6..2=0x19 1..0=3\n'
        '$pseudo_op rv_i::jalr jalr rs1 31..20=0 14..12=0 11..7=1 6..2=0x19 1..0=3\n'})
    assert len(rows) == 1
    assert rows[0]['args'] == ['rd', 'rs1', 'imm12']


def test_manifest_context_and_cli(tmp_path):
    from rvw.cov.cli import execute_json
    from rvw.cov.functional import functional
    path = source(tmp_path)
    assert execute_json('isa-check', manifest=path)['status'] == 'inconclusive'
    assert execute_json('isa-diff', before=path, after=path,
                        old_source_root=tmp_path, source_root=tmp_path)['status'] == 'unchanged'
    trace = tmp_path / 'bad.jsonl'
    trace.write_text(json.dumps({'schema':'rvw.rvfi/1','xlen':64,'isa':'rv32im'})+'\n')
    with pytest.raises(ValueError, match='contradicts'):
        functional([trace], manifest=path, source_root=tmp_path)
