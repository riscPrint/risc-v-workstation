import pytest

pytestmark = pytest.mark.fast


def test_independent_command_and_mcp_registration():
    from rvw.cli import build_parser
    from rvw.formal.commands import initial_split, lazy_ram, counter_quotient
    parser = build_parser()
    for command, module in [('initial-split', initial_split), ('lazy-ram', lazy_ram), ('counter-quotient', counter_quotient)]:
        args = parser.parse_args(['formal', command, '--manifest', 'plan.json', '--out', 'out'])
        assert args.func is not None
        assert module.mcp_tools()[0].name == 'formal_' + command.replace('-', '_')
