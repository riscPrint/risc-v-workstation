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
    with pytest.raises(ValueError, match='git revision/export input failed'):
        export_revision(repo / 'rvw.toml', 'no-such-revision', None, 'leaf', tmp_path / 'missing-rev', 30)
    if all(shutil.which(tool) for tool in ('eqy', 'sby', 'yosys-abc', 'yices-smt2')):
        from rvw.cli import main
        for rev, expected in [(first, 'equivalent'), (second, 'not_equivalent')]:
            out = tmp_path / ('proof-' + rev)
            rc = main(['--project', str(repo / 'rvw.toml'), 'formal', 'equiv',
                       '--gold-rev', first, '--gate-rev', rev, '--top', 'leaf',
                       '--settle', '1', '--out', str(out)])
            result = json.loads((out / 'result.json').read_text())
            assert result['status'] == expected, result
            assert rc == (0 if expected == 'equivalent' else 1)
            assert result['exports']['gold']['revision'] == first
            assert result['exports']['gate']['revision'] == rev
    (repo / 'build.py').write_text('raise Exception("dirty")')
    with pytest.raises(ValueError, match='must be clean'):
        export_revision(repo / 'rvw.toml', first, None, 'leaf', tmp_path / 'dirty', 30)


def test_revision_arguments_fail_closed(tmp_path):
    from rvw.cli import main
    out = tmp_path / 'out'
    assert main(['formal', 'equiv', '--gold-rev', 'HEAD', '--top', 'leaf', '--out', str(out)]) == 1
    assert json.loads((out / 'result.json').read_text())['status'] == 'inconclusive'


def test_export_timeout_includes_lock_queue(tmp_path):
    repo = tmp_path / 'repo'
    repo.mkdir()
    subprocess.run(['git', 'init', '-q', str(repo)], check=True)
    locks = tmp_path / 'locks'
    (repo / 'rvw.toml').write_text(f'''[core]
name="fixture"
adapter="false"
source_env="TEST_SOURCE"
lock="export-test"
lock_dir="{locks}"
[query]
build=["{sys.executable}", "-c", "raise SystemExit(99)"]
[formal]
export_dependencies=["."]
''')
    rev = commit(repo)
    code = f'from rvw.common.lock import held; import sys\nwith held("export-test", directory={str(locks)!r}):\n print("ready",flush=True)\n sys.stdin.read()\n'
    holder = subprocess.Popen([sys.executable, '-c', code], stdin=subprocess.PIPE, stdout=subprocess.PIPE, text=True)
    try:
        assert holder.stdout.readline().strip() == 'ready'
        with pytest.raises(ValueError, match=r'revision build failed \(124\)'):
            export_revision(repo / 'rvw.toml', rev, None, 'leaf', tmp_path / 'export', 0.5)
        assert 'waiting for export-test' in (tmp_path / 'export/build.log').read_text()
    finally:
        holder.communicate(input='', timeout=10)
