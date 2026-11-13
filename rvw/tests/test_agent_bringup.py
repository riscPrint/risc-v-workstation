"""Bring-up check wiring (no native tools): fixture, placeholders, guide steps, refusal."""
import pytest

from rvw.agent import bringup, guide


def test_fixture_core_has_the_seeded_bug_and_the_guide_steps_exist():
    source = (bringup.HERE / 'core/src/main/scala/tiny/TinyCore.scala').read_text()
    assert source.count(bringup.FIX) == 1 and bringup.BUG not in source
    assert (bringup.HERE / 'CoreAdapter.scala').read_text().count('object Adapter extends CoreAdapter') == 1
    data = guide.load()
    steps = {(w['id'], s['id']) for w in data['workflows'] for s in w['steps']}
    for pair in [('bring-up', s) for s in ('doctor', 'init-plan', 'init', 'map-adapter', 'smoke', 'regress-list',
                                           'quick', 'cosim', 'gate', 'design-db')] + \
                [('test-fails', s) for s in ('bundle', 'cosim', 'drivers', 'fix', 'gate')]:
        assert pair in steps, pair


def test_placeholders_and_refusal(tmp_path):
    assert bringup._subst('<RUN>/rvfi.jsonl', {'RUN': '/x'}) == '/x/rvfi.jsonl'
    assert bringup._subst('<UNKNOWN>', {}) == '<UNKNOWN>'
    with pytest.raises(ValueError):
        bringup.run_check(tmp_path)
