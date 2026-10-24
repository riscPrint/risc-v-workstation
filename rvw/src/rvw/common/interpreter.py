"""Bind installed interpreters without losing Python virtual environments."""
import json
import os
from pathlib import Path
import shutil
import shlex

from .capture import CaptureError
from .proc import run_group


def script_interpreter(header: bytes) -> list[str]:
    """Parse a shebang. Refuse env options and extra direct-interpreter words."""
    if not header.startswith(b'#!'):
        return []
    try:
        words = shlex.split(header.splitlines()[0][2:].decode())
    except (ValueError, UnicodeError) as exc:
        raise CaptureError('input_not_captured:interpreter', 'unsupported shebang') from exc
    if words and Path(words[0]).name == 'env':
        words = words[1:]
        supported = len(words) == 1
    else:
        supported = len(words) <= 2
    if not supported or not words or words[0].startswith('-') or '=' in words[0]:
        raise CaptureError('input_not_captured:interpreter', 'unsupported shebang')
    return words


def bind_interpreter(capture, name, *, environments, env, guard, run=run_group):
    """Record Python venv config and packages, and preserve its lookup path."""
    selected = shutil.which(str(name), path=env.get('PATH', os.defpath))
    if selected is None:
        raise CaptureError('input_not_captured:interpreter', str(name))
    selected = Path(selected).absolute()
    tool = capture.tool(selected)
    config = selected.parent.parent / 'pyvenv.cfg'
    if not selected.name.startswith('python') or not config.is_file():
        return tool.path
    # One interpreter can serve rvw and an adapter with different import paths.
    # Do not reuse the server's package inventory for that child environment.
    key = (str(selected), tuple(sorted(env.items())))
    if key not in environments:
        descriptor = capture.file(config)
        guard(descriptor)
        result = run([str(selected), '-c',
            'import importlib.metadata as m, json; '
            'print(json.dumps(sorted([[d.metadata["Name"], d.version] '
            'for d in m.distributions()])))'],
            env=env, capture=True, timeout=30)
        try:
            packages = json.loads(result.stdout)
            if result.returncode or result.timed_out or not isinstance(packages, list) or any(
                    not isinstance(p, list) or len(p) != 2
                    or not all(isinstance(v, str) for v in p) for p in packages):
                raise ValueError('incomplete package inventory')
        except (TypeError, ValueError) as exc:
            raise CaptureError('input_not_captured:python_environment', str(selected)) from exc
        environments[key] = {
            'path': str(selected), 'config_sha256': descriptor.sha256, 'packages': packages}
    return selected
