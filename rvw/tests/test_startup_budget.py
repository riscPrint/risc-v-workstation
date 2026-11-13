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
