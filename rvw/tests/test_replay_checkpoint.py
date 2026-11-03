import importlib.util
import json
from pathlib import Path

import pytest

spec = importlib.util.spec_from_file_location('checkpoint', Path(__file__).resolve().parents[2] /
                                             'RiscvSim/scripts/replay-checkpoint.py')
checkpoint = importlib.util.module_from_spec(spec)
spec.loader.exec_module(checkpoint)


def evidence(directory):
    directory.mkdir()
    result = dict(schema='rvw.run/1', core='fixture', config='test', status='pass',
                  elf_sha256='a' * 64, rtl_sha256='b' * 64, cycles=100, instret=3,
                  seed=1, max_cycles=200, mem_latency=None, irq_schedule=None,
                  tools={'native_build': {'sha256': 'c' * 64}},
                  artifacts={'rvfi_trace': 'rvfi.jsonl'})
    (directory / 'result.json').write_text(json.dumps(result))
    events = [dict(schema='rvw.rvfi/1'), dict(cycle=20, rd_wdata='0x1'),
              dict(cycle=80, rd_wdata='0x2'), dict(event='end', cycle=100, status='pass')]
    (directory / 'rvfi.jsonl').write_text('\n'.join(map(json.dumps, events)))
    return directory / 'result.json'


def test_equivalent_suffix_and_bound_identity(tmp_path):
    original = evidence(tmp_path / 'original')
    replay = evidence(tmp_path / 'replay')
    saved = tmp_path / 'checkpoint.json'
    checkpoint.create(original, 50, saved)
    assert checkpoint.verify(saved, replay)['status'] == 'equivalent'
    result = json.loads(replay.read_text())
    result['seed'] = 2
    replay.write_text(json.dumps(result))
    with pytest.raises(ValueError, match='identity mismatch'):
        checkpoint.verify(saved, replay)


def test_suffix_corruption_and_original_changes_are_rejected(tmp_path):
    original = evidence(tmp_path / 'original')
    replay = evidence(tmp_path / 'replay')
    saved = tmp_path / 'checkpoint.json'
    checkpoint.create(original, 50, saved)
    trace = replay.parent / 'rvfi.jsonl'
    trace.write_text(trace.read_text().replace('0x2', '0x3'))
    with pytest.raises(ValueError, match='suffix mismatch'):
        checkpoint.verify(saved, replay)
    original.write_text(original.read_text() + '\n')
    with pytest.raises(ValueError, match='original evidence changed'):
        checkpoint.verify(saved, replay)


def test_descriptor_tampering_inconclusive_and_invalid_bounds(tmp_path):
    result = evidence(tmp_path / 'original')
    saved = tmp_path / 'checkpoint.json'
    checkpoint.create(result, 50, saved)
    value = json.loads(saved.read_text())
    value['cycle'] = 1
    saved.write_text(json.dumps(value))
    with pytest.raises(ValueError, match='checkpoint identity mismatch'):
        checkpoint.verify(saved, result)
    with pytest.raises(ValueError, match='inside the run'):
        checkpoint.create(result, 100, saved)
    value = json.loads(result.read_text())
    value['inconclusive'] = 'missing input'
    result.write_text(json.dumps(value))
    with pytest.raises(ValueError, match='conclusive'):
        checkpoint.create(result, 50, saved)
