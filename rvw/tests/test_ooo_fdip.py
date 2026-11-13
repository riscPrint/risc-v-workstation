"""FTQ runahead and explicit native instruction prefetch traffic."""
from dataclasses import replace
import shutil
import pytest
from rvw.ooo.core import Config, Instruction, simulate
from rvw.ooo.frontend import Frontend, FrontendConfig
from rvw.csim.lib import Components

pytestmark=pytest.mark.fast


def test_ftq_runahead_is_bounded_and_targets_wait_for_prediction():
    class Memory:
        def __init__(self): self.requests=[]
        def prefetch(self,first,last,cycle): self.requests.append((first.pc,last.pc,cycle))
        def fetch(self,op,cycle): return 0
    memory=Memory()
    f=Frontend(dict(fdip=True,ftq_entries=2,block_bytes=16,predictor_latency=2,decode_entries=1),4,4)
    ops=[Instruction('alu',pc=4*i) for i in range(64)]
    f.advance(0,ops,memory=memory)
    assert not f.fetch
    assert memory.requests==[(0,12,0)]
    for cycle in range(1,30):
        f.advance(cycle,ops,memory=memory)
        assert len(f.targets)<=2
        assert f.predicted_position>=f.position
    assert f.events['fdip_ftq_full']>0
    requests=len(memory.requests)
    f.advance(30,ops,blocked=True,memory=memory)
    assert len(memory.requests)==requests


def test_component_prefetch_and_missing_cache():
    if not shutil.which('c++'): pytest.skip('native C++ compiler absent')
    with Components({}) as c:
        with pytest.raises(ValueError,match='l1i'):
            c.prefetch_instruction(0,0x100,0x100)
    with Components({'memory':{'dram_latency':20,'l1i':{'size_kib':1,'ways':1,'latency':2}}}) as c:
        c.prefetch_instruction(0,0x100,0x100)
        c.access(100,0x100,0x100,fetch=True)
        stats=c.stats(1)['memory']['l1i']
        assert stats['prefetch']['issued']==1
        assert stats['prefetch']['useful']==1
        assert stats['demand_misses']==0
        with pytest.raises(ValueError,match='unsigned'):
            c.prefetch_instruction(-1,0,0)


def test_fdip_runs_with_shared_cache_and_preserves_retirement():
    if not shutil.which('c++'): pytest.skip('native C++ compiler absent')
    config=Config(4,32,4,32,4,16,8,8,4,{'alu':1},
                  frontend={'fdip':True,'ftq_entries':4,'block_bytes':16},
                  components={'memory':{'dram_latency':20,'l1i':{'size_kib':1,'ways':1,'latency':2}}})
    ops=[Instruction('alu',pc=0x100+4*i) for i in range(64)]
    r=simulate(ops,config)
    assert r['instret']==64
    assert r['events']['fdip_targets']==16
    assert r['events']['fdip_line_requests']==16
    assert r['components']['memory']['l1i']['prefetch']['issued']>0
    baseline=simulate(ops,replace(config,frontend={**config.frontend,'fdip':False}))
    assert baseline['instret']==r['instret']
    assert r['cycles']<baseline['cycles']
    with pytest.raises(ValueError,match='l1i'):
        replace(config,components={})
    with pytest.raises(ValueError,match='boolean'):
        FrontendConfig(fdip=1)
