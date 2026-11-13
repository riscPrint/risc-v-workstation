"""Solver candidates are independently decoded and classified; never counted as hits."""
from hashlib import sha256
import json
import pytest
from rvw.cov import stimulus
from rvw.cov.semantic import value_class
from rvw.common.riscv import decode


def source(tmp_path, xlen=32):
    # Pinned public RV base opcode fields. No core signal names or private data.
    r = [('add',0,0),('sub',0,32),('xor',4,0),('or',6,0),('and',7,0),('slt',2,0),('sltu',3,0)]
    i = [('addi',0),('xori',4),('ori',6),('andi',7),('slti',2),('sltiu',3)]
    text = ''.join(f'{n} rd rs1 rs2 31..25={f7} 14..12={f3} 6..2=12 1..0=3\n' for n,f3,f7 in r)
    text += ''.join(f'{n} rd rs1 imm12 14..12={f3} 6..2=4 1..0=3\n' for n,f3 in i)
    files = {'extensions/rv_i': text, 'arg_lut.csv': '"rd",11,7\n"rs1",19,15\n"rs2",24,20\n"imm12",31,20\n'}
    for name, content in files.items():
        path = tmp_path/name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content)
    manifest = {'schema':'rvw.isa/1', 'isa':f'rv{xlen}i', 'extensions':{'i':{'version':'2.1'}},
                'options':{}, 'source':{'revision':'a'*40, 'files':{k:sha256(v.encode()).hexdigest() for k,v in files.items()}},
                'semantics':{'version':1, 'privilege_modes':['M']}}
    path = tmp_path/'isa.json'
    path.write_text(json.dumps(manifest))
    return path


@pytest.mark.parametrize('xlen', [32,64])
def test_all_170_candidates_decode_and_satisfy_observer_classes(tmp_path, xlen):
    pytest.importorskip('z3')
    from rvw.cov.isa import plan
    from rvw.cov import captured
    manifest = source(tmp_path, xlen)
    @captured.command
    def goals():
        return stimulus.profile(plan(manifest, tmp_path)['isa_plan'])
    selected = goals()
    assert len(selected) == 170
    for index, (goal, target) in enumerate(selected.items()):
        result = stimulus.generate(manifest, tmp_path, goal, tmp_path/str(index), [5,6,7], seed=48)
        assert result['status'] == 'generated'
        assert result['measured_hits'] == []
        assert result['full_plan_bins'] > 170
        values = result['model']
        info = decode(values['instruction'], xlen).as_dict()
        assert info['mnemonic'] == target['instruction']
        assert values['instruction'] >> 7 & 31 == 5
        assert values['instruction'] >> 15 & 31 == 6
        if target['field'] != 'imm12':
            assert value_class(values[target['field']], xlen) == target['value_class']
        else:
            imm = values['instruction'] >> 20
            expected = ('zero' if imm == 0 else 'minimum' if imm == 2048 else
                        'maximum' if imm == 2047 else 'negative' if imm > 2048 else 'positive')
            assert expected == target['value_class']


def test_unsupported_and_missing_backend_keep_denominator(tmp_path, monkeypatch):
    manifest = source(tmp_path)
    result = stimulus.generate(manifest, tmp_path, 'pipeline_hazard', tmp_path/'no-output', [5,6,7])
    assert result['status'] == 'unsupported' and result['supported_bins'] == 170
    assert not (tmp_path/'no-output').exists()
    monkeypatch.setattr(stimulus, 'version', lambda _: 'wrong')
    result = stimulus.generate(manifest, tmp_path, 'sem_add_rs1:["zero"]', tmp_path/'missing', [5,6,7])
    assert result['status'] == 'inconclusive' and result['measured_hits'] == []


def test_invalid_resources_and_seed(tmp_path):
    for registers in ([0,1,2], [1,1,2], [1,2], [1,2,32]):
        with pytest.raises(ValueError, match='three distinct'):
            stimulus.generate('unused', '.', 'unused', tmp_path, registers)
    with pytest.raises(ValueError, match='uint32'):
        stimulus.generate('unused', '.', 'unused', tmp_path, [5,6,7], seed=-1)


def test_replay_and_pinned_source_change(tmp_path):
    pytest.importorskip('z3')
    manifest = source(tmp_path)
    a = stimulus.generate(manifest, tmp_path, 'sem_add_rs1:["other_negative"]', tmp_path/'a', [5,6,7], seed=48)
    b = stimulus.generate(manifest, tmp_path, 'sem_add_rs1:["other_negative"]', tmp_path/'b', [5,6,7], seed=48)
    assert a['source_sha256'] == b['source_sha256']
    assert a['constraints_sha256'] == b['constraints_sha256']
    (tmp_path/'extensions/rv_i').write_text('changed')
    with pytest.raises(ValueError, match='hash mismatch'):
        stimulus.generate(manifest, tmp_path, 'unused', tmp_path/'c', [5,6,7])


def test_unsat_is_only_template_evidence(tmp_path, monkeypatch):
    pytest.importorskip('z3')
    manifest = source(tmp_path)
    original = stimulus.plan
    def impossible(*args):
        result = original(*args)
        add = next(i for i in result['isa_plan']['instructions'] if i['name'] == 'add')
        add['mask'] |= 31 << 7
        add['value'] &= ~(31 << 7)
        return result
    monkeypatch.setattr(stimulus, 'plan', impossible)
    result = stimulus.generate(manifest, tmp_path, 'sem_add_rs1:["zero"]', tmp_path/'unsat', [5,6,7])
    assert result['status'] == 'unsat'
    assert 'not an unreachable-bin proof' in result['reason']
    assert result['measured_hits'] == []
    assert (tmp_path/'unsat/constraints.smt2').is_file()
    assert not (tmp_path/'unsat/payload.S').exists()


def test_cli_mcp_parity(tmp_path):
    import subprocess
    import sys
    from rvw.cov.cli import execute_json
    pytest.importorskip('z3')
    manifest = source(tmp_path)
    result = subprocess.run([sys.executable, '-m', 'rvw', 'cov', 'generate', '--manifest', str(manifest),
        '--source-root', str(tmp_path), '--goal', 'sem_add_rs1:["one"]', '--work-dir', str(tmp_path/'cli'),
        '--registers', '5,6,7', '--seed', '48', '--json'], capture_output=True, text=True)
    assert result.returncode == 0, result.stderr
    cli = json.loads(result.stdout)
    mcp = execute_json('generate', manifest=str(manifest), source_root=str(tmp_path), goal='sem_add_rs1:["one"]',
                       work_dir=str(tmp_path/'mcp'), registers=[5,6,7], seed=48)
    assert cli['status'] == mcp['status'] == 'generated'
    assert cli['source_sha256'] == mcp['source_sha256']
    assert cli['plan_sha256'] == mcp['plan_sha256']


def test_seed_varies_free_operand_without_changing_goal(tmp_path):
    pytest.importorskip('z3')
    manifest=source(tmp_path)
    a=stimulus.generate(manifest,tmp_path,'sem_add_rs1:["zero"]',tmp_path/'a',[5,6,7],seed=1)
    b=stimulus.generate(manifest,tmp_path,'sem_add_rs1:["zero"]',tmp_path/'b',[5,6,7],seed=2)
    assert a['model']['rs1']==b['model']['rs1']==0
    assert a['model']['rs2']!=b['model']['rs2']
    assert a['source_sha256']!=b['source_sha256']
