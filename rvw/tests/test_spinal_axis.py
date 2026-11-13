"""The Spinal libraries take SpinalHDL from the shared version axis, never from a pinned jar line."""
from pathlib import Path
import re

import pytest

pytestmark = pytest.mark.fast

ROOT = Path(__file__).resolve().parents[2]
LIBRARIES = {
    'RiscvSim': ('core', 'sim'),
    'SpinalProbes': ('core', 'sim'),
    'SpinalChecks': ('core', 'lib'),
    'SpinalTrace/spinaltrace': ('core', 'lib'),
    'SpinalWaves/spinalwaves': ('core', 'lib'),
    'SpinalDB/spinaldb': ('core', 'lib'),
}


@pytest.mark.parametrize('library', sorted(LIBRARIES))
def test_library_uses_the_spinal_axis(library):
    build = (ROOT / library / 'build.sbt').read_text()
    modules = ', '.join(f'"{m}"' for m in LIBRARIES[library])
    assert f'SpinalAxis.projects({modules}): _*' in build
    assert f'SpinalAxis.settings({modules})' in build
    assert 'com.github.spinalhdl' not in build
    meta = (ROOT / library / 'project/spinal-axis.sbt').read_text()
    depth = library.count('/') + 2
    assert meta.count('getParentFile') == depth
    assert '"scripts" / "sbt"' in meta


def test_axis_defaults_to_the_release_and_cross_builds_both_scala_versions():
    axis = (ROOT / 'scripts/sbt/SpinalAxis.scala').read_text()
    assert re.search(r'val release = "1\.15\.0"', axis)
    assert 'sys.env.get("RVW_SPINAL_SOURCE")' in axis
    assert 'crossScalaVersions := Seq("2.13.14", "2.12.18")' in axis
    assert 's"spinal-$axis"' in axis  # each source axis compiles into its own target directory
