import json
from rvw.farm import cli, mcp_tools


def test_cli_and_mcp_dashboard_filters(tmp_path, capsys):
    import argparse
    parser = argparse.ArgumentParser()
    cli.register(parser.add_subparsers())
    output = tmp_path / 'dashboard.html'
    args = parser.parse_args(['farm', 'dashboard', '--root', str(tmp_path), '--out', str(output),
                             '--core', 'fixture', '--suite', 'isa', '--config', 'a', '--run', 'chosen'])
    args.func(args)
    result = json.loads(capsys.readouterr().out)
    assert result['filters']['config'] == 'a'
    assert result['runs'] == 0
    assert mcp_tools.execute_json(action='dashboard', root=str(tmp_path), out=str(output), config='a')['filters']['config'] == 'a'


def test_new_mcp_tools_are_registered():
    specs = mcp_tools.mcp_tools()
    assert {'farm_recover', 'farm_dashboard', 'farm_classify', 'farm_notifications'} <= {s.name for s in specs}
