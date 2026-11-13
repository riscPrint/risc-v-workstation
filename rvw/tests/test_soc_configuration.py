import json
import pytest
from rvw.soc.configuration import configuration

pytestmark=pytest.mark.fast


def test_fragments(tmp_path):
    (tmp_path/'clock.json').write_text(json.dumps({'clock_hz':100,'devices':{'uart':{'class':'First'}}}))
    (tmp_path/'second.json').write_text(json.dumps({'clock_hz':200,'devices':{'ram':{'type':'ram'}}}))
    p=tmp_path/'compose.json'
    p.write_text(json.dumps({'fragments':['clock.json','second.json'],'clock_hz':300,'devices':{'uart':{'class':'Last'}}}))
    config,hashes=configuration(p)
    assert config==dict(clock_hz=300,devices=dict(uart={'class':'Last'},ram={'type':'ram'}))
    assert len(hashes)==2
    assert all(len(h['sha256'])==64 for h in hashes)


def test_nested_fragments_refused(tmp_path):
    (tmp_path/'fragment.json').write_text('{"fragments": []}')
    p=tmp_path/'compose.json';p.write_text('{"fragments": ["fragment.json"]}')
    with pytest.raises(ValueError,match='expected fields'):configuration(p)


def test_composed_fragment_identity(tmp_path):
    from pathlib import Path
    from rvw.soc.compose import compose
    root=Path(__file__).resolve().parents[2]
    spec=json.loads((root/'SpinalSoc/examples/compose.json').read_text())
    (tmp_path/'soc.json').write_text((root/'SpinalSoc/examples/soc.json').read_text())
    (tmp_path/'base.json').write_text(json.dumps({'clock_hz':1234,'devices':spec.pop('devices')}))
    spec.pop('clock_hz');spec['fragments']=['base.json']
    src=tmp_path/'compose.json';src.write_text(json.dumps(spec))
    compose(src,tmp_path/'out')
    manifest=json.loads((tmp_path/'out/composition.json').read_text())
    assert manifest['clock_hz']==1234
    assert manifest['effective_configuration']['devices']['ram']['type']=='ram'
    assert len(manifest['fragments'])==1
