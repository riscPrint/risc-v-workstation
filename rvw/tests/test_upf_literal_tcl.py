import pytest
from rvw.formal.literal_tcl import commands
from rvw.formal.upf_subset import parse

pytestmark = pytest.mark.fast


def test_literal_quotes_separators_comments_and_continuations():
    source = '''# header
upf_version "2.1"; # after command separator
create_power_domain PD -elements "core bus"; create_power_domain AUX -elements {aux}
'''
    result = parse(source)
    assert result['domains']['PD']['elements'] == ['core', 'bus']
    assert result['domains']['AUX']['elements'] == ['aux']
    assert commands('cmd "a;b" {c d}; next e')[0][1] == ['cmd', 'a;b', 'c d']
    assert commands('cmd a\\\n  b') == [(1, ['cmd', 'a', 'b'])]
    assert commands('# hidden\\\ncmd a\nnext b') == [(2, ['next', 'b'])]


def test_newlines_in_literal_group_are_not_command_separators():
    assert commands('cmd "a\nb"; next {c\nd}') == [(1, ['cmd', 'a\nb']), (2, ['next', 'c\nd'])]


@pytest.mark.parametrize('source', ['cmd $x', 'cmd [exec touch file]', 'cmd {$x}',
    'cmd "[bad]"', 'cmd {a {b}}', 'cmd "unterminated', 'cmd {unterminated',
    'cmd {a}tail', 'cmd "a"tail', 'cmd a\\tb', 'cmd a"b', 'cmd a{b'])
def test_unrepresented_tcl_is_refused(source):
    with pytest.raises(ValueError): commands(source)


def test_command_after_separator_is_still_validated_as_upf():
    with pytest.raises(ValueError, match='unsupported UPF command'):
        parse('upf_version 2.1; create_power_domain PD -elements {core}; puts ignored')
