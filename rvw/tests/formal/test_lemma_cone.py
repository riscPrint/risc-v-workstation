from copy import deepcopy
import pytest
from rvw.formal.lemma_cone import identity

pytestmark = pytest.mark.fast


def model(delta=0):
    b = lambda n: n + delta
    return {'ports': {'clk': {'direction': 'input', 'bits': [b(2)]},
                      'data': {'direction': 'input', 'bits': [b(3)]}},
            'netnames': {'q': {'bits': [b(4)], 'hide_name': 0, 'attributes': {'init': '0'}}},
            'cells': {'generated_ff': {'type': '$dff', 'parameters': {'CLK_POLARITY': '1'},
                                      'port_directions': {'CLK': 'input', 'D': 'input', 'Q': 'output'},
                                      'connections': {'CLK': [b(2)], 'D': [b(5)], 'Q': [b(4)]}},
                      'generated_xor': {'type': '$xor', 'parameters': {'Y_WIDTH': '1'},
                                        'port_directions': {'A': 'input', 'B': 'input', 'Y': 'output'},
                                        'connections': {'A': [b(4)], 'B': [b(3)], 'Y': [b(5)]}}}}


def test_stable_under_numeric_ids_and_generated_names():
    a, b = model(), model(100)
    b['cells']['renamed_ff'] = b['cells'].pop('generated_ff')
    b['cells']['renamed_logic'] = b['cells'].pop('generated_xor')
    assert identity(a, [('q', 0)])[0] == identity(b, [('q', 0)])[0]


def test_ignores_unrelated_cells_but_keeps_transition_clock_and_init():
    a = model()
    original = identity(a, [('q', 0)])[0]
    a['cells']['unrelated'] = {'type': '$not', 'parameters': {},
                             'port_directions': {'A': 'input', 'Y': 'output'},
                             'connections': {'A': [3], 'Y': [20]}}
    assert identity(a, [('q', 0)])[0] == original
    for mutation in ('init', 'clock', 'logic', 'input'):
        b = deepcopy(a)
        if mutation == 'init':
            b['netnames']['q']['attributes']['init'] = '1'
        elif mutation == 'clock':
            b['cells']['generated_ff']['parameters']['CLK_POLARITY'] = '0'
        elif mutation == 'logic':
            b['cells']['generated_xor']['type'] = '$and'
        else:
            b['ports']['renamed'] = b['ports'].pop('data')
        assert identity(b, [('q', 0)])[0] != original, mutation


def test_undefined_or_unmapped_state_cannot_match():
    a = model()
    a['netnames']['q']['hide_name'] = 1
    with pytest.raises(ValueError, match='unnamed'):
        identity(a, [('q', 0)])
    with pytest.raises(ValueError, match='missing'):
        identity(model(), [('missing', 0)])
    a = model()
    a['cells']['generated_ff']['connections']['D'] = [88]
    with pytest.raises(ValueError, match='undriven'):
        identity(a, [('q', 0)])
