from types import SimpleNamespace
from rvw.ooo.control import supported


def test_only_nonblocking_system_returns_are_supported():
    assert supported(SimpleNamespace(cls='system',mnemonic='mret'))
    assert not supported(SimpleNamespace(cls='system',mnemonic='wfi'))
    assert not supported(SimpleNamespace(cls='system',mnemonic='ecall'))
    assert supported(SimpleNamespace(cls='csr',mnemonic='csrrw'))


def test_csr_and_fence_serialize_older_execution():
    from rvw.ooo.core import Config, Instruction, simulate
    c = Config(4,16,4,32,4,16,4,4,4,{'alu':1,'divide':12,'csr':1,'fence':1,'system':1})
    ops = [Instruction('divide',(),1), Instruction('fence'), Instruction('alu',(),2)]
    r = simulate(ops,c)
    assert r['cycles'] >= 17
    assert r['events']['control_serialize_blocked'] > 0
    assert r['events']['issued'] == 3


def test_c2_startup_csr_is_accepted_with_declared_latency(tmp_path):
    import json
    from dataclasses import asdict
    from test_ooo import trace
    from rvw.ooo.core import Config, run
    config = Config(2,4,2,8,2,4,2,2,2,{'csr':1})
    path,c2 = tmp_path/'config.json',tmp_path/'trace.jsonl'
    path.write_text(json.dumps(asdict(config)))
    trace(c2,insn='0xf1402573')  # csrr a0,mhartid
    r = run(path,c2)
    assert r['instret'] == 4
    assert r['accuracy_status'] == 'inconclusive'


def test_fence_i_does_not_silently_preserve_uop_cache():
    import pytest
    from rvw.ooo.core import Config, Instruction, simulate
    c = Config(2,4,2,8,2,4,2,2,2,{'fence':1},frontend={'uop_cache_entries':8})
    with pytest.raises(ValueError,match='invalidation'):
        simulate([Instruction('fence',mnemonic='fence.i')],c)
