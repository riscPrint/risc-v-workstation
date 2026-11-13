"""Opt-in native continuation test. Run with the VexRiscv tool environment."""
import json
import os
from pathlib import Path

from rvw.common.proc import run_group

EXAMPLE = Path(__file__).resolve().parents[1]


def test_live_checkpoint_in_new_process(tmp_path):
    source = EXAMPLE / 'programs' / 'smoke.S'
    elf = tmp_path / 'smoke'
    gcc = os.environ.get('RISCV_PREFIX', 'riscv64-unknown-elf-') + 'gcc'
    built = run_group([gcc, '-march=rv32im_zicsr_zifencei', '-mabi=ilp32',
        '-nostdlib', '-nostartfiles', '-T', str(EXAMPLE / 'programs/link.ld'),
        str(source), '-o', str(elf)], timeout=30, capture=True, text=True)
    assert built.returncode == 0, built.stderr
    state = tmp_path / 'state.json'
    for mode in ('save', 'restore'):
        result = run_group([str(EXAMPLE / 'checkpoint-probe.sh'), str(elf),
            str(tmp_path / mode), str(state), mode, '8'], timeout=600,
            capture=True, text=True)
        assert result.returncode == 0, result.stdout + result.stderr
    original = (tmp_path / 'save/rvfi.jsonl').read_bytes()
    resumed = (tmp_path / 'restore/rvfi.jsonl').read_bytes()
    assert original == resumed
    payload = json.loads(state.read_text())['state']
    assert payload['retired'] == '8'
    assert len(payload['rtl']['registers']) > 100
    assert payload['rtl']['memories']
    position = int(payload['writer']['position'])
    assert len(original) > position
    assert json.loads(original.splitlines()[-1])['status'] == 'pass'
