"""Keep raw generated output out of the tracked source tree."""
import json
from pathlib import Path
import subprocess
import pytest

pytestmark = pytest.mark.fast
ROOT = Path(__file__).resolve().parents[2]
# Runtime source inputs, dependency locks, and two pre-existing C2 examples.
SOURCE_DATA = {
    'rvw/src/rvw/csr/csr_catalog.json',
    'rvw/src/rvw/csr/csr_aia_catalog.json',
    'rvw/src/rvw/doctor/tools.json',
    'examples/profiles/source-index.json',
    'SpinalTrace/gui/package-lock.json',
    'SpinalWaves/vendor-lock.json',
    'vscode/package-lock.json',
    'RiscvSim/boom/examples/pass-rv64ui-p-add/rvfi.jsonl',
    'RiscvSim/boom/examples/traps-rv64mi-p-ma_addr/rvfi.jsonl',
    'examples/smp/rvw/upstream-results.json',
}


def test_tracked_generated_output_size():
    names = subprocess.check_output(['git', 'ls-files', '-z'], cwd=ROOT).decode().split('\0')
    oversized = []
    for name in names:
        path = ROOT / name
        if not name or name in SOURCE_DATA or not path.is_file():
            continue
        if path.suffix in {'.json', '.jsonl', '.kanata'}:
            limit = 50_000
            if path.suffix == '.json' and path.stat().st_size > 20_000:
                data = json.loads(path.read_text())
                if isinstance(data, dict) and data.get('summary_only'):
                    limit = 20_000
        elif name == 'docs/status/2026-11-13/PR_EVIDENCE.md':
            limit = 200_000  # PR titles, evidence labels and links only.
            assert '\n## PR ' not in path.read_text(), 'Link PR bodies instead of copying them.'
        elif name.startswith('docs/examples/') and path.suffix == '.html':
            limit = 50_000
        else:
            continue
        if path.stat().st_size > limit:
            oversized.append(f'{name}: {path.stat().st_size} bytes (limit {limit})')
    assert not oversized, 'Keep counts and regeneration commands; store raw output outside Git:\n' + '\n'.join(oversized)
