"""A misspelled waiver scope must never turn into a wildcard waiver."""
import pytest

from rvw.regress.known import Known, load_known


ENTRY = '[[known]]\nsuite = "isa"\nid = "test"\nsignature = "fail:7"\n'


@pytest.mark.parametrize('field,value', [
    ('configs', '"large"'), ('reasonn', '"triaged"'), ('config', 'false'),
    ('config', '["small"]'), ('config', '""'), ('reason', '7'),
    ('recorded_at_rev', 'false'), ('recorded_at', '2026-10-23T00:00:00Z'),
])
def test_known_rejects_unknown_or_mistyped_fields_with_line(tmp_path, field, value):
    path = tmp_path / 'known.toml'
    path.write_text(ENTRY + f'{field} = {value}\n')
    with pytest.raises(ValueError, match=rf'{path}:5:.*{field}'):
        load_known(path)


@pytest.mark.parametrize('text', [
    'known = "oops"\n', 'known = {}\n', 'known = [1]\n',
    '[[knwon]]\nsuite = "isa"\n',
    ENTRY.replace('suite = "isa"', 'suite = 1'),
    ENTRY.replace('id = "test"', 'id = ""'),
    ENTRY.replace('signature = "fail:7"', 'signature = false'),
])
def test_known_malformed_structure_is_a_usage_error(tmp_path, text):
    path = tmp_path / 'known.toml'
    path.write_text(text)
    with pytest.raises(ValueError, match='known'):
        load_known(path)


def test_config_limited_waiver_cannot_match_missing_config():
    assert not Known('isa', 'test', 'fail:7', config='large').matches('isa', 'test', 'fail:7')


@pytest.mark.parametrize('transport', ['cli', 'mcp'])
def test_known_typo_refuses_gate_before_execution(fake, rvw, tmp_path, transport):
    (tmp_path / 'known.toml').write_text(ENTRY + 'configs = "large"\n')
    if transport == 'cli':
        code, _, data = rvw('regress', 'gate', '--core', fake.config, '--base-rev', 'HEAD', '--json')
        assert code == 2 and data is None
        assert 'known.toml:5:' in rvw.stderr and 'configs' in rvw.stderr
    else:
        from rvw.mcp.registry import Registry
        registry, problems = Registry.discover({'regress'})
        assert not problems
        try:
            _, data, error = registry.call_json('regress_gate', {'core': str(fake.config), 'base_rev': 'HEAD'})
            if not error and 'job_id' in data:
                _, data, error = registry.call_json('job_status', {'job_id': data['job_id'], 'wait_s': 60})
                assert not error and data['status'] == 'failed', data
            assert 'known.toml:5:' in str(data) and 'configs' in str(data)
        finally:
            registry.jobs.shutdown()
    assert not fake.calls()
