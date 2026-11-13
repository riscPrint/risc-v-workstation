import copy
import json
from rvw.cosim.checker import check
from rvw.cosim.platform import Platform
from rvw.cosim.trace import record


def test_native_shared_store_load_and_mismatch(tmp_path, tmp_path_factory):
    from cosim_build import _build
    from model_fixtures import Spike
    source = tmp_path/'shared.S'
    source.write_text('''.section .text
.globl _start
_start:
 csrr t0, mhartid
 bnez t0, reader
 li t1, 0x80001000
 li t2, 7
 sd t2, 0(t1)
 j done
reader:
 li t1, 0x80001000
 ld a0, 0(t1)
done:
 wfi
''')
    elf = _build(tmp_path_factory, source)
    platform = Platform.load('boom')
    rows = [dict(schema='rvw.rvfi/2', xlen=64, isa=platform.isa, core='fixture', config='test',
                 elf=str(elf), harts=[0, 1], capabilities=['multihart'], memory_profile='serialized-retirement')]
    def append(hart, row):
        row.update(hart=hart, epoch=0, capture_seq=str(len(rows)-1))
        rows.append(row)
    for hart in (0, 1):
        append(hart, dict(event='reset', cycle=0))
    model = Spike(platform, elf)
    load_index = None
    try:
        model.add_hart(1)
        for hart in (0, 1):
            model.select_hart(hart)
            model.regs = [0]*32
            for order in range(30):
                effect = model.step()
                row = record(effect, order, cycle=len(rows))
                row['order'] = str(order)
                append(hart, row)
                if hart == 1 and effect['rd'] == 10:
                    assert effect['rd_wdata'] == 7
                    load_index = len(rows)-1
                if effect['insn'] == 0x10500073:
                    append(hart, dict(event='hart_end', cycle=len(rows), status='pass'))
                    break
            else:
                raise AssertionError('fixture did not finish')
    finally:
        model.close()
    assert load_index is not None
    for mutate in (False, True):
        trace_rows = copy.deepcopy(rows)
        if mutate:
            trace_rows[load_index]['rd_wdata'] = '0x8'
        trace = tmp_path/'trace.jsonl'
        trace.write_text('\n'.join(map(json.dumps, trace_rows)))
        model = Spike(platform, elf)
        try:
            result = check(trace, model, platform, sync=())
            assert result['status'] == ('mismatch' if mutate else 'match'), result
            assert result['memory_profile'] == 'serialized-retirement'
            if mutate:
                assert result['hart'] == 1
                assert 'rd_wdata' in result['mismatch']['differences']
        finally:
            model.close()
