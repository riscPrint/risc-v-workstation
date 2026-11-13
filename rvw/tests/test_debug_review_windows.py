"""Hart-array windows hold separate parts of one persistent selection mask."""
import pytest
from rvw.debug import dm, profile

pytestmark = pytest.mark.fast


def module():
    model = dm.DebugModule(profile.normalize({'harts': 64, 'hart_array': True,
                                              'ticks_per_access': 0}))
    model.write(dm.DMCONTROL, 1)
    return model


def test_windows_store_independent_masks_and_select_across_banks():
    model = module()
    model.write(dm.HAWINDOW, 2)
    model.write(dm.HAWINDOWSEL, 1)
    assert model.read(dm.HAWINDOW) == 0
    model.write(dm.HAWINDOW, 4)
    model.write(dm.DMCONTROL, (1 << 26) | 1)
    assert model.selected() == [0, 1, 34]
    model.write(dm.HAWINDOWSEL, 0)
    assert model.read(dm.HAWINDOW) == 2
    assert model.selected() == [0, 1, 34]


def test_dmactive_reset_clears_all_windows():
    model = module()
    model.write(dm.HAWINDOW, 2)
    model.write(dm.DMCONTROL, 0)
    model.write(dm.DMCONTROL, 1)
    assert model.read(dm.HAWINDOW) == 0
