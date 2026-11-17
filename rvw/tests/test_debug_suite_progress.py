"""Target progress must report final results and preserve driver ownership."""
from types import SimpleNamespace

import pytest

from rvw.debug import api, checks, profile, suite  # noqa: F401

pytestmark = pytest.mark.fast


@pytest.fixture
def campaign(monkeypatch):
    calls = []
    target = SimpleNamespace(close=lambda: calls.append('close'))
    model = object()
    items = [suite.Check(f'unit.{name}', 'unit', None, '') for name in ('first', 'skip', 'last')]
    monkeypatch.setattr(suite, 'CHECKS', {c.id: c for c in items})
    monkeypatch.setattr(suite, 'open_target', lambda p, **kw: target)
    monkeypatch.setattr(suite, 'model_driver', lambda p: (model, None))

    def run_one(item, prof, driver):
        calls.append(('target' if driver is target else 'reference', item.id))
        return dict(id=item.id, group=item.group, status='pass', observations={'value': 1},
                    dmi_accesses=0, wall_s=0)

    monkeypatch.setattr(suite, 'run_one', run_one)
    prof = profile.normalize({'transport': {'kind': 'jtag-model'},
                              'skip': {'unit.skip': 'not available'}})
    return prof, calls, target, model, run_one


def test_selection_order_skips_and_reference_are_distinct(campaign):
    prof, calls, _, _, _ = campaign
    events = []

    def progress(event, item, entry):
        events.append((event, item.id, entry))
        calls.append((event, item.id))

    rows = suite.run(prof, groups=['unit'], ids=['unit.last', 'unit.skip'], progress=progress)
    assert calls == [('start', 'unit.skip'), ('finish', 'unit.skip'),
                     ('start', 'unit.last'), ('target', 'unit.last'), ('reference', 'unit.last'),
                     ('finish', 'unit.last'), 'close']
    assert [(e, i) for e, i, _ in events] == [
        ('start', 'unit.skip'), ('finish', 'unit.skip'),
        ('start', 'unit.last'), ('finish', 'unit.last')]
    assert events[0][2] is None and events[2][2] is None
    assert events[1][2] == rows[0]
    assert rows[0]['status'] == 'unsupported'
    assert rows[0]['reason'] == 'skipped by profile: not available'
    assert events[3][2] == rows[1]
    assert rows[1]['reference_status'] == 'pass'


@pytest.mark.parametrize('case,expected', [('diff', 'fail'), ('missing', 'fail'),
                                          ('reference_fail', 'inconclusive'), ('target_fail', 'fail')])
def test_finish_has_final_reference_verdict(monkeypatch, campaign, case, expected):
    prof, _, target, _, original = campaign

    def run_one(item, p, driver):
        row = original(item, p, driver)
        if driver is target and case == 'diff':
            row['observations']['value'] = 2
        if driver is target and case == 'missing':
            row['observations'] = {}
        if (driver is target and case == 'target_fail') or (driver is not target and case == 'reference_fail'):
            row.update(status='fail', message='rule failed')
        return row

    monkeypatch.setattr(suite, 'run_one', run_one)
    events = []
    rows = suite.run(prof, ids=['unit.first'], progress=lambda *args: events.append(args))
    assert events[-1][0] == 'finish'
    assert events[-1][2] == rows[0]
    assert rows[0]['status'] == expected
    assert 'reference_status' in rows[0]


@pytest.mark.parametrize('event', ['start', 'finish'])
@pytest.mark.parametrize('owned', [False, True])
def test_callback_error_aborts_and_closes_only_owned_driver(campaign, event, owned):
    prof, calls, target, _, _ = campaign

    def progress(phase, item, entry):
        if phase == event:
            raise RuntimeError('progress failed')

    with pytest.raises(RuntimeError, match='progress failed'):
        suite.run(prof, driver=None if owned else target, progress=progress)
    assert calls.count('close') == int(owned)
    assert not any(isinstance(c, tuple) and c[1] == 'unit.last' for c in calls)
    if event == 'start':
        assert calls == (['close'] if owned else [])


@pytest.mark.parametrize('reference', [False, True])
def test_callback_snapshot_cannot_change_results(campaign, reference):
    prof, _, _, _, _ = campaign

    def progress(event, item, entry):
        if entry is not None:
            entry['status'] = 'fail'
            entry['observations']['value'] = 999

    rows = suite.run(prof, ids=['unit.first'], reference=reference, progress=progress)
    assert rows[0]['status'] == 'pass'
    assert rows[0]['observations'] == {'value': 1}
    assert ('reference_status' in rows[0]) == reference


def test_empty_selection_has_no_progress(campaign):
    prof, calls, _, _, _ = campaign
    assert suite.run(prof, ids=['no.check'], progress=lambda *a: pytest.fail('unexpected event')) == []
    assert calls == ['close']


def test_api_forwards_progress_and_writes_final_results(tmp_path):
    path = tmp_path / 'profile.toml'
    path.write_text('schema = "rvw.debug-profile/1"\nname = "self-test"\n'
                    '[transport]\nkind = "model"\n')
    events = []
    result = api.suite_run(tmp_path / 'out', profile=path, checks=['dm.halt'],
                           progress=lambda *args: events.append(args))
    assert result['status'] == 'pass'
    assert [(e, c.id) for e, c, _ in events] == [('start', 'dm.halt'), ('finish', 'dm.halt')]
    assert events[-1][2]['status'] == 'pass'
    assert events[-1][2]['dmi_accesses'] > 0


@pytest.mark.parametrize('status', ['unsupported', 'inconclusive'])
def test_nonverdict_target_results_do_not_run_reference(monkeypatch, campaign, status):
    prof, calls, _, _, original = campaign

    def run_one(*args):
        return {**original(*args), 'status': status, 'reason': 'cannot exercise rule'}

    monkeypatch.setattr(suite, 'run_one', run_one)
    events = []
    rows = suite.run(prof, ids=['unit.first'], progress=lambda *args: events.append(args))
    assert calls == [('target', 'unit.first'), 'close']
    assert events[-1][2] == rows[0]
    assert rows[0]['status'] == status


@pytest.mark.parametrize('comparison', ['disabled', 'timing', 'model'])
def test_no_reference_when_comparison_does_not_apply(campaign, comparison):
    prof, calls, target, _, _ = campaign
    if comparison == 'timing':
        suite.CHECKS['unit.first'].reference = False
    if comparison == 'model':
        prof['transport']['kind'] = 'model'
    events = []
    rows = suite.run(prof, driver=target, ids=['unit.first'], reference=comparison != 'disabled',
                     progress=lambda *args: events.append(args))
    assert calls == [('target', 'unit.first')]
    assert len(events) == 2
    assert events[-1][2] == rows[0]
    assert 'reference_status' not in rows[0]


def test_skip_callback_failure_still_closes_driver(campaign):
    prof, calls, _, _, _ = campaign

    def progress(event, item, entry):
        if event == 'finish':
            assert entry['status'] == 'unsupported'
            raise ValueError('skip callback failed')

    with pytest.raises(ValueError, match='skip callback failed'):
        suite.run(prof, ids=['unit.skip'], progress=progress)
    assert calls == ['close']
