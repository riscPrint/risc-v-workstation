import hashlib
import json
from pathlib import Path
import runpy
import pytest


def test_fetch_pinned_bytes(tmp_path):
    fetch = runpy.run_path(str(Path(__file__).resolve().parents[3] / 'scripts/fetch-formal-bench.py'))['fetch']
    source = tmp_path / 'source.aig'
    source.write_bytes(b'fixture')
    plan = {'cases': [{'sources': [{'path': 'case.aig', 'url': source.as_uri(),
                                  'sha256': hashlib.sha256(b'fixture').hexdigest()}]}]}
    manifest = tmp_path / 'plan.json'
    manifest.write_text(json.dumps(plan))
    out = tmp_path / 'download'
    assert fetch(manifest, out) == out / 'manifest.json'
    assert (out / 'case.aig').read_bytes() == b'fixture'
    (out / 'case.aig').write_bytes(b'corrupt')
    with pytest.raises(ValueError, match='hash mismatch'):
        fetch(manifest, out)


@pytest.fixture
def tmp_path(external_tmp_path):
    return external_tmp_path
