"""Failure-window capture from the original live VexRiscv server."""
import json
import os
from pathlib import Path
import sys
import tempfile
import threading

from rvw.common.proc import run_group
from rvw.sim.server import request, serve
from test_adapter import EXAMPLE, compile_elf


def test_bundle_requests_fst_window_on_original_server(tmp_path):
    elf = compile_elf(tmp_path, 'failure', '''li t0, 1000
loop: addi t0, t0, -1
bnez t0, loop
la t0, tohost
li t1, 7
sw t1, 0(t0)''')
    command = json.loads(os.environ.get('RVW_VEX_SERVER_COMMAND',
                                        json.dumps([str(EXAMPLE / 'run.sh'), 'serve'])))
    with tempfile.TemporaryDirectory(prefix='rvw-fst-', dir='/tmp') as directory:
        endpoint = Path(directory) / 'server.sock'
        ready = threading.Event()
        worker = threading.Thread(target=serve, args=(endpoint, command),
                                  kwargs={'timeout': 180, 'ready': ready}, daemon=True)
        worker.start()
        assert ready.wait(10)
        try:
            job = dict(elf=str(elf), out=str(tmp_path / 'failure-run'), seed=1,
                       max_cycles=50000, mem_latency=0, rvfi_trace=True)
            original = request(endpoint, job, timeout=180)['result']
            assert original['status'] == 'fail'
            done = run_group([sys.executable, '-m', 'rvw.cli', 'bundle', job['out'],
                              '--out', str(tmp_path / 'bundle'), '--sim-server', str(endpoint),
                              '--core-config', str(EXAMPLE / 'debug.toml'), '--no-spinaltrace',
                              '--rerun-window', '100', '--cut-cycles', '100', '--timeout', '180', '--json'],
                             capture=True, text=True, timeout=240)
            assert done.returncode == 0, done.stdout + done.stderr
            summary = json.loads(done.stdout)
            assert summary['rerun']['reproduced'], summary
            assert summary['files']['wave_window'] == 'wave-window.vcd'
            assert (tmp_path / 'bundle/wave-window.vcd').is_file()
            rerun = json.loads((Path(summary['rerun']['dir']) / 'result.json').read_text())
            assert rerun['artifacts']['wave'].endswith('.fst')
            assert rerun['details']['model']['wave_format'] == 'fst'
            assert rerun['details']['simulation_session']['id'] == original['details']['simulation_session']['id']
            assert rerun['details']['wave_window']['from'] == original['cycles'] - 100
            assert rerun['details']['wave_time_of_cycle_1'] >= 0
            assert rerun['status'] == original['status']
            from rvw.wave.vcd import end_time
            wave = Path(summary['rerun']['dir']) / rerun['artifacts']['wave']
            assert end_time(str(wave)) is not None
        finally:
            request(endpoint, {'op': 'shutdown'}, timeout=10)
            worker.join(10)
            assert not worker.is_alive()
