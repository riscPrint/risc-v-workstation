import io
import json
import pytest
from rvw.cosim.trace import Trace
from test_state import fixture


def test_combined_state_and_multihart():
    h, row = fixture()
    h.update(harts=[0, 1], capabilities=['state', 'multihart'], csr_snapshot=['0x300'])
    row.update(hart=0, epoch=0, order='0', capture_seq='1', csr_state={'0x300': '0x0'}, trap=True,
               fault_access=dict(addr='0x0', rmask=1, wmask=0, completed_rmask=0,
                                 completed_wmask=0, rdata=None, wdata=None))
    records = [dict(event='reset', hart=0, epoch=0, cycle=0, capture_seq='0'), row]
    parsed = list(Trace(io.StringIO('\n'.join(map(json.dumps, [h, *records])))))
    assert parsed[1]['fd_wdata'] == int(row['fd_wdata'], 16)
    assert parsed[1]['csr_state'] == {'0x300': 0}
    assert parsed[1]['fault_access']['rmask'] == 1
    del row['fcsr']
    with pytest.raises(ValueError):
        list(Trace(io.StringIO('\n'.join(map(json.dumps, [h, *records])))))
