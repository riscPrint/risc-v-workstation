"""Cold-process import and CPU guards. No native tools are started."""
import json
import subprocess
import sys

import pytest

pytestmark = pytest.mark.fast


def test_parser_import_budget():
    code = '''
import json, os, sys, time
start = time.process_time()
from rvw.cli import build_parser
p = build_parser()
print(json.dumps({'cpu': time.process_time()-start, 'load': os.getloadavg(),
                  'modules': list(sys.modules)}))
'''
    results = [json.loads(subprocess.check_output([sys.executable, '-c', code], text=True))
               for _ in range(2)]
    for result in results:
        assert result['cpu'] < 0.4, result
        for prefix in ('jsonschema', 'numpy', 'z3', 'sqlite3', 'rvw.formal.flows',
                       'rvw.csr.catalog', 'rvw.query.ops', 'rvw.regress.runner'):
            assert not any(m == prefix or m.startswith(prefix + '.')
                           for m in result['modules']), (prefix, result)


def test_lazy_help_and_command_inventory():
    from rvw.cli import build_parser
    from rvw.mcp.command_map import nodes
    p = build_parser()
    with pytest.raises(SystemExit) as exc:
        p.parse_args(['query', '--help'])
    assert exc.value.code == 0
    paths = {path for path, _ in nodes(p)}
    assert ('query', 'drivers') in paths
    assert ('replay',) in paths
    assert ('backends',) in paths
    args = build_parser().parse_args(['query', 'drivers', 'signal', '--json', '--project', 'test.toml'])
    assert args.signal == 'signal'
    assert args.project == 'test.toml'
    assert args.json


def test_light_declarations_match_provider_commands():
    import argparse
    import importlib
    import pkgutil
    import rvw
    for module in pkgutil.iter_modules(rvw.__path__):
        if not module.ispkg:
            continue
        try:
            declaration = importlib.import_module(f'rvw.{module.name}.cli_declarations')
        except ModuleNotFoundError as exc:
            if exc.name == f'rvw.{module.name}.cli_declarations':
                continue
            raise
        parser = argparse.ArgumentParser()
        sub = parser.add_subparsers()
        importlib.import_module(f'rvw.{module.name}.cli').register(sub)
        assert declaration.COMMANDS == [(a.dest, a.help) for a in sub._choices_actions]


def test_core_registry_import_and_cpu_budget():
    code = '''
import json, os, sys, time
start = time.process_time()
from rvw.mcp.registry import Registry
registry, problems = Registry.discover(profile='core')
print(json.dumps({'cpu': time.process_time()-start, 'load': os.getloadavg(),
                  'modules': list(sys.modules), 'problems': problems,
                  'tools': sorted(registry.tools)}))
'''
    for _ in range(2):
        result = json.loads(subprocess.check_output([sys.executable, '-c', code], text=True))
        assert not result['problems'], result
        assert result['cpu'] < 0.4, result
        for prefix in ('jsonschema', 'numpy', 'z3', 'sqlite3', 'rvw.formal', 'rvw.query',
                       'rvw.cosim', 'rvw.regress', 'rvw.arch', 'rvw.wave'):
            assert not any(m == prefix or m.startswith(prefix + '.')
                           for m in result['modules']), (prefix, result)
        assert {'query_build_db', 'cosim_check', 'regress_gate'} <= set(result['tools'])


def test_core_workflow_declarations_match_live_providers():
    from dataclasses import fields
    from rvw.mcp.core_calls import DECLARATIONS
    from rvw.mcp.lazy import resolve
    from rvw.mcp.profiles import CORE_CALLS
    assert {row['spec']['name'] for row in DECLARATIONS} == CORE_CALLS
    for row in DECLARATIONS:
        live = resolve(row['provider'], row['spec']['name'])
        assert row['spec'] == {f.name: getattr(live, f.name) for f in fields(live)
                               if f.name != 'handler'}
        assert row['wants_job'] == live.wants_job


def test_schema_check_is_deferred_and_reused(monkeypatch):
    from jsonschema.validators import Draft202012Validator
    from rvw.mcp.registry import Registry
    from rvw.mcp.spec import ToolSpec, schema, ToolError
    calls = []
    original = Draft202012Validator.check_schema
    monkeypatch.setattr(Draft202012Validator, 'check_schema',
                        lambda *args, **kwargs: (calls.append(1), original(*args, **kwargs))[1])
    registry = Registry([ToolSpec('tiny', 'tiny', schema({'n': {'type': 'integer'}}, ['n']),
                                  lambda n: n)])
    assert not calls
    assert registry.call('tiny', {'n': 1}) == 1
    assert registry.call('tiny', {'n': 2}) == 2
    with pytest.raises(ToolError):
        registry.call('tiny', {'n': 'bad'})
    assert len(calls) == 1
    registry.jobs.shutdown()


def test_all_registry_does_not_load_csr_catalog_data():
    code = '''
import json, os, time
start = time.process_time()
from rvw.mcp.registry import Registry
registry, problems = Registry.discover()
from rvw.csr.catalog import _catalog
print(json.dumps({'cpu': time.process_time()-start, 'load': os.getloadavg(),
                  'catalog_reads': _catalog.cache_info().misses, 'problems': problems}))
'''
    for _ in range(2):
        result = json.loads(subprocess.check_output([sys.executable, '-c', code], text=True))
        assert not result['problems'], result
        assert result['catalog_reads'] == 0, result
        assert result['cpu'] < 0.7, result


def test_query_help_does_not_import_query_implementation():
    code = '''
import json, os, sys, time, contextlib, io
start = time.process_time()
from rvw.cli import main
with contextlib.redirect_stdout(io.StringIO()):
    try: main(['query', '--help'])
    except SystemExit as exc: assert exc.code == 0
print(json.dumps({'cpu': time.process_time()-start, 'load': os.getloadavg(),
                  'modules': list(sys.modules)}))
'''
    for _ in range(2):
        result = json.loads(subprocess.check_output([sys.executable, '-c', code], text=True))
        assert result['cpu'] < 0.4, result
        for prefix in ('jsonschema', 'sqlite3', 'rvw.query.ops', 'rvw.query.diff'):
            assert not any(m == prefix or m.startswith(prefix + '.')
                           for m in result['modules']), (prefix, result)
