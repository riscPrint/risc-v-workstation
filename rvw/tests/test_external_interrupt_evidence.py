import copy
import io
import json
import pytest
from rvw.cosim.trace import Trace
from rvw.cosim.external_interrupts import SCHEMA, validate

pytestmark = pytest.mark.fast
HEADER = dict(schema='rvw.rvfi/1', xlen=64, isa='rv64i', core='fixture', config='test', elf='fixture',
              external_interrupts=dict(schema=SCHEMA))
EVENTS = [dict(kind='pins', levels='0x800'), dict(kind='source', source=1, level=True),
          dict(kind='mmio', address='0xc200004', bytes=4, value='0x1', write=False),
          dict(kind='mmio', address='0xc200004', bytes=4, value='0x1', write=True),
          dict(kind='ack', address='0x80001008', bytes=8, value='0x2', step=2),
          dict(kind='taken', cause='0x800000000000000b')]


def test_trace_accepts_declared_ordered_external_events():
    rows = [dict(event='external_interrupt', cycle=i, seq=i, before_order=0, **r) for i, r in enumerate(EVENTS)]
    trace = Trace(io.StringIO('\n'.join(map(json.dumps, [HEADER, *rows, dict(event='end', cycle=6, status='pass')]))))
    assert len(list(trace)) == 7


@pytest.mark.parametrize('patch', [dict(seq=1), dict(before_order=1), dict(bytes=3), dict(value='0x100000000'), dict(write=1)])
def test_bad_order_or_access_is_refused(patch):
    event = dict(event='external_interrupt', seq=0, before_order=0, **EVENTS[2], **{})
    event.update(patch)
    with pytest.raises(ValueError):
        validate(event, HEADER, 0, 0)


def test_undeclared_evidence_is_refused():
    with pytest.raises(ValueError, match='declaration'):
        validate(dict(seq=0, before_order=0, **EVENTS[0]), dict(xlen=64), 0, 0)
