from rvw.common.riscv import decode
from rvw.ooo.floating import operands


def test_fp_zero_register_is_a_real_register():
    # fadd.s f0,f0,f1: f0 maps to 32, not immutable integer x0.
    word = 0x53 | 1 << 20
    assert operands(decode(word), dict(insn=word,rd=0)) == ('fp_fadd',(32,33),32)


def test_fp_load_and_fma_bank_mapping():
    word = 0x3007 | 1 << 7 | 2 << 15
    assert operands(decode(word), dict(insn=word,rd=0)) == ('load',(2,),33)
    word = 0x43 | 1 << 7 | 2 << 15 | 3 << 20 | 4 << 27
    assert operands(decode(word), dict(insn=word,rd=0)) == ('fp_fmadd',(34,35,36),33)


def test_fp_dependencies_and_separate_pressure():
    from dataclasses import replace
    from rvw.ooo.core import Config, Instruction, simulate
    c = Config(4,16,4,32,4,16,4,4,4,{'fp_fadd':3},physical_float_registers=33)
    ops = [Instruction('fp_fadd',(32,33),32), Instruction('fp_fadd',(32,33),34)]
    constrained = simulate(ops,c)
    assert constrained['events']['float_register_full'] > 0
    assert constrained['cycles'] >= simulate(ops,replace(c,physical_float_registers=0))['cycles']
    # f0 is mutable. Its consumer must wait, unlike an integer x0 consumer.
    independent = [Instruction('fp_fadd',(33,34),32), Instruction('fp_fadd',(33,34),35)]
    assert simulate(ops,replace(c,physical_float_registers=0))['cycles'] > simulate(independent,replace(c,physical_float_registers=0))['cycles']


def test_fp_c2_uses_encoded_destination_bank(tmp_path):
    import json
    from dataclasses import asdict
    from test_ooo import trace
    from rvw.ooo.core import Config, run
    config = Config(2,4,2,8,2,4,2,2,2,{'fp_fadd':3})
    path,c2 = tmp_path/'config.json',tmp_path/'trace.jsonl'
    path.write_text(json.dumps(asdict(config)))
    trace(c2,insn='0x00100053')
    rows = [json.loads(line) for line in c2.read_text().splitlines()]
    rows[0]['isa'] = 'rv64gc'
    c2.write_text(''.join(json.dumps(row)+'\n' for row in rows))
    r = run(path,c2)
    assert r['instret'] == 4
    assert r['cycles'] >= 14
    assert r['accuracy_status'] == 'inconclusive'
