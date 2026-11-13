"""Pin and reverse each OoO task against the actual versioned example."""
import hashlib
from pathlib import Path
import pytest
from rvw.agent_bench import native

pytestmark = pytest.mark.fast
ROOT = Path(__file__).resolve().parents[2]
SOURCE_PIN = '4a8757808d344f6db4660ce2e08ae88465f6e27a'
SOURCE_SHA256 = '0a67c42f36297a487e8ae0d9e184b3da6203a27a825e55c3debe8a57bd668f41'


def test_pinned_ooo_mutations_round_trip(tmp_path):
    pack, _, _ = native.load_pack(ROOT / 'examples/agent-bench/ooo-mini.json')
    assert len(pack['tasks']) == 10
    assert pack['config'] == 'default'
    assert pack['source']['revision'] == SOURCE_PIN
    content = (Path(__file__).parent / 'fixtures/agent-ooo/Core.scala').read_bytes()
    assert hashlib.sha256(content).hexdigest() == SOURCE_SHA256
    for task in pack['tasks']:
        mutation = task['private']['mutation']
        path = tmp_path / mutation['file']
        path.parent.mkdir(parents=True, exist_ok=True)
        assert mutation['file'] == 'examples/ooo-mini/src/main/scala/ooomini/Core.scala'
        path.write_bytes(content)
        native.mutate(tmp_path, mutation)
        assert path.read_bytes() != content
        native.mutate(tmp_path, mutation, reverse=True)
        assert path.read_bytes() == content
