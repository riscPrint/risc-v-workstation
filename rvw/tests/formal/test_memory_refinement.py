"""An abstract memory contract must state its observable initialization policy."""
from copy import deepcopy
import json
from pathlib import Path
from types import SimpleNamespace
import pytest
from rvw.formal.memory_refinement import validate, model, run

pytestmark=pytest.mark.fast
ROOT=Path(__file__).resolve().parents[3]


def spec():
    return json.loads((ROOT/'SpinalChecks/equiv/memory/spec.json').read_text())


@pytest.mark.parametrize('field,value', [('unwritten','arbitrary'),('address_width',0),('address_width',9),
                                        ('word_width',True),('read_latency',2),('byte_enable',True)])
def test_unsupported_semantics_are_not_ignored(field,value):
    s=spec();s[field]=value
    with pytest.raises(ValueError):validate(s)


def test_port_aliases_are_refused():
    s=spec();s['ports']['read_address']=s['ports']['write_address']
    with pytest.raises(ValueError,match='distinct'):validate(s)


def test_model_keeps_storage_uninitialized_and_masks_unwritten_words():
    text=model(spec(),'Logical')
    assert 'initial' not in text and 'valid <= 0' in text
    assert "valid[ra] ? words[ra] : 8'd0" in text
    s=spec();s['read_latency']=1
    assert 'else rd <=' in model(s,'Logical')


def test_inconclusive_backend_is_not_promoted_to_refinement(tmp_path,monkeypatch):
    from rvw.formal import equiv
    s=tmp_path/'spec.json';s.write_text(json.dumps(spec()))
    def backend(args):
        assert args.memory_spec is None and args.memory_map is True
        assert args.unmatched_state=='prove' and args.gold
        path=Path(args.out);path.mkdir()
        (path/'result.json').write_text(json.dumps({'status':'inconclusive','reason':'budget'}))
        return 1
    monkeypatch.setattr(equiv,'run',backend)
    args=SimpleNamespace(memory_spec=str(s),out=str(tmp_path/'out'),top='Banked',gate=['banked.v'],
                         latency=0,settle=0,json=False)
    assert run(args)==1
    result=json.loads((tmp_path/'out/result.json').read_text())
    assert result['status']=='inconclusive'
    assert 'shared initial RAM assumptions' in result['scope']
