import json
import shutil
import subprocess
import sys

import pytest

from rvw.formal.export import export_revision


def commit(repo):
    subprocess.run(['git', '-C', str(repo), 'add', '.'], check=True)
    subprocess.run(['git', '-C', str(repo), '-c', 'user.name=Test', '-c', 'user.email=test@example.org', 'commit', '-qm', 'fixture'], check=True)
    return subprocess.check_output(['git', '-C', str(repo), 'rev-parse', 'HEAD'], text=True).strip()


@pytest.mark.skipif(not shutil.which('yosys'), reason='needs Yosys')
def test_committed_revision_module_selection(tmp_path):
    repo = tmp_path / 'repo'
    repo.mkdir()
    subprocess.run(['git', 'init', '-q', str(repo)], check=True)
    (repo / 'design.v').write_text('module leaf(input clk,a, output reg q); always @(posedge clk) q<=a; endmodule\nmodule unrelated(input a,output q); missing m(a,q); endmodule')
    generator = repo / 'build.py'
    generator.write_text('import os,sys,pathlib,shutil\na=sys.argv\nout=pathlib.Path(a[a.index("--rtl")+1]);out.mkdir();shutil.copy(pathlib.Path(os.environ["TEST_SOURCE"])/"design.v",out/"all.v")\n')
    (repo / 'rvw.toml').write_text(f'''[core]
name="fixture"
adapter="false"
source_repo="."
source_env="TEST_SOURCE"
[query]
build=["{sys.executable}", "{generator}"]
[formal]
export_dependencies=["."]
''')
    first = commit(repo)
    (repo / 'design.v').write_text((repo / 'design.v').read_text().replace('q<=a', 'q<=!a'))
    second = commit(repo)
    a, rec = export_revision(repo / 'rvw.toml', first, None, 'leaf', tmp_path / 'first', 30)
    b, _ = export_revision(repo / 'rvw.toml', second, None, 'leaf', tmp_path / 'second', 30)
    assert a.read_text() != b.read_text()
    assert 'module leaf' in a.read_text() and 'unrelated' not in a.read_text()
    assert rec['revision'] == first
    assert rec['generator_dependencies'][0]['revision'] == second
    assert json.loads((a.parent / 'export.json').read_text())['module_sha256']
    with pytest.raises(ValueError, match='module selection failed'):
        export_revision(repo / 'rvw.toml', first, None, 'absent', tmp_path / 'absent', 30)
    (repo / 'build.py').write_text('raise Exception("dirty")')
    with pytest.raises(ValueError, match='must be clean'):
        export_revision(repo / 'rvw.toml', first, None, 'leaf', tmp_path / 'dirty', 30)


def test_revision_arguments_fail_closed(tmp_path):
    from rvw.cli import main
    out = tmp_path / 'out'
    assert main(['formal', 'equiv', '--gold-rev', 'HEAD', '--top', 'leaf', '--out', str(out)]) == 1
    assert json.loads((out / 'result.json').read_text())['status'] == 'inconclusive'
