import copy
import importlib.util
import json
from pathlib import Path

import pytest

pytestmark = pytest.mark.fast
ROOT = Path(__file__).resolve().parents[2]
EXAMPLE = ROOT / 'examples/vexiiriscv'


def generator():
    spec = importlib.util.spec_from_file_location('vexii_csr_bank', EXAMPLE / 'rvw/csr-bank-programs.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.generate


def test_nine_catalog_views_generate_without_trap_setup(tmp_path):
    obj = generator()(EXAMPLE / 'csr-bank.json', tmp_path / 'out')
    assert len(obj['views']) == 9
    assert {v['address'] for v in obj['views']} == {0x340,0x343,0x341,0x305,0x301,0xf11,0xf12,0xf13,0xf14}
    for view in obj['views']:
        text = (tmp_path / 'out' / (view['name'] + '.S')).read_text()
        assert 'handler:' not in text and 'mret' not in text and 'la t0, handler' not in text
        assert 'bne s2, t0, fail' in text
    assert 'li t0, 46' in (tmp_path / 'out/marchid.S').read_text()


@pytest.mark.parametrize('fault', ['rv64','alias','shift','supervisor','setup'])
def test_refuse_models_outside_the_native_binding(tmp_path, fault):
    model = json.loads((EXAMPLE / 'csr-bank.json').read_text())
    if fault == 'rv64': model['xlen'] = 64
    if fault == 'alias':
        view = copy.deepcopy(model['views'][0]);view.update(name='second',address=0x345,privilege='M');view.pop('catalog')
        model['views'].append(view)
    if fault == 'shift':
        model['views'][0].update(shift=1,mask=0x7fffffff,write_mask=0x7fffffff)
    if fault == 'supervisor':
        model['views'][0].pop('catalog');model['views'][0].update(address=0x140,privilege='S')
    if fault == 'setup': model['setup'] = ['open_pmp']
    source = tmp_path/'model.json';source.write_text(json.dumps(model))
    with pytest.raises(ValueError): generator()(source,tmp_path/'out')
    assert not (tmp_path/'out').exists()
