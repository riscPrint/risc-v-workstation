import json
from pathlib import Path
import shutil

import pytest
from rvw.cli import main

ROOT=Path(__file__).resolve().parents[3]/'SpinalChecks/security/examples/pair'
TOOLS=all(shutil.which(t) for t in ('yosys','sby','yosys-abc'))


@pytest.mark.skipif(not TOOLS,reason='needs native formal tools')
@pytest.mark.parametrize('fixture,expected',[
 ('speculation-1-safe','pass'),('speculation-1-leaky','fail'),
 ('speculation-7-safe','pass'),('speculation-7-leaky','fail'),
 ('zkt-fixed','pass'),('zkt-leaky','fail'),
])
def test_native_seeded_security_contracts(tmp_path,fixture,expected):
    out=tmp_path/'out'
    main(['formal','security','pair','--manifest',str(ROOT/(fixture+'.json')),'--timeout','60','--out',str(out)])
    result=json.loads((out/'result.json').read_text())
    assert result['status']==expected,result
    assert result['proof']['status']==expected
    if expected=='fail':
        assert list((out/'proof').rglob('trace*.vcd'))
