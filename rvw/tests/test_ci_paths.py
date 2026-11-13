import runpy
from pathlib import Path
import pytest
pytestmark = pytest.mark.fast
select = runpy.run_path(str(Path(__file__).resolve().parents[2] / 'scripts/ci-paths.py'))['select']

@pytest.mark.parametrize('paths,expected', [
    (['docs/a.md'], set()),
    (['vscode/features/wave/a.ts'], {'javascript'}),
    (['rvw/src/rvw/formal/a.py'], {'python'}),
    (['SpinalTrace/src/lib.rs'], {'rust'}),
    (['SpinalProbes/build.sbt'], {'scala'}),
    (['scripts/ci-local.sh'], {'python', 'javascript', 'rust', 'scala'}),
])
def test_path_selection(paths, expected):
    assert {key for key, value in select(paths).items() if value} == expected


def test_scala_change_selects_only_its_project():
    projects = runpy.run_path(str(Path(__file__).resolve().parents[2] / 'scripts/ci-paths.py'))['scala_projects']
    assert projects(['SpinalProbes/src/main/scala/Probe.scala']) == ['SpinalProbes']
    assert len(projects(['scripts/ci-local.sh'])) >= 9


def test_package_documentation_does_not_select_builds():
    assert not any(select(['vscode/README.md', 'SpinalProbes/README.md']).values())
