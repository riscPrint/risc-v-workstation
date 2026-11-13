import pytest
from rvw.cov.proof import point_cone, _sby_text, _job_harness, sanity_plan

pytestmark=pytest.mark.fast


def test_missing_elaboration_cannot_establish_sanity():
    plan=sanity_plan({'top':'h','points':[{'expression':'q'}],'reset':None},None)
    assert plan['expression'] is None
    assert plan['error']


def test_constant_or_undriven_point_has_no_eligible_cone():
    for bits in [['0'],[5]]:
        netlist={'modules':{'h':{'ports':{},'cells':{},'netnames':{'q':{'bits':bits,'hide_name':0}}}},'source_modules':[]}
        signals,problems=point_cone(netlist,'h','q')
        assert not signals and problems


def test_generated_cover_isolation_preserves_other_property_kinds():
    text=_sby_text('cover',4,2,[],'h',isolated_covers=1)
    assert 'chformal -cover -remove' in text
    assert 'chformal -assume' not in text and 'chformal -assert' not in text
    harness=_job_harness('always @(posedge clk) begin // RVW_POINT\nend','cover (q);',1)
    assert 'rvw_generated_cover_0: cover (q)' in harness
