"""ACT4 selection and provenance need no native core."""
import json
from pathlib import Path
import pytest
from rvw.regress.act4 import description, selection, verify_manifest, digest
from rvw.regress.config import Suite, ConfigError
from rvw.regress.discover import discover

pytestmark = pytest.mark.fast


def profile(tmp_path):
    platform = dict(name='test', xlen=32, isa='rv32im_zicsr_zifencei', reset_pc='0x80000000',
                    ram=[dict(base='0x80000000', size='0x1000000')], mmio=[], privilege_modes='M')
    (tmp_path/'platform.json').write_text(json.dumps(platform))
    data = dict(schema='rvw.act4/1', platform='platform.json', halt='tohost-1-3',
                extensions={'i':'= 2.1', 'm':'= 2.0', 'zicsr':'= 2.0', 'zifencei':'= 2.0.0', 'sm':'= 1.12.0'}, params={'MXLEN':32})
    p = tmp_path/'profile.json'
    p.write_text(json.dumps(data))
    return p, data


def test_selection(tmp_path):
    p, _ = profile(tmp_path)
    assert selection(p)['extensions'] == ['i', 'm', 'zicsr', 'zifencei']
    assert selection(p)['privilege_modes'] == 'M'


@pytest.mark.parametrize('change', [dict(extensions={'i':'= 2.1', 'sm':'= 1.12.0','s':'= 1.12.0'}),
                                    dict(params={'MXLEN':64}), dict(halt='completion-only'),
                                    dict(test_extensions=[]), dict(privileged_extensions=['sv32'])])
def test_invalid_declaration(tmp_path, change):
    p, data = profile(tmp_path)
    data.update(change)
    p.write_text(json.dumps(data))
    with pytest.raises(ValueError):
        description(p)


def test_manifest_checks_complete_set_and_bytes(tmp_path):
    elfs = tmp_path/'elfs'
    elfs.mkdir()
    elf = elfs/'add.elf'
    elf.write_bytes(b'ELF fixture')
    manifest = tmp_path/'manifest.json'
    manifest.write_text(json.dumps(dict(schema='rvw.act4-build/1', status='built',
                                       tests=[dict(path='add.elf',sha256=digest(elf))])))
    suite = Suite('act4', dir=elfs, glob='*.elf', act4_manifest=manifest)
    assert len(discover(suite)) == 1
    elf.write_bytes(b'changed')
    with pytest.raises(ConfigError, match='hashes'):
        discover(suite)
    elf.unlink()
    with pytest.raises(ConfigError):
        discover(suite)


def test_failed_build_never_discovers(tmp_path):
    elfs = tmp_path/'elfs'
    elfs.mkdir()
    manifest = tmp_path/'manifest.json'
    manifest.write_text(json.dumps(dict(schema='rvw.act4-build/1',status='error',tests=[])))
    with pytest.raises(ValueError, match='failed'):
        verify_manifest(manifest, elfs)


def test_build_retains_reference_inputs_and_final_elf(tmp_path, monkeypatch):
    from rvw.regress import act4
    from rvw.common.proc import Result
    p, data = profile(tmp_path)
    data.update(revision='a'*40, files={n:n for n in ('sail.json','link.ld','rvmodel_macros.h')})
    p.write_text(json.dumps(data))
    for n in data['files']:
        (tmp_path/n).write_text('fixture')
    out = tmp_path/'out'
    def command(argv, **kw):
        if '--version' in argv:
            return Result(0, stdout='test tool 1.0')
        if 'rev-parse' in argv:
            return Result(0, stdout='a'*40)
        if 'status' in argv:
            return Result(0, stdout='')
        elf = out/'work/rvw-act4/elfs/I/add.elf'
        elf.parent.mkdir(parents=True)
        elf.write_bytes(b'final self-check fixture')
        return Result(0)
    monkeypatch.setattr(act4, 'run_group', command)
    report = act4.build(p, tmp_path, out)
    assert report['status'] == 'built'
    assert report['counts'] == {'I':1}
    assert report['tools']['reference']['version'] == ['test tool 1.0']
    assert 'sail.json' in report['files']
    verify_manifest(out/'manifest.json', out/'work/rvw-act4/elfs')


def test_all_applicable_uses_udb_metadata(tmp_path):
    p, data = profile(tmp_path)
    data['all_applicable'] = True
    p.write_text(json.dumps(data))
    assert selection(p)['test_selection'] == 'all-applicable'
    assert selection(p)['include_priv_tests'] is True
    assert 'sm' in selection(p)['extensions']
    data['test_extensions'] = ['i']
    p.write_text(json.dumps(data))
    with pytest.raises(ValueError, match='mutually exclusive'):
        selection(p)


def test_reference_extensions_can_differ_from_trace_isa(tmp_path):
    p, data = profile(tmp_path)
    platform_path = tmp_path / 'platform.json'
    platform = json.loads(platform_path.read_text())
    platform['reference_isa'] = platform['isa'] + '_zicntr'
    platform_path.write_text(json.dumps(platform))
    data['extensions']['zicntr'] = '= 2.0'
    p.write_text(json.dumps(data))
    _, loaded, selected = description(p)
    assert loaded.isa == platform['isa']
    assert 'zicntr' in selected
