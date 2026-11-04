"""Native reset equivalence for the persistent request server."""
import json
import os
import sys
from pathlib import Path

from rvw.common.proc import run_group
from test_adapter import EXAMPLE, compile_elf


def test_server_reset_matches_fresh_process(tmp_path):
    poison = compile_elf(tmp_path, 'poison',
                         'la t0, tohost\nli t1, 7\nsw t1, 0(t0)')
    spin = compile_elf(tmp_path, 'spin', 'j _start')
    target = compile_elf(tmp_path, 'target',
                         'la t0, tohost\nli t1, 1\nsw t1, 0(t0)')
    jobs = [dict(elf=str(elf), out=str(tmp_path / name), seed=317,
                 max_cycles=1000, rvfi_trace=True) for elf, name in
            [(spin, 'timeout'), (poison, 'poison-run'), (target, 'second'), (target, 'third')]]
    result = run_group([str(EXAMPLE / 'run.sh'), 'serve'],
                       input=''.join(json.dumps(j) + '\n' for j in jobs),
                       env=dict(os.environ), timeout=600, capture=True, text=True)
    assert result.returncode == 0, result.stderr
    replies = [json.loads(line)['result'] for line in result.stdout.splitlines()]
    assert [r['status'] for r in replies] == ['timeout', 'fail', 'pass', 'pass']
    assert not any(r.get('inconclusive') for r in replies)
    assert all(r['execution_mode'] == 'server' for r in replies)
    sessions = [r['details']['simulation_session'] for r in replies]
    assert len({s['id'] for s in sessions}) == 1
    assert [s['model_run'] for s in sessions] == [1, 2, 3, 4]
    # The server has compiled Scala. Start a fresh JVM with that exact classpath.
    # Do not queue another sbt build just to run the same classes.
    repo = Path(os.environ['RVW_HOME'])
    classpath = (EXAMPLE / 'target/streams/runtime/fullClasspath/_global/streams/export').read_text().strip()
    source = run_group([sys.executable, str(repo / 'RiscvSim/scripts/source-identity.py'),
                        os.environ['VEXRISCV'], str(repo)], capture=True, text=True, timeout=30)
    assert source.returncode == 0, source.stderr
    source_path = tmp_path / 'source.json'
    source_path.write_text(source.stdout)
    env = dict(os.environ, SPINAL_MAKE_CMD=str(repo / 'RiscvSim/scripts/make-jobs.sh'))
    native = run_group([sys.executable, str(repo / 'RiscvSim/scripts/native-identity.py')],
                       env=env, capture=True, text=True, timeout=30)
    assert native.returncode == 0, native.stderr
    fresh = run_group([str(repo / 'scripts/with-lock.sh'), 'vex', 'nice', '-n', '10',
        sys.executable, str(repo / 'RiscvSim/scripts/native-identity.py'), 'launch',
        native.stdout, str(tmp_path), '-Xmx3g', '-Xss64m',
        '-Driscvsim.tools=' + str(repo), '-Driscvsim.source=' + str(source_path),
        '-Driscvsim.script=' + str(EXAMPLE / 'run.sh'),
        '-cp', classpath, 'rvwvex.Main', 'run', '--elf', str(target),
        '--out', str(tmp_path / 'fresh'), '--seed', '317', '--max-cycles', '1000',
        '--rvfi-trace', '--json'], env=env, capture=True, text=True, timeout=600)
    assert fresh.returncode == 0, fresh.stderr
    reference = json.loads(fresh.stdout)
    assert reference['execution_mode'] == 'process'
    for result in replies[2:]:
        for key in ('status', 'cycles', 'instret', 'fail_code', 'elf_sha256', 'rtl_sha256'):
            assert result[key] == reference[key]
    expected = (tmp_path / 'fresh/rvfi.jsonl').read_bytes()
    assert (tmp_path / 'second/rvfi.jsonl').read_bytes() == expected
    assert (tmp_path / 'third/rvfi.jsonl').read_bytes() == expected

    # The regression-facing opt-in must use the same server reset path.
    manifest = tmp_path / 'manifest.jsonl'
    batch_jobs = [dict(jobs[-1], out=str(tmp_path / name)) for name in ('batch-one', 'batch-two')]
    manifest.write_text(''.join(json.dumps(j) + '\n' for j in batch_jobs))
    batch = run_group([str(EXAMPLE / 'run.sh'), 'run-many', '--persistent',
                       '--jobs', '1', '--manifest', str(manifest), '--json'],
                      env=dict(os.environ), timeout=600, capture=True, text=True)
    assert batch.returncode == 0, batch.stderr
    assert json.loads(batch.stdout)['counts']['pass'] == 2
    for name in ('batch-one', 'batch-two'):
        result = json.loads((tmp_path / name / 'result.json').read_text())
        assert result['execution_mode'] == 'server'
        assert not result.get('inconclusive')
        for key in ('status', 'cycles', 'instret', 'fail_code', 'elf_sha256', 'rtl_sha256'):
            assert result[key] == reference[key]
        assert (tmp_path / name / 'rvfi.jsonl').read_bytes() == expected

    # A portable checkpoint records a suffix and verifies a fresh replay.
    import importlib.util
    spec = importlib.util.spec_from_file_location('checkpoint',
        Path(os.environ['RVW_HOME']) / 'RiscvSim/scripts/replay-checkpoint.py')
    checkpoint = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(checkpoint)
    saved = tmp_path / 'checkpoint.json'
    checkpoint.create(tmp_path / 'second/result.json', 2, saved)
    assert checkpoint.verify(saved, tmp_path / 'fresh/result.json')['status'] == 'equivalent'
