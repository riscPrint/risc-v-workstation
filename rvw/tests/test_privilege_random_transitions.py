import pytest
from rvw.privilege import campaign, random_transitions

pytestmark = pytest.mark.fast


def test_seeded_plan_and_trap_return_coverage():
    config = campaign.load('examples/privilege/random-transitions.json')
    rows = campaign.scenarios(config)
    assert rows == campaign.scenarios(config)
    assert len(rows) == 4
    bins = {b for row in rows for b in row['bins']}
    assert len(bins) == 13
    assert rows[0]['transition_plan'] != rows[1]['transition_plan']
    for row in rows:
        assert len(row['transition_plan']) == 32
        assert 'step_32:\n j pass' in row['assembly']
        for i, step in enumerate(row['transition_plan']):
            assert f'probe_{i}:' in row['assembly']
            assert f'resume_{i}:' in row['assembly']
            if step['delegated']:
                assert step['mode'] != 'M' and step['operation'] != 'ecall'


@pytest.mark.parametrize('field,value', [('seeds', []), ('seeds', [1, 1]), ('seeds', [True]), ('steps', 0), ('steps', 257)])
def test_bad_random_bounds(field, value):
    config = campaign.load('examples/privilege/random-transitions.json')
    config['random_transitions'][field] = value
    with pytest.raises(ValueError):
        campaign.scenarios(config)


def test_rv32_transport_and_saved_interrupt_enable_frames():
    config = campaign.load('examples/privilege/random-transitions-rv32.json')
    rows = campaign.scenarios(config)
    all_steps = [s for row in rows for s in row['transition_plan']]
    assert {s['previous_ie'] for s in all_steps} == {0, 1}
    assert {s['previous_ie'] for s in all_steps if s['delegated']} == {0, 1}
    for row in rows:
        code = row['assembly']
        assert ' sd ' not in code
        assert ' sw t1, 0(t0)\n sw zero, 4(t0)' in code
        for i, step in enumerate(row['transition_plan']):
            level = 's' if step['delegated'] else 'm'
            frame = random_transitions.check(i, step, level)
            assert ('li t1, 290' if level == 's' else 'li t1, 6280') in frame
            # Check current IE clear and previous IE saved, including saved mode.
            previous_mode = (0x100 if step['mode'] == 'S' else 0) if level == 's' else {'M': 3, 'S': 1, 'U': 0}[step['mode']] << 11
            expected = previous_mode | ((0x20 if level == 's' else 0x80) if step['previous_ie'] else 0)
            assert f'li t1, {expected}\n bne t0, t1, fail' in frame
    # Width changes transport, but not the seeded operation sequence.
    rv64 = campaign.scenarios(campaign.load('examples/privilege/random-transitions.json'))
    assert [r['transition_plan'] for r in rows] == [r['transition_plan'] for r in rv64]


def test_random_profiles_are_selected_by_width(tmp_path):
    import json
    from rvw.regress.commands.applicability import plan
    for bits in (32, 64):
        features = tmp_path / 'features.json'
        features.write_text(json.dumps(dict(schema='rvw.regress-features/1',
            capabilities=[f'xlen:{bits}', 'mode:S', 'mode:U', 'pmp'])))
        names = {r['name'] for r in plan(features)['suites'] if r['applicable']}
        assert f'random-privilege-rv{bits}' in names
        assert f'random-privilege-rv{96-bits}' not in names
