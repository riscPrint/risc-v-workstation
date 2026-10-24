"""Review 15: validate arguments before any handler, worker, or job can run."""
from dataclasses import replace

import pytest

from rvw.mcp.registry import Registry, discover
from rvw.mcp.spec import ToolSpec, schema


def sample(s):
    if 'enum' in s:
        return s['enum'][0]
    kind = s['type']
    return {'string': 'fixture', 'integer': 1, 'number': 1.0, 'boolean': False,
            'array': [sample(s['items'])] if kind == 'array' else None}.get(kind)


def tool_names():
    r = Registry(discover()[0])
    try:
        return list(r.tools)
    finally:
        r.jobs.shutdown()


@pytest.mark.parametrize('name', tool_names())
def test_every_tool_rejects_wrong_types_before_dispatch(name, monkeypatch):
    r = Registry(discover()[0])
    spec = r.tools[name]
    def forbidden(*args, **kwargs):
        pytest.fail('invalid arguments reached dispatch')
    r.tools[name] = replace(spec, handler=forbidden)
    monkeypatch.setattr(r.jobs, 'submit', forbidden)
    monkeypatch.setattr(r, '_isolated', forbidden)
    props = spec.input_schema['properties']
    valid = {k: sample(props[k]) for k in spec.input_schema.get('required', [])}
    try:
        # job_list has no properties: reject a non-object rather than normalizing it to {}.
        bad_calls = [[]] if not props else []
        for key, prop in props.items():
            wrong = 'false' if prop.get('type') != 'string' else False
            bad_calls.append({**valid, key: wrong})
        bad_calls.append({**valid, 'unknown_argument': True})
        bad_calls.extend({k: v for k, v in valid.items() if k != missing} for missing in valid)
        for args in bad_calls:
            _, result, error = r.call_json(name, args)
            assert error and result['error'].startswith(f'bad arguments for {name}:'), (args, result)
        assert not r.jobs.list()
    finally:
        r.jobs.shutdown()


@pytest.mark.parametrize('args', [
    {'mode': 'other'}, {'count': 0}, {'count': 4}, {'ratio': 0},
    {'ratio': float('nan')}, {'ratio': float('inf')}, {'items': []},
    {'items': [1]}, {'nested': {'extra': True}}, {'count': True},
])
@pytest.mark.parametrize('long,isolate', [(False, False), (True, False), (False, True)])
def test_schema_constraints_apply_before_all_dispatch_paths(args, long, isolate, monkeypatch):
    def forbidden(*unused, **kwargs):
        pytest.fail('invalid arguments reached handler or job submission')
    props = {'mode': {'type': 'string', 'enum': ['safe']},
             'count': {'type': 'integer', 'minimum': 1, 'maximum': 3},
             'ratio': {'type': 'number', 'exclusiveMinimum': 0},
             'items': {'type': 'array', 'items': {'type': 'string'}, 'minItems': 1},
             'nested': schema({})}
    r = Registry([ToolSpec('fixture', 'fixture', schema(props), forbidden, long=long, isolate=isolate)])
    monkeypatch.setattr(r.jobs, 'submit', forbidden)
    try:
        _, result, error = r.call_json('fixture', args)
        assert error and result['error'].startswith('bad arguments for fixture:'), result
    finally:
        r.jobs.shutdown()


def test_boolean_string_cannot_allow_missing_tests(tmp_path):
    from rvw.results import SuiteResults, TestEntry, save_results
    for label, tests in [('base', [TestEntry('shared', 'pass', seed=1),
                                    TestEntry('missing', 'fail', seed=1, signature='fail:7')]),
                         ('candidate', [TestEntry('shared', 'pass', seed=1)])]:
        save_results(SuiteResults(run_id=label, suite='isa', core='fake', config='small',
                                 created='2026-10-22T00:00:00Z', source={}, tests=tests), tmp_path / label)
    r, problems = Registry.discover({'regress'})
    assert not problems
    args = {'base': str(tmp_path / 'base'), 'candidate': str(tmp_path / 'candidate')}
    try:
        _, result, error = r.call_json('regress_compare', {**args, 'allow_missing': False})
        assert not error and result['verdict'] == 'reject', result
        output = tmp_path / 'verdict.json'
        _, result, error = r.call_json('regress_compare', {**args, 'allow_missing': 'false', 'out': str(output)})
        assert error and 'allow_missing' in result['error'], result
        assert not output.exists()
    finally:
        r.jobs.shutdown()


@pytest.mark.parametrize('name', ['reduce_run', 'bisect_run'])
@pytest.mark.parametrize('threshold', [-5, 0])
def test_hang_threshold_refused_before_job_submission(name, threshold, monkeypatch):
    r = Registry(discover()[0])
    def forbidden(*args, **kwargs):
        pytest.fail('invalid hang threshold reached job submission')
    monkeypatch.setattr(r.jobs, 'submit', forbidden)
    try:
        prop = r.tools[name].input_schema['properties']['hang_cycles']
        assert prop['minimum'] == 1
        args = {'run_dir': 'unused', 'hang_cycles': threshold}
        if name == 'bisect_run':
            args['good'] = 'unused'
        _, result, error = r.call_json(name, args)
        assert error and 'hang_cycles' in result['error']
        assert not r.jobs.list()
    finally:
        r.jobs.shutdown()


def test_debug_numeric_bounds_refuse_before_dispatch(monkeypatch):
    r = Registry(discover()[0])
    def forbidden(*args, **kwargs):
        pytest.fail('out-of-range numeric argument reached dispatch')
    monkeypatch.setattr(r.jobs, 'submit', forbidden)
    monkeypatch.setattr(r, '_isolated', forbidden)
    names = ['reduce_run', 'bisect_run', 'bundle_make', 'wave_changes', 'wave_sample',
             'wave_cut', 'job_status', 'job_log']
    try:
        for name in names:
            spec = r.tools[name]
            r.tools[name] = replace(spec, handler=forbidden)
            props = spec.input_schema['properties']
            args = {k: sample(props[k]) for k in spec.input_schema.get('required', [])}
            for key, prop in props.items():
                if prop.get('type') not in ('integer', 'number'):
                    continue
                assert 'minimum' in prop or 'exclusiveMinimum' in prop, (name, key)
                bound = prop.get('minimum', prop.get('exclusiveMinimum'))
                invalid = bound - 1 if 'minimum' in prop else bound
                _, result, error = r.call_json(name, {**args, key: invalid})
                assert error and key in result['error'], (name, key, result)
        assert not r.jobs.list()
    finally:
        r.jobs.shutdown()
