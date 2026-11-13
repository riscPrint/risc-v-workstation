from rvw.formal.counter_quotient import generate
import pytest


def test_counter_model_relation_and_low_reset_binding():
    small, harness, expected = generate({'top': 'wide', 'width': 32, 'keep_bits': 4,
        'reset_active': 'low', 'ports': {'clock': 'clock', 'reset': 'resetn', 'enable': 'inc', 'count': 'value'}})
    assert '[3:0] count' in small and 'if(enable)' in small
    assert '.resetn(!reset)' in harness
    assert 'concrete_count[3:0] == abstract_count' in harness
    assert expected['value'] == ('output', 32)


@pytest.mark.parametrize('width,keep', [(4, 4), (4, 0), (257, 4), (4, True)])
def test_invalid_projection_rejected(width, keep):
    with pytest.raises(ValueError):
        generate({'top': 'wide', 'width': width, 'keep_bits': keep})


def test_native_reset_qualified_relation_and_refuted_candidate(tmp_path):
    import hashlib
    import json
    import shutil
    from argparse import Namespace
    from rvw.formal.counter_quotient import run
    if not all(shutil.which(t) for t in ['yosys', 'sby', 'yosys-abc']):
        pytest.skip('optional native formal tools missing')
    ports = {'clock': 'clock', 'reset': 'resetn', 'enable': 'go', 'count': 'value'}
    for name, step in [('safe', 1), ('bad', 2)]:
        source = tmp_path / (name + '.sv')
        source.write_text(f'module wide(input clock,resetn,go,output reg[15:0] value); '
                          f'always @(posedge clock) if(!resetn) value<=0; else if(go) value<=value+{step}; endmodule')
        plan = {'top': 'wide', 'width': 16, 'keep_bits': 3, 'ports': ports, 'reset_active': 'low',
                'sources': [{'path': source.name, 'sha256': hashlib.sha256(source.read_bytes()).hexdigest()}]}
        manifest = tmp_path / (name + '.json')
        manifest.write_text(json.dumps(plan))
        out = tmp_path / name
        rc = run(Namespace(manifest=str(manifest), out=str(out), timeout=15, depth=8, engine='abc:pdr', json=True))
        r = json.loads((out / 'result.json').read_text())
        assert r['restrictions']
        if name == 'safe':
            assert rc == 0 and r['status'] == 'pass'
            assert r['proof_kind'] == 'unbounded_reset_qualified_counter_relation'
        else:
            assert rc == 1 and r['status'] == 'inconclusive'
            assert r['reason'] == 'obligation_failed'
