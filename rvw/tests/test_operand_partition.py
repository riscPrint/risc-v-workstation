import pytest
from rvw.formal.operand_partition import partition, constrain

pytestmark = pytest.mark.fast


def test_prefixes_cover_domain_once():
    cases = [partition(8, 3, i) for i in range(8)]
    values = [v for c in cases for v in range(c['lower'], c['upper']+1)]
    assert values == list(range(256))
    assert all(c['parts'] == 8 and not c['complete_domain'] for c in cases)


def test_constant_case_preserves_other_operand_domain():
    assert constrain(partition(16, 16, 65535)) == 'b = (b & 0ULL) | 65535ULL;\n'
    assert constrain(partition(16, 8, 3)) == 'b = (b & 255ULL) | 768ULL;\n'
    assert partition(16, None, None) is None
    assert constrain(None) == ''


@pytest.mark.parametrize('bits,index', [(None, 1), (2, None), (0,0), (17,0), (1,2), (1,-1), (True,0)])
def test_reject_incomplete_or_empty_partition(bits,index):
    with pytest.raises(ValueError): partition(16,bits,index)


def test_cli_and_mcp_expose_same_partition():
    import argparse
    from rvw.formal.datapath import register
    parser = argparse.ArgumentParser()
    register(parser.add_subparsers())
    args = parser.parse_args(['datapath','--width','16','--rtl','x','--model','y',
                               '--out','o','--operand-prefix-bits','8','--operand-prefix','7'])
    assert args.operand_prefix_bits == 8 and args.operand_prefix == 7
    from rvw.formal.mcp_tools import mcp_tools
    tool = next(t for t in mcp_tools() if t.name == 'formal_datapath')
    assert 'operand_prefix' in tool.input_schema['properties']
