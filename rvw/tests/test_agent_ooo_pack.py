"""Pin and reverse each OoO task against the actual versioned example."""
import json
import subprocess
from pathlib import Path
import pytest
from rvw.agent_bench import native

pytestmark = pytest.mark.fast
ROOT = Path(__file__).resolve().parents[2]


def test_pinned_ooo_mutations_round_trip(tmp_path):
    pack, _, _ = native.load_pack(ROOT / 'examples/agent-bench/ooo-mini.json')
    assert len(pack['tasks']) == 10
    assert pack['config'] == 'default'
    for task in pack['tasks']:
        mutation = task['private']['mutation']
        path = tmp_path / mutation['file']
        path.parent.mkdir(parents=True, exist_ok=True)
        content = subprocess.check_output(['git', '-C', str(ROOT), 'show',
            pack['source']['revision'] + ':' + mutation['file']])
        path.write_bytes(content)
        native.mutate(tmp_path, mutation)
        assert path.read_bytes() != content
        native.mutate(tmp_path, mutation, reverse=True)
        assert path.read_bytes() == content
