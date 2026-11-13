"""A completed replay without samples must not reject an X candidate."""
from pathlib import Path
import runpy
import pytest

pytestmark = pytest.mark.fast
ROOT = Path(__file__).resolve().parents[3]
check = runpy.run_path(str(ROOT / 'examples/vexriscv/formal/x-candidates/replay.py'))['check_log']


@pytest.mark.parametrize('text', ['RVW_DONE', 'RVW_SAMPLE reset=0 ibus=x dbus=0\nRVW_DONE',
                                   'RVW_SAMPLE reset=0 ibus=1 dbus=0\nRVW_X rvw_x_0 7 x\nRVW_DONE'])
def test_missing_or_unknown_samples_cannot_reject(text):
    assert not check(text)


def test_known_samples_and_completion_reject_only_saved_witness():
    assert check('RVW_SAMPLE reset=0 ibus=1 dbus=0\nRVW_DONE')
