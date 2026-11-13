import ast
import json
from pathlib import Path
import pytest
from rvw.arch.gem5_export import export
from rvw.ooo.project import configuration

pytestmark=pytest.mark.fast


def test_gem5_export_shared_dimensions(tmp_path):
    p=Path(__file__).resolve().parents[2]/'Arch/reference/boom-large.json'
    out=tmp_path/'generated';r=export(p,out)
    ast.parse((out/'model.py').read_text())
    core=json.loads((out/'core.json').read_text())
    own=json.loads((out/'ooo.json').read_text())
    assert own['rob_entries']==core['cpu']['numROBEntries']==96
    assert own['rename_width']==core['cpu']['renameWidth']==3
    assert configuration(core)==configuration(own)
    assert r['description_sha256']
    with pytest.raises(FileExistsError):
        export(p,out)
