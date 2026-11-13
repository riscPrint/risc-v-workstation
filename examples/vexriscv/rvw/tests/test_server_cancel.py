"""Opt-in native cancellation after a completed request and during the next ELF."""
import json
import os
from pathlib import Path
import signal
import threading
import time

from rvw.common.proc import run_group
from test_adapter import EXAMPLE, compile_elf
from test_server import assert_stopped


def test_cancel_stops_actual_native_server(tmp_path):
    target = compile_elf(tmp_path, 'target', 'la t0,tohost\nli t1,1\nsw t1,0(t0)')
    spin = compile_elf(tmp_path, 'spin', 'j _start')
    first = tmp_path / 'completed'
    pending = tmp_path / 'cancelled'
    jobs = [dict(elf=str(elf), out=str(out), seed=317, max_cycles='9223372036854775807',
                 rvfi_trace=True) for elf, out in ((target, first), (spin, pending))]
    done = threading.Event()
    observation = {}
    errors = []

    def observe_and_cancel(launcher_pid):
        try:
            deadline = time.monotonic() + 100
            while not done.wait(0.05):
                if time.monotonic() >= deadline:
                    raise AssertionError('native server did not finish its first request')
                # Require actual retirement in the next request, not just request setup.
                trace = pending / 'rvfi.jsonl'
                if not trace.exists() or not (first / 'result.json').exists():
                    continue
                # The final line can still be in flight. A preceding full line is stable.
                prefix = trace.read_text().splitlines()[:-1]
                if not any('order' in json.loads(line) for line in prefix):
                    continue
                data = json.loads((first / 'result.json').read_text())
                session = data['details']['simulation_session']
                assert data['status'] == 'pass' and data['execution_mode'] == 'server'
                native_pid = int(session['process_id'])
                os.kill(native_pid, 0)
                observation.update(native_pid=native_pid, first_status=data['status'],
                                   first_cycles=data['cycles'], first_instret=data['instret'],
                                   cancelled_retirement_observed=True)
                os.kill(launcher_pid, signal.SIGTERM)
                return
        except BaseException as error:
            errors.append(error)

    threads = []
    def started(pid):
        thread = threading.Thread(target=observe_and_cancel, args=(pid,), daemon=True)
        threads.append(thread)
        thread.start()

    started_at = time.monotonic()
    try:
        result = run_group([str(EXAMPLE / 'run.sh'), 'serve'],
            input=''.join(json.dumps(job) + '\n' for job in jobs), env=dict(os.environ),
            timeout=120, grace=20, capture=True, on_start=started)
    finally:
        done.set()
        for thread in threads:
            thread.join(timeout=2)
    assert not errors, errors
    assert observation, result.stdout + result.stderr
    assert not result.timed_out, result.stderr
    assert result.returncode == 143, result.stderr
    assert_stopped(observation['native_pid'])
    if (pending / 'result.json').exists():
        assert json.loads((pending / 'result.json').read_text())['status'] != 'pass'
    observation.update(launcher_exit=result.returncode, native_process_stopped=True,
                       cancelled_run_pass=False, wall_s=round(time.monotonic()-started_at, 3))
    (tmp_path / 'teardown.json').write_text(json.dumps(observation, indent=2) + '\n')
