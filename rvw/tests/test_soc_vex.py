"""Fast checks for the project-owned composed core adapter."""
import importlib.util
from pathlib import Path
import struct
import pytest

pytestmark = pytest.mark.fast
ROOT = Path(__file__).resolve().parents[2]


def adapter():
    spec = importlib.util.spec_from_file_location('soc_vex_adapter',ROOT/'SpinalSoc/examples/vex/adapter.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def elf(tmp_path, base=0x80000000, size=8, entry=0x80000000):
    ident=b'\x7fELF\x01\x01\x01'+bytes(9)
    header=struct.pack('<16sHHIIIIIHHHHHH',ident,2,243,1,entry,52,0,0,52,32,1,0,0,0)
    program=struct.pack('<IIIIIIII',1,84,base,base,4,size,7,4)
    path=tmp_path/'test.elf';path.write_bytes(header+program+b'\x13\x01\x02\x03')
    return path


def test_preload_image(tmp_path):
    out=tmp_path/'image.hex'
    assert adapter().image(elf(tmp_path),out)==0
    words=out.read_text().splitlines()
    assert len(words)==16384
    assert words[:3]==['03020113','00000000','00000000']


@pytest.mark.parametrize('base,size,entry',[(0x7ffffffc,8,0x80000000),(0x8000fffc,8,0x80000000),(0x80000000,8,0x80000004)])
def test_refuse_outside_profile(tmp_path,base,size,entry):
    with pytest.raises(ValueError):
        adapter().image(elf(tmp_path,base,size,entry),tmp_path/'image.hex')
    assert not (tmp_path/'image.hex').exists()


def test_configure_resolves_captured_paths(tmp_path):
    import tomllib
    spec=importlib.util.spec_from_file_location('soc_vex_configure',ROOT/'SpinalSoc/examples/vex/configure.py')
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    core=tmp_path/'core';(core/'src/main/scala/vexriscv').mkdir(parents=True)
    (core/'src/main/scala/vexriscv/VexRiscv.scala').write_text('// fixture')
    compiled=tmp_path/'classes';compiled.mkdir()
    path=module.configure(tmp_path/'project',core,str(compiled))
    config=tomllib.loads(path.read_text())['core']
    assert config['source_repo']==str(core)
    assert config['source_env']=='VEXRISCV'
    assert str(compiled) in config['cache_paths']
    assert 'RVW_SOC_CLASSPATH' in config['input_env']
    assert all(Path(p).is_absolute() for p in config['cache_paths'])
    with pytest.raises(ValueError,match='must be new'):
        module.configure(tmp_path/'project',core)
    with pytest.raises(ValueError,match='must exist'):
        module.configure(tmp_path/'bad',core,str(tmp_path/'missing'))


def test_standalone_checker_keeps_missing_and_wrong_uart_failures(tmp_path):
    import json
    spec=importlib.util.spec_from_file_location('soc_vexii_check',ROOT/'SpinalSoc/examples/vexii/check-results.py')
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    manifest=tmp_path/'jobs.tsv';manifest.write_text('image\t31\t1000\t0\tuart_irq\n')
    log=tmp_path/'run.log';log.write_text('')
    with pytest.raises(ValueError,match='missing or extra'):
        module.check(manifest,log)
    log.write_text('SOC_RESULT '+json.dumps(dict(status='pass',uart_hex=''))+'\n')
    assert module.check(manifest,log)['status']=='fail'
    log.write_text('SOC_RESULT '+json.dumps(dict(status='pass',uart_hex='49'))+'\n')
    assert module.check(manifest,log)['status']=='pass'
