import pytest
from rvw.ooo.custom import decode, validate


def rule():
    return dict(name='custom_mac', mask=0x7f, match=0x0b, sources=['rs1','rs2'], writes_rd=True)


def test_register_mapping_and_opcode_overlap():
    r = rule()
    validate([r], {'custom_mac': 3})
    row = dict(insn=0x0b | 3 << 7 | 1 << 15 | 2 << 20,
               rs1=1, rs2=2, rd=3, pc=0, pc_next=4, mem_rmask=0, mem_wmask=0)
    assert decode(row, [r]) == ('custom_mac', (1,2), 3)
    row['rd'] = 0
    with pytest.raises(ValueError, match='destination'):
        decode(row, [r])
    with pytest.raises(ValueError, match='overlap'):
        validate([r,r], {'custom_mac':3})


def test_custom_cannot_override_standard_or_hide_control_flow():
    r = rule(); r['match'] = 0x33
    with pytest.raises(ValueError, match='reserved'):
        validate([r], {'custom_mac':3})
    r = rule()
    row = dict(insn=0x0b, rs1=0, rs2=0, rd=0, pc=0, pc_next=8, mem_rmask=0, mem_wmask=0)
    with pytest.raises(ValueError, match='fallthrough'):
        decode(row,[r])


def test_custom_c2_uses_project_latency_and_dependencies(tmp_path):
    import json
    from dataclasses import asdict
    from test_ooo import trace
    from rvw.ooo.core import Config, run
    config = Config(2, 4, 2, 8, 2, 4, 2, 2, 2, {'custom_mac': 3}, custom_instructions=[rule()])
    path = tmp_path/'config.json'; path.write_text(json.dumps(asdict(config)))
    c2 = tmp_path/'trace.jsonl'; trace(c2)
    rows = [json.loads(line) for line in c2.read_text().splitlines()]
    for i,row in enumerate(rows[1:-1]):
        row.update(insn=hex(0x0b | 1 << 7 | 1 << 15 | 2 << 20), rs1=1, rs2=2, rd=1,
                   pc=hex(4*i), pc_next=hex(4*i+4))
    c2.write_text(''.join(json.dumps(row)+'\n' for row in rows))
    result = run(path,c2)
    assert result['instret'] == 4
    assert result['cycles'] >= 14
    assert result['events']['issued'] == 4
    assert result['accuracy_status'] == 'inconclusive'
    config.latencies['custom_mac'] = 1
    path.write_text(json.dumps(asdict(config)))
    assert run(path,c2)['cycles'] < result['cycles']
