"""Keep the source-only disposition report reproducible and conservative."""
import json
from pathlib import Path
import runpy
import pytest

pytestmark = pytest.mark.fast
ROOT = Path(__file__).resolve().parents[2]


def test_source_report_is_current_and_does_not_claim_native_results():
    root = ROOT / 'SpinalChecks/boom'
    regenerate = runpy.run_path(str(root / 'stream-dispositions.py'))['dispositions']
    report = json.loads((root / 'stream-dispositions.json').read_text())
    assert report == regenerate()
    assert report['native_validation'] == 'NOT RUN'
    assert report['generic_cancellation_explained'] == 0
    assert len({r['id'] for r in report['checks']}) == report['source_dispositions']
    assert report['source_dispositions'] + report['unmapped_historical_checks'] == 24
