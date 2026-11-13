"""Public-port wave capture refuses overwrite and retains high packed bits."""
import pytest
from rvw.sim.native_wave import PortWave

pytestmark = pytest.mark.fast


def test_public_wave_preserves_high_bits_and_refuses_overwrite(tmp_path):
    path = tmp_path / 'port.vcd'
    wave = PortWave(path, {'bus': ('output', 129)})
    wave.sample(0, lambda _: (1 << 128) | 3)
    wave.close()
    from rvw.wave.vcd import read_header, body_changes, to_int
    with path.open() as stream:
        header = read_header(stream)
        changes = list(body_changes(stream))
    assert to_int(changes[-1][2]) == (1 << 128) | 3
    with pytest.raises(FileExistsError):
        PortWave(path, {'bus': ('output', 129)})
