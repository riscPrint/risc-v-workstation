import pytest
from rvw.formal.rvfi_binding import wrapper
from rvw.formal.riscv import FIELDS

pytestmark = pytest.mark.fast


def plan():
    return dict(schema='rvw.rvfi-binding/1', top='Core', clock='clk', reset='rst',
                ports={f: 'rvfi_'+f for f in FIELDS},
                inputs=dict(ready=1, response=1, error=1), outputs=dict(valid=1, write=1),
                bus_environment=[dict(protocol='stream-response', valid='valid', ready='ready',
                                      response='response', write='write', service_bound=3)],
                environment_constants=dict(error=0))


def test_environment_only_assumes_inputs():
    text = wrapper(plan())
    assert 'assume(bound_inputs_0)' in text
    assert 'assume(!bound_inputs_1 || env_0_pending > 0)' in text
    assert 'assert(env_0_pending >= 0' in text
    assert "assume(bound_inputs_2 == 1'd0)" in text
    assert 'assume(rvfi_' not in text
    assert 'bound_outputs_0 && bound_inputs_0 && !bound_outputs_1' in text


@pytest.mark.parametrize('change', [
    lambda p: p['bus_environment'][0].update(protocol='axi'),
    lambda p: p['bus_environment'][0].update(service_bound=0),
    lambda p: p['bus_environment'][0].update(ready='valid'),
    lambda p: p['environment_constants'].update(valid=0),
    lambda p: p['environment_constants'].update(error=2),
])
def test_reject_bad_environment(change):
    p = plan()
    change(p)
    with pytest.raises(ValueError):
        wrapper(p)
