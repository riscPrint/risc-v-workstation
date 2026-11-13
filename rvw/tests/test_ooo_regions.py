import json
from dataclasses import replace
import pytest
from rvw.ooo.core import Config, Instruction, simulate
from rvw.ooo.regions import Regions, compare, profile, elf_ranges

pytestmark = pytest.mark.fast


def config():
    return Config(2, 8, 2, 16, 2, 8, 4, 4, 2,
                  {'alu': 1, 'load': 8, 'branch': 1}, branch_penalty=5)


def test_region_partition_and_memory_dependency():
    c = config()
    ops = [Instruction('load', dest=1, pc=0), Instruction('alu', (1,), 2, pc=4),
           Instruction('branch', pc=8, next_pc=0)]
    a = Regions(2, [(0,8,'kernel'), (8,12,'branch')])
    result = simulate(ops, c, observer=a)
    r = a.report()
    assert sum(r['slots'].values()) == 2*result['cycles']
    assert r['slots']['retiring'] == 3
    assert r['slots']['backend_memory_bound'] > 0
    assert r['slots']['bad_speculation'] > 0
    assert sum(v['total_slots'] for v in r['regions'].values()) == r['total_slots']
    assert r['regions']['kernel']['slots']['retiring'] == 2
    assert r['regions']['branch']['slots']['retiring'] == 1
    assert result == simulate(ops, c, backend='python')


def test_region_validation():
    with pytest.raises(ValueError, match='nonoverlapping'):
        Regions(2, [(0,8,'a'), (4,12,'b')])
    a = Regions(2, [(0,8,'a')])
    assert a.name(8) == '<unmapped>'
    assert a.name(None) == '<pipeline-empty>'


def test_profile_and_diff(tmp_path):
    from test_ooo import trace
    from dataclasses import asdict
    t = tmp_path/'trace.jsonl'
    trace(t)
    cfg = tmp_path/'cfg.json'
    cfg.write_text(json.dumps(asdict(config())))
    a = profile(cfg,t)
    cfg.write_text(json.dumps(asdict(replace(config(), latencies={'alu':4}))))
    b = profile(cfg,t)
    pa, pb = tmp_path/'a.json', tmp_path/'b.json'
    pa.write_text(json.dumps(a)); pb.write_text(json.dumps(b))
    r = compare(pa,pb)
    assert r['cycles_saved'] < 0
    assert r['slot_delta']['retiring'] == 0
    assert sum(r['slot_delta'].values()) == 2*(b['cycles']-a['cycles'])
    b['trace_sha256'] = 'different'
    pb.write_text(json.dumps(b))
    with pytest.raises(ValueError, match='same trace'):
        compare(pa,pb)


def test_elf_join(tmp_path):
    # Reuse the standard ELF reader and supply only executable sized symbols.
    import struct
    p = tmp_path/'test.elf'
    data = bytearray(512)
    data[:6] = b'\x7fELF\x02\x01'
    struct.pack_into('<QQ',data,0x20,0,64)
    struct.pack_into('<HHHHH',data,0x36,56,0,64,4,0)
    struct.pack_into('<IIQQQQIIQQ',data,64+64,0,1,6,0x1000,320,8,0,0,4,0)
    names = b'\0kernel\0'
    struct.pack_into('<IIQQQQIIQQ',data,64+128,0,3,0,0,400,len(names),0,0,1,0)
    struct.pack_into('<IIQQQQIIQQ',data,64+192,0,2,0,0,424,24,2,0,8,24)
    data[400:400+len(names)] = names
    struct.pack_into('<IBBHQQ',data,424,1,2,0,1,0x1000,8)
    p.write_bytes(data)
    assert elf_ranges(p) == [(0x1000,0x1008,'kernel')]
