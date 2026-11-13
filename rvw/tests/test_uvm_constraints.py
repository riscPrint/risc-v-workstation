import pytest
from rvw.uvm.constraints import ConstraintSolver, FunctionalCoverage
from rvw.cov.exchange import export_ucis, import_ucis


def test_solve_reproducible_constraints():
    pytest.importorskip('z3')
    def solver():
        return ConstraintSolver({'x':(0,100),'y':(0,100)},
            lambda v:[v['x']+v['y']==100, v['x']%4==0],seed=7)
    a,b = solver(),solver()
    samples = [a.sample() for _ in range(30)]
    assert samples == [b.sample() for _ in range(30)]
    assert len({s['x'] for s in samples}) > 1
    assert all(s['x']+s['y']==100 and s['x']%4==0 for s in samples)


def test_unsatisfiable_never_returns_a_transaction():
    pytest.importorskip('z3')
    s = ConstraintSolver({'x':(0,3)},lambda v:[v['x']>5])
    with pytest.raises(ValueError,match='unsat'): s.sample()


def test_observed_coverage_roundtrip_keeps_zero_bins():
    c = FunctionalCoverage({'write':[True,False],'address':[0,4]})
    c.sample(dict(write=True,address=4))
    value = c.export(context={'design':'fixture'})
    restored = import_ucis(export_ucis(value))
    assert restored['rows'] == value['rows']
    assert sorted(r['count'] for r in restored['rows']) == [0,0,0,1]
    with pytest.raises(ValueError,match='outside'): c.sample(dict(write=True,address=8))
