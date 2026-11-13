import importlib.util
from pathlib import Path
import subprocess
import pytest

pytestmark=pytest.mark.fast
ROOT=Path(__file__).resolve().parents[2]
spec=importlib.util.spec_from_file_location('docs_build',ROOT/'scripts/build-docs.py')
docs=importlib.util.module_from_spec(spec);spec.loader.exec_module(docs)


def test_every_cli_tool_readme_is_a_site_page():
    pages=docs.readmes()
    for path in (ROOT/'rvw/src/rvw').glob('*/README.md'):
        assert path.relative_to(ROOT).as_posix() in pages
    assert 'Cosim/README.md' in pages


def test_docs_staging_does_not_write_sources(tmp_path):
    done=subprocess.run(['python3',str(ROOT/'scripts/build-docs.py'),'--check','--out',str(tmp_path/'site')],capture_output=True,text=True)
    assert done.returncode==0,done.stderr
    assert 'tool README pages' in done.stdout
    assert not (tmp_path/'site').exists()
