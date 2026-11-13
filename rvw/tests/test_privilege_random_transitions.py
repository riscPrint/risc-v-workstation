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
