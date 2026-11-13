import pytest

from rvw.formal.temporal import Unsupported, lower
from rvw.formal.sva_defaults import expand

pytestmark = pytest.mark.fast


def test_controls_match_explicit_statement():
    original = ('module Top(input clk,rst,a,b); default clocking cb @(posedge clk); endclocking '
                'default disable iff(rst); p: assert property(a |=> b); endmodule')
    explicit = ('module Top(input clk,rst,a,b); p: assert property '
                '(@(posedge clk) disable iff(rst) a |=> b); endmodule')
    actual, reports = lower(original)
    expected, expected_reports = lower(explicit)
    assert reports == expected_reports
    assert actual[actual.index('wire rvw_sva'):].strip() == expected[expected.index('wire rvw_sva'):].strip()


def test_explicit_controls_override_defaults():
    _, reports = lower('module Top(input clk,other,rst,a); default clocking cb @(posedge clk); endclocking '
                       'default disable iff(rst); p: assert property (@(posedge other) disable iff(0) a); endmodule')
    assert reports[0]['clock'] == 'other'
    assert reports[0]['disable_iff'] == '0'


def test_named_aliases_receive_controls_once():
    _, reports = lower('module Top(input clk,rst,a); default clocking @(posedge clk); endclocking '
                       'default disable iff(rst); property first; a; endproperty '
                       'property second; first; endproperty p: assert property(second); endmodule')
    assert len(reports) == 1
    assert reports[0]['clock'] == 'clk'
    assert reports[0]['disable_iff'] == 'rst'


def test_defaults_do_not_leak_to_other_modules():
    with pytest.raises(Unsupported, match='clock'):
        lower('module A(input clk,a); default clocking @(posedge clk); endclocking '
              'assert property(a); endmodule module B(input a); assert property(a); endmodule')


@pytest.mark.parametrize('declaration', ['default disable iff(0); default disable iff(1);',
                                       'default clocking @(posedge a); endclocking '
                                       'default clocking @(posedge b); endclocking'])
def test_duplicate_defaults_are_refused(declaration):
    with pytest.raises(Unsupported, match='duplicate_default_control'):
        expand('module Top; ' + declaration + ' endmodule')


def test_nested_defaults_and_skews_stay_unsupported():
    with pytest.raises(Unsupported, match='nested_default_control'):
        expand('module Top; generate begin default disable iff(rst); end endgenerate endmodule')
    with pytest.raises(Unsupported, match='clock'):
        lower('module Top(input clk,a); default clocking cb @(posedge clk); input #1step a; endclocking '
              'assert property(a); endmodule')


def test_liveness_uses_default_clock_without_changing_strength():
    from rvw.formal.liveness import lower_live
    _, rows, _ = lower_live('module Top(input clk,req,ack); default clocking cb @(posedge clk); endclocking '
                         'p: assert property(req |-> s_eventually ack); endmodule', 'Top')
    assert rows[0]['clock'] == 'clk'
    assert rows[0]['id'] == 'p'
