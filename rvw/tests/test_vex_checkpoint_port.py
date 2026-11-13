"""Process-port state checks. Native execution has a separate opt-in test."""
import importlib.util
import json
from pathlib import Path
import sys

import pytest

MODULE = Path(__file__).resolve().parents[2] / 'examples/vexriscv/rvw/checkpoint_port.py'


def port(tmp_path):
    spec = importlib.util.spec_from_file_location('vex_checkpoint_port', MODULE)
    module = importlib.util.module_from_spec(spec); spec.loader.exec_module(module)
    elf = tmp_path / 'elf'; elf.write_bytes(b'fixture')
    result = module.create(dict(elf=str(elf), launcher=sys.executable))
    result.raw = json.dumps(dict(state=dict(schema='rvw.vex-bridge-probe/1',
        retired='8', cycle='30', handler=False, identity=dict(rtl='fixture')))).encode()
    result.count = 8
    return result


def test_port_retains_payload_and_counter_inventory(tmp_path):
    instance = port(tmp_path)
    try:
        raw, state = instance.save()
        instance.validate_restore(raw, state)
        instance.restore(raw, state)
        assert instance.position('instructions') == 8 and instance.quiescent()
        assert instance.save() == (raw, state)
        instance.replay_to_instruction(8, max_seconds=1)
        with pytest.raises(ValueError, match='precedes'):
            instance.replay_to_instruction(7, max_seconds=1)
        with pytest.raises(ValueError, match='boundaries'):
            instance.advance('cycles', 10)
    finally:
        instance.close()


def test_port_refuses_inconsistent_counters_before_restore(tmp_path):
    instance = port(tmp_path)
    try:
        raw, state = instance.save()
        state['counters']['instructions'] = 9
        with pytest.raises(ValueError, match='counters'):
            instance.restore(raw, state)
        assert instance.position('instructions') == 8
    finally:
        instance.close()


def test_fresh_port_is_stopped_before_restore(tmp_path):
    instance = port(tmp_path)
    try:
        raw, state = instance.save()
        instance.raw = None
        instance.count = 0
        assert instance.quiescent()
        instance.restore(raw, state)
        assert instance.position('instructions') == 8
    finally:
        instance.close()
