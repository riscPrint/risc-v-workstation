"""Boot launch policy and immutable runtime capture without a native compile."""
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
import zipfile
import pytest

pytestmark = pytest.mark.fast
EXAMPLE = Path(__file__).resolve().parents[2] / 'examples/vexiiriscv/rvw'


def module():
    spec = importlib.util.spec_from_file_location('freeze_runtime', EXAMPLE / 'linux/freeze_runtime.py')
    obj = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(obj)
    return obj


def test_frozen_runtime_preserves_classes_resources_and_order(tmp_path):
    classes = tmp_path / 'classes'
    (classes / 'p').mkdir(parents=True)
    (classes / 'p/A.class').write_bytes(b'class bytes')
    (classes / 'p/resource').write_bytes(b'resource bytes')
    library = tmp_path / 'library.jar'
    with zipfile.ZipFile(library, 'w') as archive:
        archive.writestr('library', b'library bytes')
    out = tmp_path / 'frozen'
    result = module().freeze(os.pathsep.join(map(str, [classes, library])), out)
    entries = [Path(p) for p in result.split(os.pathsep)]
    with zipfile.ZipFile(entries[0]) as archive:
        assert archive.read('p/A.class') == b'class bytes'
        assert archive.read('p/resource') == b'resource bytes'
    assert entries[1].read_bytes() == library.read_bytes()
    assert (out / 'classpath.txt').read_text().strip() == result
    (classes / 'p/A.class').write_bytes(b'new build')
    with zipfile.ZipFile(entries[0]) as archive:
        assert archive.read('p/A.class') == b'class bytes'
    with pytest.raises(FileExistsError):
        module().freeze(str(classes), out)
    with pytest.raises(ValueError, match='outside'):
        module().freeze(str(classes), classes / 'recursive')


def script(path, text):
    path.write_text(text)
    path.chmod(0o755)


@pytest.mark.parametrize('threads,opt', [('1', '3'), ('2', '0')])
def test_launcher_reaches_nice_ten_once(tmp_path, threads, opt):
    root, commands = tmp_path / 'root', tmp_path / 'bin'
    (root / 'scripts').mkdir(parents=True)
    commands.mkdir()
    script(root / 'scripts/with-lock.sh', '#!/bin/sh\nshift\nexec "$@"\n')
    script(commands / 'sbt', f'#!{sys.executable}\nimport os,json\nfrom pathlib import Path\nPath(os.environ["SBT_RECORD"]).write_text(str(os.getpriority(os.PRIO_PROCESS,0)))\nprint("/fake/scala-library.jar")\n')
    script(commands / 'java', f'#!{sys.executable}\nimport os,json\nprint(json.dumps(dict(nice=os.getpriority(os.PRIO_PROCESS,0),flags=os.environ["SPINAL_VERILATOR_FLAGS"])))\n')
    env = dict(os.environ, RVW_HOME=str(root), VEXIIRISCV=str(tmp_path),
               PATH=str(commands) + os.pathsep + os.environ['PATH'], SBT_RECORD=str(tmp_path / 'sbt-nice'),
               RVW_BOOT_THREADS=threads, RVW_BOOT_OPT=opt)
    for key in ('SPINAL_VERILATOR_FLAGS', 'RVW_BOOT_CLASSPATH', 'RVW_BOOT_FREEZE_RUNTIME'):
        env.pop(key, None)
    run = subprocess.run(['bash', str(EXAMPLE / 'boot-slices.sh')],
                         env=env, capture_output=True, text=True, timeout=20)
    assert run.returncode == 0, run.stderr
    result = json.loads(run.stdout)
    assert result['nice'] == 10
    assert (tmp_path / 'sbt-nice').read_text() == '10'
    assert f'-CFLAGS -O{opt}' in result['flags']
    assert f'--threads {threads}' in result['flags']


def test_checkpoint_comparison_includes_ram(tmp_path):
    spec = importlib.util.spec_from_file_location('boot_bench', EXAMPLE / 'linux/bench.py')
    bench = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(bench)
    def image(name, ram):
        path = tmp_path / name
        with zipfile.ZipFile(path, 'w') as archive:
            archive.writestr('state.json', b'{"cycle":"100"}')
            archive.writestr('ram.bin', ram)
        return path
    assert bench.digest(image('a.zip', b'ab')) == bench.digest(image('b.zip', b'ab'))
    assert bench.digest(tmp_path / 'a.zip') != bench.digest(image('c.zip', b'ac'))
