"""The MCP kit reads the CLI's proposal or nested proof result."""
import json
import sqlite3
from pathlib import Path

import pytest

from rvw.cli import main
from rvw.formal.commands.datapath_kit import mcp_tools

pytestmark = pytest.mark.fast


@pytest.mark.parametrize('confirm', [False, True])
def test_mcp_kit_uses_cli_output_path(tmp_path, monkeypatch, confirm):
    db = tmp_path / 'design.db'
    with sqlite3.connect(db) as conn:
        schema = Path(__file__).parents[3] / 'rvw/src/rvw/query/schema.sql'
        conn.executescript(schema.read_text())
        conn.execute("INSERT INTO meta VALUES ('schema','rvw.designdb/20')")
    args = dict(unit='mul', db=str(db), out=str(tmp_path / 'out'))
    if confirm:
        binding = tmp_path / 'binding.json'
        binding.write_text('{"top":"Reviewed","ports":{"a":"a","y":"y"}}')
        args.update(confirm=True, binding=str(binding), rtl='dut.v', model='mul.c', width=32)
        from rvw.formal import datapath
        original = datapath.run

        def prove(parsed):
            if parsed.unit:
                return original(parsed)
            out = Path(parsed.out)
            out.mkdir()
            (out / 'result.json').write_text('{"status":"proved"}')
            return 0

        monkeypatch.setattr(datapath, 'run', prove)

    class Job:
        def run(self, argv):
            return main(argv[3:])

        def tail(self, _):
            return []

    result = mcp_tools()[0].handler(Job(), **args)
    assert result['status'] == ('proved' if confirm else 'no_candidates')
    if not confirm:
        assert result['proof_ran'] is False
