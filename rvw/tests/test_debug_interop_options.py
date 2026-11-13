"""Legal absent debug features must not become failed client checks."""
import json
import pytest
from rvw.debug.interop import assess, write_c3, CHECKS

pytestmark = pytest.mark.fast


def test_optional_watchpoint_is_unsupported(tmp_path):
    output = 'RVW_CONNECTED\nRVW_COMPLETE\nRVW_UNSUPPORTED:watchpoint:no store trigger\n'
    output += '\n'.join('RVW_CHECK:' + name for name in CHECKS if name != 'watchpoint')
    summary = assess(output, 0, False, expect_reset=False, allowed_unsupported=('watchpoint',))
    assert summary['status'] == 'pass'
    assert summary['missing'] == []
    summary.update(target='rtl', openocd_version='test')
    write_c3(summary, tmp_path)
    result = json.loads((tmp_path / 'results.json').read_text())
    assert len(result['tests']) == 7
    assert all(t['status'] == 'pass' for t in result['tests'])
    assert result['unsupported'] == [{'id': 'interop.watchpoint', 'reason': 'no store trigger'}]


def test_undeclared_unsupported_marker_cannot_hide_failure():
    output = 'RVW_CONNECTED\nRVW_COMPLETE\nRVW_UNSUPPORTED:load:invented\n'
    output += '\n'.join('RVW_CHECK:' + name for name in CHECKS if name != 'load')
    summary = assess(output, 0, False, expect_reset=False)
    assert summary['status'] == 'fail'
    assert 'load' in summary['missing']


def test_profile_without_transport_cannot_start_implicit_model(tmp_path):
    from rvw.debug.api import interop_run
    p = tmp_path / 'profile.toml'
    p.write_text('schema = "rvw.debug-profile/1"\nname = "cpu"\n')
    with pytest.raises(ValueError, match=r'no \[transport\]'):
        interop_run(tmp_path / 'out', 'unused.elf', profile=p)


def test_attach_starts_at_valid_elf_entry():
    from rvw.debug.interop import openocd_config
    config = openocd_config(1234, log='openocd.log', entry=0x80000000)
    assert config.index('halt') < config.index('reg pc 0x80000000')
