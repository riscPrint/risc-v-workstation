import pytest

from rvw.formal.unbounded import emit

pytestmark=pytest.mark.fast


@pytest.mark.parametrize('prefix',['a[*1:$]','a[*]','a[->1:2]','a[=1:2]'])
@pytest.mark.parametrize('strength',['strong','weak'])
def test_parenthesized_repetition_prefix_keeps_automaton(prefix,strength):
    plain=emit(f'req |-> {strength}({prefix} ##1 b)','clk','mon')
    grouped=emit(f'req |-> {strength}(({prefix}) ##1 (b))','clk','mon')
    assert grouped==plain
