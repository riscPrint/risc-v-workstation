import copy
import pytest
from rvw.privilege.scheduled import programs, clock_check


pytestmark = pytest.mark.fast


def samples():
    return [dict(tick=i, clock_running=i not in (1, 2), state={'x': 42},
                 retired=4 if i < 3 else 5, pending=i == 2) for i in range(4)]


def test_matrix():
    rows = programs({'wake': {'assert_cycle': 1000, 'clear_cycle': 20000}})
    assert len(rows) == 6
    assert {r['options']['irq_schedule'] for r in rows} == {
        f'1:0x0,1000:0x{1 << c:x},20000:0x0' for c in (3, 7, 11)}
    assert all('reference_unavailable' in r for r in rows)


def test_stop_resume():
    assert clock_check(samples(), {'x': 0xff})['status'] == 'pass'


@pytest.mark.parametrize('field,value,expected', [
    ('state', {'x': 43}, 'fail'), ('state', {}, 'inconclusive'),
    ('retired', 5, 'fail'), ('retired', None, 'inconclusive')])
def test_pause_mutations(field, value, expected):
    rows = samples(); rows[1][field] = value
    assert clock_check(rows, {'x': 0xff})['status'] == expected


def test_missing_pending_and_resume():
    for field in ('pending', 'retired'):
        rows = samples()
        for row in rows:
            row[field] = False if field == 'pending' else 4
        assert clock_check(rows, {'x': 0xff})['status'] == 'inconclusive'
    assert clock_check([], {'x': 1})['status'] == 'inconclusive'


def test_stimulus_ack_read_is_reference_blind_only_for_that_word(tmp_path):
    import json
    from rvw.privilege.campaign import reference_blind
    platform = tmp_path / 'p.json'
    platform.write_text(json.dumps({'irq_inputs': [], 'mmio': []}))
    def comparison(address, fields=('mem_rdata', 'rd_wdata')):
        return {'mismatch': {'differences': dict.fromkeys(fields, {}),
                             'actual': {'insn': '0x2b303', 'rd_wdata': '0xa', 'mem_addr': hex(address)},
                             'expected': {'rd_wdata': '0x0'}}}
    assert 'stimulus_ack' in reference_blind(comparison(0x80001008), platform, 0x80001008)
    assert reference_blind(comparison(0x80001008), platform) is None
    assert reference_blind(comparison(0x80001010), platform, 0x80001008) is None
    assert reference_blind(comparison(0x80001008, ('pc',)), platform, 0x80001008) is None
