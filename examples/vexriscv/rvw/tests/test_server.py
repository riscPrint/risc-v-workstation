"""Native reset equivalence for the persistent request server."""
import json
import os
from pathlib import Path

from rvw.common.proc import run_group
from test_adapter import EXAMPLE, compile_elf, invoke


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
    sessions = [r['details']['simulation_session'] for r in replies]
    assert len({s['id'] for s in sessions}) == 1
    assert [s['model_run'] for s in sessions] == [1, 2, 3, 4]
    fresh = invoke(['run', '--elf', target, '--out', tmp_path / 'fresh',
                    '--seed', 317, '--max-cycles', 1000, '--rvfi-trace', '--json'])
    assert fresh.returncode == 0, fresh.stderr
    reference = json.loads(fresh.stdout)
    for result in replies[2:]:
        for key in ('status', 'cycles', 'instret', 'fail_code', 'elf_sha256', 'rtl_sha256'):
            assert result[key] == reference[key]
    expected = (tmp_path / 'fresh/rvfi.jsonl').read_bytes()
    assert (tmp_path / 'second/rvfi.jsonl').read_bytes() == expected
    assert (tmp_path / 'third/rvfi.jsonl').read_bytes() == expected

