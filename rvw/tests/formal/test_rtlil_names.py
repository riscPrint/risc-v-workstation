"""Old and Yosys 0.70 interned hierarchy names."""
import pytest
from rvw.formal.common import count_asserts

pytestmark = pytest.mark.fast


@pytest.mark.parametrize('interned', [False, True])
def test_hierarchy_counts_each_instance(tmp_path, interned):
    table = 'twines\n  leaf 100 "to"\n  suffix 101 100 "p"\n  leaf 102 "sub"\nend\n'
    top, sub = ('$pub@101', '$pub@102') if interned else ('\\top', '\\sub')
    path = tmp_path / 'design.il'
    path.write_text((table if interned else '') +
        f'module {sub}\n  cell $assert $priv@200\n  end\nend\n'
        f'module {top}\n  cell {sub} \\a\n  end\n  cell {sub} \\b\n  end\nend\n')
    assert count_asserts(path, 'top') == 2
    assert count_asserts(path, 'absent') is None


def test_unresolved_module_does_not_earn_proof(tmp_path):
    path = tmp_path / 'bad.il'
    path.write_text('module $pub@999\n  cell $assert $a\n  end\nend\n')
    assert count_asserts(path, 'top') is None
