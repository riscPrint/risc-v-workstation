import json
from pathlib import Path
import runpy
import pytest
pytestmark=pytest.mark.fast
MODULE=runpy.run_path(str(Path(__file__).parents[1]/'scaling.py'))


def inputs(tmp_path,monkeypatch,bad_replay=False):
    def summarize(path):
        _,hart,repeat,_=path.name.split('-')
        return dict(run=path.name,status='pass',cycles=5000,instret=2000*int(hart),
                    trace_sha256='bad' if bad_replay and hart=='2' and repeat=='3' else 'same-'+hart,core_rev='pinned',per_hart_retirements={str(i):2000 for i in range(int(hart))})
    monkeypatch.setattr(runpy,'run_path',lambda path:{'summarize':summarize})
    log=tmp_path/'adapter.log';lines=['[run-many] 28 jobs, 1 workers']
    for h in range(2,9):
        for r,ms in enumerate((999999,100,300,200)):
            folder=tmp_path/f'timing-{h}-{r}-run';folder.mkdir()
            (folder/'result.json').write_text(json.dumps(dict(config=f'smp{h}',seed=31,details=dict(timing=dict(random_max_delay=7,ready_percent=55,clock_enable_percent=90,fixed_latency=None)))))
            lines += [f'[timing-{h}-{r}-run#1] run elf config=smp{h}',f'[Done] Simulation done in {ms} ms']
    log.write_text('\n'.join(lines)+'\n')
    return log


def test_warmup_is_excluded_and_all_replay_hashes_are_checked(tmp_path,monkeypatch):
    log=inputs(tmp_path,monkeypatch)
    result=MODULE['timing_summarize'](tmp_path,log)
    assert len(result['runs'])==7
    assert result['seed']==31 and result['timing']['random_max_delay']==7
    assert all(r['simulation_wall_samples']==[.1,.3,.2] and r['median_simulation_wall_s']==.2 for r in result['runs'])
    assert json.loads((tmp_path/'timing-results.json').read_text())==result


def test_changed_capture_cannot_earn_identical_replay(tmp_path,monkeypatch):
    log=inputs(tmp_path,monkeypatch,bad_replay=True)
    with pytest.raises(ValueError,match='replay differs'):
        MODULE['timing_summarize'](tmp_path,log)
    assert not (tmp_path/'timing-results.json').exists()


def test_mixed_stress_controls_cannot_earn_one_timing_series(tmp_path,monkeypatch):
    log=inputs(tmp_path,monkeypatch)
    path=tmp_path/'timing-8-3-run/result.json'
    row=json.loads(path.read_text());row['details']['timing']['ready_percent']=100
    path.write_text(json.dumps(row))
    with pytest.raises(ValueError,match='timing controls differ'):
        MODULE['timing_summarize'](tmp_path,log)
    assert not (tmp_path/'timing-results.json').exists()


def test_interleaved_worker_log_cannot_supply_per_run_wall_times(tmp_path,monkeypatch):
    log=inputs(tmp_path,monkeypatch)
    log.write_text(log.read_text().replace('1 workers','2 workers'))
    with pytest.raises(ValueError,match='one run-many worker'):
        MODULE['timing_summarize'](tmp_path,log)


def test_plic_totals_cannot_hide_completion_context_mismatch():
    MODULE['check_plic'](dict(claims=[3,5],completions=[3,5]))
    with pytest.raises(ValueError,match='context counts differ'):
        MODULE['check_plic'](dict(claims=[3,5],completions=[8,0]))
