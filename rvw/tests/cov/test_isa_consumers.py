import json
import pytest
from .test_isa import manifest
from rvw.cov.isa import check_manifest
from rvw.cov.isa_consumers import REQUIRED


def configured(tmp_path):
    path, data = manifest(tmp_path)
    data['extensions']['i']['version'] = '2.1'
    item = {'xlen': 32, 'extensions': {'i': '2.1', 'm': '2.0'}, 'options': {}}
    (tmp_path / 'config.json').write_text(json.dumps({'isa_config': item}))
    data['probes'] = {name: {'kind': 'json', 'path': 'config.json', 'key': ['isa_config']} for name in REQUIRED}
    path.write_text(json.dumps(data))
    return path, data, item


def test_no_probes_never_verifies_versions(tmp_path):
    path, data = manifest(tmp_path)
    data['extensions']['i']['version'] = '2.1'
    path.write_text(json.dumps(data))
    report = check_manifest(path)
    assert report['status'] == 'inconclusive'
    assert report['unchecked_consumers'] == list(REQUIRED)


def test_all_configurations_and_capture(tmp_path):
    path, data, item = configured(tmp_path)
    result = check_manifest(path)
    assert result['status'] == 'consistent'
    assert not result['unchecked_consumers']
    assert len(result['probes']) == 5
    assert 'capture' in result


@pytest.mark.parametrize('change', ['version', 'xlen', 'extensions', 'option'])
def test_contradictions(tmp_path, change):
    path, data, item = configured(tmp_path)
    if change == 'version':
        item['extensions']['m'] = '1.0'
    elif change == 'xlen':
        item['xlen'] = 64
    elif change == 'extensions':
        del item['extensions']['m']
    else:
        data['options']['misaligned'] = 'trap'
        item['options']['misaligned'] = 'emulate'
        path.write_text(json.dumps(data))
    (tmp_path / 'config.json').write_text(json.dumps({'isa_config': item}))
    with pytest.raises(ValueError, match='contradict'):
        check_manifest(path)


def test_missing_options_and_versions_remain_unknown(tmp_path):
    path, data, item = configured(tmp_path)
    data['options']['misaligned'] = 'trap'
    path.write_text(json.dumps(data))
    item['extensions']['m'] = None
    (tmp_path / 'config.json').write_text(json.dumps({'isa_config': item}))
    result = check_manifest(path)
    assert result['status'] == 'inconclusive'
    assert result['probes']['dut']['unverified_versions'] == ['m']
    assert result['probes']['dut']['unverified_options'] == ['misaligned']


def test_native_compiler_probe(tmp_path):
    from pathlib import Path
    compiler = Path('/opt/homebrew/opt/riscv-gnu-toolchain/bin/riscv64-unknown-elf-gcc')
    if not compiler.is_file():
        pytest.skip('native RISC-V GCC unavailable')
    path, data, item = configured(tmp_path)
    data['probes']['compiler'] = {'kind': 'gcc', 'argv': [str(compiler), '-march=rv32im', '-mabi=ilp32']}
    path.write_text(json.dumps(data))
    report = check_manifest(path)
    assert report['probes']['compiler']['observed']['extensions'] == {'i': '2.1', 'm': '2.0', 'zmmul': '1.0'}


def test_native_capability_command_and_failure(tmp_path):
    import sys
    path, data, item = configured(tmp_path)
    item['schema'] = 'rvw.isa-consumer/1'
    data['probes']['dut'] = {'kind': 'command', 'argv': [sys.executable, '-c',
        'import json; print(' + repr(json.dumps(item)) + ')']}
    path.write_text(json.dumps(data))
    assert check_manifest(path)['status'] == 'consistent'
    data['probes']['dut']['argv'] = [sys.executable, '-c', 'raise SystemExit(2)']
    path.write_text(json.dumps(data))
    with pytest.raises(ValueError, match='probe failed'):
        check_manifest(path)


def test_toml_configuration(tmp_path):
    path, data, item = configured(tmp_path)
    (tmp_path / 'act.toml').write_text('''[target]
xlen = 32
[target.extensions]
i = "2.1"
m = "2.0"
''')
    data['probes']['act'] = {'kind': 'toml', 'path': 'act.toml', 'key': ['target']}
    path.write_text(json.dumps(data))
    assert check_manifest(path)['status'] == 'consistent'


def test_patch_zero_versions_are_equivalent(tmp_path):
    path, data, item = configured(tmp_path)
    data['extensions']['i']['version'] = '2.1.0'
    path.write_text(json.dumps(data))
    assert check_manifest(path)['status'] == 'consistent'


def test_unknown_version_labels_cannot_earn_consistent(tmp_path):
    path, data, item = configured(tmp_path)
    data['extensions']['i']['version'] = 'latest'
    path.write_text(json.dumps(data))
    item['extensions']['i'] = 'latest'
    (tmp_path / 'config.json').write_text(json.dumps({'isa_config': item}))
    result = check_manifest(path)
    assert result['status'] == 'inconclusive'
    assert result['probes']['dut']['unverified_versions'] == ['i']
