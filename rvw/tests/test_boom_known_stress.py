"""The BOOM LSU waiver must not cover a different failure or workload."""
from rvw.regress.config import load_config
from rvw.regress.known import load_known
from rvw.regress.compare import compare
from test_regress import T, _res


def test_boom_stress_waiver_keeps_exact_scope():
    entries = load_known(load_config('boom').known_failures)
    def covered(suite='stress', tid='qsort', signature='assert:lsu.scala:1241', config='large'):
        return any(e.matches(suite, tid, signature, config) for e in entries)
    assert covered()
    assert not covered(signature='assert:lsu.scala:1242')
    assert not covered(signature='assert:dcache.scala:1241')
    assert not covered(signature='timeout')
    assert not covered(signature='fail:3')
    assert not covered(config='small')
    assert not covered(tid='median')
    assert not covered(suite='benchmarks')


def test_boom_stress_changed_assertion_rejects():
    entries = load_known(load_config('boom').known_failures)
    base = _res([T('qsort', 'pass')])
    cand = _res([T('qsort', 'assert', 'assert:lsu.scala:1241')])
    for result in (base, cand):
        result.core, result.suite, result.config = 'boom', 'stress', 'large'
    assert compare([base], [cand], entries).known_failures
    cand.tests[0].signature = 'assert:lsu.scala:1242'
    changed = compare([base], [cand], entries)
    assert changed.verdict == 'reject'
    assert changed.new_failures
    assert not changed.known_failures
