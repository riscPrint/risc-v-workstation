"""Device poison/reset and per-request thread builds in one real server."""
import json
import os
from rvw.common.proc import run_group
from test_adapter import EXAMPLE, GCC


def test_device_wide_reset_and_thread_selection(tmp_path):
    programs = {}
    for name in ('device-poison', 'device-reset-check', 'device-echo'):
        elf = tmp_path / name
        result = run_group([GCC, '-march=rv32im_zicsr', '-mabi=ilp32', '-nostdlib',
                            '-T', str(EXAMPLE / 'programs/link.ld'),
                            str(EXAMPLE / 'programs' / (name + '.S')), '-o', str(elf)],
                           capture=True, text=True, timeout=30)
        assert result.returncode == 0, result.stderr
        programs[name] = elf
    sequence = [('poison', 'device-poison', 1), ('check-two', 'device-reset-check', 2),
                ('echo-one', 'device-echo', 1), ('echo-two', 'device-echo', 2),
                ('check-one', 'device-reset-check', 1)]
    jobs = [dict(elf=str(programs[program]), out=str(tmp_path / name), seed=1,
                 sim_threads=threads, max_cycles=20000, mem_latency=0, rvfi_trace=True,
                 soc_map=str(EXAMPLE.parent / 'live-devices.json')) for name, program, threads in sequence]
    result = run_group([str(EXAMPLE / 'run.sh'), 'serve'],
                       input=''.join(json.dumps(j) + '\n' for j in jobs), env=dict(os.environ),
                       capture=True, text=True, timeout=600)
    assert result.returncode == 0, result.stdout + result.stderr
    reports = [json.loads(line)['result'] for line in result.stdout.splitlines()]
    assert [r['status'] for r in reports] == ['fail', 'pass', 'pass', 'pass', 'pass'], reports
    assert reports[0]['fail_code'] == 3
    assert reports[0]['details']['device_output']['uart'] == 'P'
    assert [r['sim_threads'] for r in reports] == [1, 2, 1, 2, 1]
    assert [r['details']['model']['sim_threads'] for r in reports] == [1, 2, 1, 2, 1]
    assert len({r['details']['simulation_session']['id'] for r in reports}) == 1
    assert [r['details']['simulation_session']['model_run'] for r in reports] == [1, 1, 2, 2, 3]
    assert len({r['details']['initial_device_state_sha256'] for r in reports}) == 1
    assert len(reports[0]['details']['initial_device_state_sha256']) == 64
    assert not any(r.get('inconclusive') for r in reports)
    for one, two in [('echo-one', 'echo-two'), ('check-one', 'check-two')]:
        assert (tmp_path / one / 'rvfi.jsonl').read_bytes() == (tmp_path / two / 'rvfi.jsonl').read_bytes()
    assert reports[2]['details']['device_output']['uart'] == 'echo\n'
    assert reports[3]['details']['device_output']['uart'] == 'echo\n'
