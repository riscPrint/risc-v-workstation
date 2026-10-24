"""Adapter interpreter options survive the shared bundle/bisect binder."""
import os
from pathlib import Path

import pytest

from rvw.common.proc import run_group
from rvw.runs.adapter import Command
from rvw.runs.inputs import DebugInputs


@pytest.mark.parametrize('suffix', ['', '.adapter', '.py', '.sh'])
@pytest.mark.parametrize('lookup', ['path', 'PATH'])
def test_adapter_shebang_does_not_need_version(tmp_path, monkeypatch, suffix, lookup):
    script = tmp_path / ('adapter' + suffix)
    script.write_text('#!/bin/bash\n[ "$1" = run ] || exit 2\nprintf "adapter ran\\n"\n')
    script.chmod(0o755)
    if lookup == 'PATH':
        monkeypatch.setenv('PATH', str(tmp_path) + os.pathsep + os.environ['PATH'])
    inputs = DebugInputs()
    cmd = inputs.bind_adapter(Command(exe=[script.name if lookup == 'PATH' else str(script)]))
    assert Path(cmd.exe[-1]) != script
    result = run_group(cmd.argv(), capture=True, timeout=10, env=cmd.child_environment())
    assert result.returncode == 0 and result.stdout == 'adapter ran\n'
    assert inputs.record()['files'][0]['sha256']
    inputs.verify()


def test_native_adapter_needs_no_version(tmp_path, monkeypatch):
    inputs = DebugInputs()
    capture_tool = inputs.capture.tool
    native = Path('/bin/echo')

    def tool(path):
        assert Path(path) != native, 'C1 adapters have no required --version interface'
        return capture_tool(path)

    monkeypatch.setattr(inputs.capture, 'tool', tool)
    cmd = inputs.bind_adapter(Command(exe=[str(native)]))
    result = run_group(cmd.argv(), capture=True, timeout=10, env=cmd.child_environment())
    assert result.returncode == 0 and result.stdout == 'run\n'
    assert any(item['source'] == str(native) for item in inputs.record()['files'])
    inputs.verify()


@pytest.mark.parametrize('shebang, options', [
    ('/bin/bash -e', ['-e']),
    ('/bin/bash -eu', ['-eu']),
    ('/usr/bin/env bash', []),
])
def test_adapter_shebang_preserves_interpreter_options(tmp_path, shebang, options):
    script = tmp_path / 'adapter.sh'
    script.write_text(f'#!{shebang}\nprintf "%s\\n" "$-"\nset -o\n')
    script.chmod(0o755)
    inputs = DebugInputs()
    cmd = inputs.bind_adapter(Command(exe=[str(script)]))
    assert Path(cmd.exe[0]).is_absolute()
    assert cmd.exe[1:-1] == options
    result = run_group(cmd.argv(), capture=True, timeout=10, env=cmd.child_environment())
    assert result.returncode == 0
    flags = result.stdout.splitlines()[0]
    assert ('e' in flags) == bool(options)
    assert ('u' in flags) == ('u' in ''.join(options))
    pipefail = any(line.split() == ['pipefail', 'on'] for line in result.stdout.splitlines())
    assert pipefail == ('pipefail' in options)
    inputs.verify()


@pytest.mark.parametrize('shebang', ['/usr/bin/env -i bash', '/usr/bin/env bash -e', '/usr/bin/env -S bash -euo pipefail'])
def test_unsupported_env_shebang_refuses(tmp_path, shebang):
    from rvw.common.capture import CaptureError
    script = tmp_path / 'adapter.sh'
    script.write_text(f'#!{shebang}\nexit 0\n')
    with pytest.raises(CaptureError, match='unsupported shebang'):
        DebugInputs().bind_adapter(Command(exe=[str(script)]))


@pytest.mark.parametrize('header', [b'#!/bin/bash -e\n', b'#!/usr/bin/env python3\n'])
def test_shared_shebang_parser_preserves_arguments(header):
    from rvw.common.interpreter import script_interpreter
    expected = ['/bin/bash', '-e'] if b'bash' in header else ['python3']
    assert script_interpreter(header) == expected


@pytest.mark.parametrize('header', [b'#!\n', b'#!/usr/bin/env -i bash\n',
                                    b'#!/usr/bin/env -S bash -e\n', b'#!/bin/bash -e -u\n',
                                    b'#!"unterminated\n', b'#!\xff\n'])
def test_shared_shebang_parser_refuses_unsupported_forms(header):
    from rvw.common.capture import CaptureError
    from rvw.common.interpreter import script_interpreter
    with pytest.raises(CaptureError, match='unsupported shebang'):
        script_interpreter(header)
