import pytest
from rvw.arch.sched_study import regression


def test_three_size_linear_fit_and_signed_error():
    samples = [dict(count=n, rtl_cycles=7+2*n, mca_cycles=3+n) for n in (16,32,64)]
    r = regression(samples)
    assert r['rtl']['slope'] == 2
    assert r['rtl']['intercept'] == 7
    assert r['error_percent'] == -50
    assert not r['rtl']['nonlinear']


def test_nonlinear_stream_is_explicit():
    samples = [dict(count=n, rtl_cycles=7+n*n, mca_cycles=3+n) for n in (16,32,64)]
    assert regression(samples)['rtl']['nonlinear']
    with pytest.raises(ValueError, match='three'):
        regression(samples[:2])


def test_study_reuses_runner_with_seed_and_fixed_memory(tmp_path, monkeypatch):
    from rvw.arch import sched_study
    import json
    description = {'issue_width': 2, 'resources': {'ALU': 2},
                   'classes': [dict(name='alu', resource='ALU', occupancy=1, latency=1)]}
    monkeypatch.setattr(sched_study.sched, 'description', lambda p: description)
    calls = []
    def measure(path, out, **kw):
        calls.append(kw)
        samples = [dict(class_name='unused', **{'class': 'alu'}, mode=mode, count=n,
                        rtl_cycles=2*n+3+kw['seed'], mca_cycles=n+2)
                   for mode in ('dependent','independent') for n in (kw['count'],2*kw['count'])]
        return dict(samples=samples)
    monkeypatch.setattr(sched_study.sched, 'measure', measure)
    r = sched_study.study('description', tmp_path/'out', count=16, repeats=3)
    assert r['sizes'] == [16,32,64]
    assert r['seeds'] == [1,2,3]
    assert r['mem_latency'] == 0
    assert len(calls) == 6
    assert all(row['signed_error_percent']['mean'] == -50 for row in r['classes'])
    assert r['generated_model_accuracy'] == 'inconclusive'


def test_reject_insufficient_register_chains(tmp_path, monkeypatch):
    from rvw.arch import sched_study
    monkeypatch.setattr(sched_study.sched, 'description', lambda p:
        dict(issue_width=8,resources={'ALU':8},classes=[dict(name='alu',resource='ALU',occupancy=1,latency=3)]))
    with pytest.raises(ValueError, match='cannot hide'):
        sched_study.study('description', tmp_path/'out')
    assert not (tmp_path/'out').exists()
