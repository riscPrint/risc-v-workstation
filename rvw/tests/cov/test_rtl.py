import copy
import json

import pytest

from rvw.cov.rtl import identity, sample, validate
from rvw.cli import main


@pytest.fixture
def plan():
    return {'schema': 'rvw.rtl-plan/1', 'design': 'fixture:tiny:rtl-sha256',
            'clock': {'signal': 'TOP.clk', 'edge': 'rising', 'sampling': 'pre-edge'},
            'reset': {'signal': 'TOP.reset', 'active': 1, 'rule': 'disable-clear'},
            'signals': {n: {'width': w, 'type': t, 'scala': None} for n, w, t in [
                ('TOP.clk', 1, 'Bool'), ('TOP.reset', 1, 'Bool'), ('TOP.state', 2, 'UInt(2 bits)')]},
            'bins': [{'id': f'state.{i}', 'kind': 'state', 'domain': 'structural',
                      'when': {'TOP.state': [i]}} for i in range(4)] + [
                      {'id': 'idle-run', 'kind': 'transition', 'domain': 'speculative',
                       'from': {'TOP.state': [0]}, 'when': {'TOP.state': [1]}}]}


def write(tmp_path, plan, states, name='trace', complete=True):
    config = tmp_path / 'plan.json'
    config.write_text(json.dumps(plan))
    trace = tmp_path / name
    rows = [{'schema': 'rvw.rtl-samples/1', 'plan_id': identity(plan), 'design': plan['design']}]
    rows += [{'cycle': n, 'values': {'TOP.clk': 0, 'TOP.reset': reset, 'TOP.state': state}}
             for n, (reset, state) in enumerate(states)]
    if complete is not None:
        rows += [{'event': 'end', 'complete': complete}]
    trace.write_text(''.join(json.dumps(r) + '\n' for r in rows))
    return config, trace


def test_state_domains_transitions_and_reset(tmp_path, plan):
    config, trace = write(tmp_path, plan, [(1, 3), (0, 0), (0, 1), (1, 0), (0, 1)])
    result = sample(config, [trace])
    assert result['status'] == 'ok'
    assert [b['count'] for b in result['bins']] == [1, 2, 0, 0, 1]
    assert result['bins'][3]['observation'] == 'unobserved'
    assert result['bins'][3]['reachability'] == 'undetermined'
    assert result['proven_unreachable_bins'] == 0
    assert result['denominator'] == 5


@pytest.mark.parametrize('complete', [None, False])
def test_incomplete_is_inconclusive_and_cli_exits_three(tmp_path, plan, complete, capsys):
    config, trace = write(tmp_path, plan, [(0, 1)], complete=complete)
    assert sample(config, [trace])['status'] == 'inconclusive'
    assert main(['cov', 'rtl', str(trace), '--config', str(config), '--json']) == 3
    assert json.loads(capsys.readouterr().out)['observed_bins'] == 1


def test_independent_runs_never_form_a_transition(tmp_path, plan):
    config, a = write(tmp_path, plan, [(0, 0)], 'a')
    _, b = write(tmp_path, plan, [(0, 1)], 'b')
    assert sample(config, [a, b])['bins'][-1]['count'] == 0
    with pytest.raises(ValueError, match='duplicate'):
        sample(config, [a, a])


@pytest.mark.parametrize('mutation', ['identity', 'gap', 'missing', 'unknown', 'postedge', 'end'])
def test_invalid_samples_refuse(tmp_path, plan, mutation):
    config, trace = write(tmp_path, plan, [(0, 0), (0, 1)])
    rows = [json.loads(line) for line in trace.read_text().splitlines()]
    if mutation == 'identity':
        rows[0]['design'] = 'other'
    elif mutation == 'gap':
        rows[2]['cycle'] = 3
    elif mutation == 'missing':
        del rows[1]['values']['TOP.state']
    elif mutation == 'unknown':
        rows[1]['values']['TOP.state'] = 'x'
    elif mutation == 'postedge':
        rows[1]['values']['TOP.clk'] = 1
    else:
        rows.append(rows[1])
    trace.write_text(''.join(json.dumps(row) + '\n' for row in rows))
    with pytest.raises(ValueError):
        sample(config, [trace])


@pytest.mark.parametrize('mutation', ['edge', 'reset', 'bin', 'duplicate', 'range', 'wildcard'])
def test_invalid_plans_refuse(plan, mutation):
    if mutation == 'edge':
        plan['clock']['edge'] = 'falling'
    elif mutation == 'reset':
        plan['reset']['rule'] = 'retain'
    elif mutation == 'bin':
        plan['bins'][0]['kind'] = 'custom-eval'
    elif mutation == 'duplicate':
        plan['bins'].append(copy.deepcopy(plan['bins'][0]))
    elif mutation == 'range':
        plan['bins'][0]['when']['TOP.state'] = [4]
    else:
        plan['signals']['TOP.*.state'] = plan['signals'].pop('TOP.state')
    with pytest.raises(ValueError):
        validate(plan)
