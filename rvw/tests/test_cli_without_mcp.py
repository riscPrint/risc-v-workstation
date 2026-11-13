"""The CLI parser loads without the optional mcp extra (anyio, mcp, uvicorn)."""
import subprocess
import sys
import pytest

pytestmark = pytest.mark.fast


def test_every_command_parser_loads_without_the_mcp_extra():
    code = ("import sys\n"
            "for name in ('anyio', 'mcp', 'uvicorn', 'starlette'):\n"
            "    sys.modules[name] = None\n"
            "from rvw.cli import build_parser\n"
            "build_parser().parse_args(['regress', 'cocotb', 'bench.json', '--out', 'x'])\n")
    result = subprocess.run([sys.executable, '-c', code], capture_output=True, text=True, timeout=60)
    assert result.returncode == 0, result.stderr[-2000:]
