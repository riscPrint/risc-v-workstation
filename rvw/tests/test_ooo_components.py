from dataclasses import replace
import shutil
import pytest
from rvw.ooo.core import Config, Instruction, simulate
from rvw.ooo.components import Adapter


def config(**kw):
    return replace(Config(2,16,2,32,2,16,8,8,2,{'alu':1,'load':1,'store':1,'branch':1,'jump':1}), **kw)


def test_native_cache_hierarchy_and_warm_reuse():
    if not shutil.which('c++'):
        pytest.skip('native C++ compiler absent')
    components = {'memory': {'dram_latency':20,
        'l1d': {'size_kib':1,'ways':1,'latency':2},
        'l2': {'size_kib':4,'ways':1,'latency':4},
        'llc': {'size_kib':16,'ways':2,'latency':8}}}
    ops = [Instruction('load', dest=1, pc=8, address=64, size=8)] * 4
    r = simulate(ops, config(components=components))
    assert r['instret'] == 4
    memory = r['components']['memory']
    assert memory['l1d']['demand_accesses'] == 4
    assert memory['l1d']['demand_misses'] == 1
    assert r['events']['l1d_demand_misses'] == 1
    assert r['events']['l1d_demand_accesses'] == 4
    assert r['cycles'] > simulate(ops, config())['cycles']


def test_branch_adapter_trains_target_and_preserves_history():
    if not shutil.which('c++'):
        pytest.skip('native C++ compiler absent')
    components = {'btb': {'entries':16,'ways':2,'latency':2}}
    # JAL with rd=0: same direct target repeats; no direction predictor needed.
    op = Instruction('jump', pc=0x100, next_pc=0x200, encoding=0x1000006f)
    with Adapter(components) as adapter:
        assert adapter.predict_instruction(op) == 0x104
        adapter.update_instruction(op)
        assert adapter.predict_instruction(op) == 0x200
        assert adapter.last_delay == 2
        adapter.update_instruction(op)


def test_instruction_cache_and_cross_line_data_access():
    if not shutil.which('c++'):
        pytest.skip('native C++ compiler absent')
    components = {'memory': {'dram_latency':10,
        'l1d': {'size_kib':1,'ways':1,'latency':2},
        'l1i': {'size_kib':1,'ways':1,'latency':2}}}
    with pytest.raises(ValueError, match='explicit frontend'):
        config(components=components)
    ops = [Instruction('load', dest=1, pc=62, address=62, size=8), Instruction('alu', pc=66)]
    r = simulate(ops, config(components=components, frontend={'decode_width':2}))
    assert r['components']['memory']['l1d']['demand_accesses'] == 2
    assert r['components']['memory']['l1i']['demand_accesses'] == 2
    assert r['instret'] == 2


def test_native_direction_and_multilevel_target_prediction():
    if not shutil.which('c++'):
        pytest.skip('native C++ compiler absent')
    components = {'branch': {'model':'bimodal','entries':64},
                  'btb': {'levels':[{'entries':8,'ways':2,'latency':0},
                                   {'entries':32,'ways':2,'latency':2}]}}
    ops = [Instruction('branch', pc=0x100, next_pc=0x100, encoding=0x63), Instruction('alu',pc=0x104)] * 10
    r = simulate(ops, config(components=components, branch_penalty=4))
    assert r['instret'] == 20
    assert 0 < r['events']['branch_misses'] < 10
    assert r['events']['btb_level_0_hits'] > 0
    assert 'direction' in r['components']
