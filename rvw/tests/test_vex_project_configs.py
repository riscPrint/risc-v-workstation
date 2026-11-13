"""Keep the project declaration aligned with the adapter info contract."""
import re
from pathlib import Path
import pytest

pytestmark = pytest.mark.fast
EXAMPLE = Path(__file__).resolve().parents[2] / 'examples/vexriscv'


def test_declared_configs_match_adapter():
    import tomllib
    declared = tomllib.loads((EXAMPLE / 'rvw.toml').read_text())['core']['configs']
    sources = EXAMPLE / 'rvw/src/main/scala/rvwvex'
    emitted = []
    for filename in ('VexAdapter.scala', 'DebugTop.scala', 'CachedConfig.scala'):
        match = re.search(r'val configs = Seq\(([^)]*)\)', (sources / filename).read_text())
        assert match, filename
        emitted.extend(re.findall(r'"([^"]+)"', match[1]))
    assert declared == emitted
