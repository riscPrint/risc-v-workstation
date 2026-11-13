"""Independent trace oracles for the unbounded SVA acceptance monitors."""
from itertools import product

import pytest

from rvw.formal.liveness import lower_live
from rvw.formal.temporal import Unsupported

pytestmark = pytest.mark.fast

# Also consumed by the generated support table. Each row has paired native tests.
SUPPORT_FEATURES = ['s_eventually', 'until', 'until_with', 's_until', 's_until_with',
                    '##[M:$]', '[*M:$]', '[*]', '[->N]', '[=N]',
                    'strong / weak', 'unbounded first_match']


def lower(expr):
    return lower_live('module m(input clk, req, a, b); p: assert property (@(posedge clk) '
                      + expr + '); endmodule', 'm')


@pytest.mark.parametrize('expr', [
    'req |=> s_eventually b', 'req |-> a until b', 'req |-> a until_with b',
    'req |-> a s_until b', 'req |-> a s_until_with b',
    'req |-> strong(a ##[2:$] b)', 'req |-> weak(##[0:$] b)',
    'req |-> strong(a[*2:$] ##1 b)', 'req |-> a[*] ##1 b',
    'req |-> strong(a[->3])', 'req |-> strong(a[=3] ##1 b)',
    'req |=> strong(first_match(a[->2] ##1 b))',
])
def test_lower_unbounded(expr):
    rtl, rows, finite = lower(expr)
    assert len(rows) == 1 and not finite
    assert '(* keep *) wire rvw_live_0' in rtl
    assert not any(word in rtl for word in ('s_eventually', 'until', 'strong(', 'first_match('))


@pytest.mark.parametrize('expr', [
    'req |-> strong(a[->65])', 'req |-> strong(a[=0])',
    'req |-> strong(a[->2:4])', 'req |-> strong(a ##[65:$] b)',
    'req |-> a[*]', 'req |-> strong((a ##1 b)[*2:$])',
    'req |-> strong(a[->2] ##2 b)', 'req |-> (a s_until b) s_until b',
    'req |-> s_eventually $future(b)', 'disable iff(a) req |-> s_eventually b',
    'req |-> s_eventually (a ##1 b)',
])
def test_refusals(expr):
    with pytest.raises(ValueError):
        lower(expr)


def test_weak_is_not_silently_strengthened():
    weak, rows, _ = lower('req |-> a[->2]')
    strong, _, _ = lower('req |-> strong(a[->2])')
    assert rows[0]['strength'] == 'weak'
    assert "wire rvw_live_0 = 1'b1;" in weak
    assert 'wire rvw_live_0 = (rvw_live_0_owed == 0);' in strong


def test_native_checks_are_not_discarded():
    with pytest.raises(Unsupported, match='mixed_liveness_safety'):
        lower_live('module m(input clk,a); always @(posedge clk) assert(a); '
                   'assert property (@(posedge clk) s_eventually a); endmodule', 'm')


def goto_accept(prefix, loop, count):
    # Specification: each request must have count events at or after its sample.
    if any(event for _, event in loop):
        return True
    if any(req for req, _ in loop):
        return False
    return all(sum(event for _, event in prefix[t:]) >= count
               for t, (req, _) in enumerate(prefix) if req)


def bucket_accept(prefix, loop, count):
    active = owed = 0
    seen, progress = {}, []
    time = 0
    while True:
        phase = time if time < len(prefix) else len(prefix)+(time-len(prefix)) % len(loop)
        state = phase, active, owed
        if state in seen:
            return any(progress[seen[state]:])
        seen[state] = time
        req, event = prefix[time] if time < len(prefix) else loop[(time-len(prefix)) % len(loop)]
        advanced = active >> 1 if event else active
        born = (1 << (count-1)) >> int(event) if req else 0
        active = advanced | born
        owed = active if owed == 0 else owed >> 1 if event else owed
        progress.append(owed == 0)
        time += 1


@pytest.mark.parametrize('count', [1,2,3])
def test_overlapping_goto_lassos(count):
    pairs = list(product((False,True), repeat=2))
    for prefix_len in range(3):
        for loop_len in range(1,4):
            for prefix in product(pairs, repeat=prefix_len):
                for loop in product(pairs, repeat=loop_len):
                    assert bucket_accept(prefix,loop,count) == goto_accept(prefix,loop,count)
    # Requests at every sample must not prevent old attempts from completing.
    assert bucket_accept((), ((True,True),), count)
