"""Identify the declared input files that option values name. Execution uses the values unchanged."""
import os
import re
from pathlib import Path

from rvw.common.capture import CaptureError

SEPARATORS = r'''\s'";:,\[\]{}()'''


def is_git(path, capture):
    from rvw.common.capture import run_git
    from rvw.common.proc import run_group
    tool = capture.tool('git')
    result = run_git(path, 'rev-parse', '--show-toplevel', tool=tool.path, run=run_group)
    return result.returncode == 0 and not result.timed_out


def _identity(item):
    if hasattr(item, 'files'):
        return {'files': {entry.copy.relative_to(item.copy).as_posix():
                          {'sha256': entry.sha256, 'size': entry.size, 'executable': entry.executable}
                          for entry in item.files},
                'directories': sorted(item.directories)}
    return {'sha256': item.sha256, 'size': item.size, 'executable': item.executable}


class OptionInputs:
    """Paths below declared roots that option values name, captured once on first use.

    A changed stimulus file must change the job identity, even when the option string is
    the same. Any other path-like value is refused: its content cannot be identified.
    """

    def __init__(self, capture, roots, cwd=None):
        self.capture = capture
        self.cwd = cwd or Path.cwd()
        self.roots = list(dict.fromkeys(Path(r).absolute() for r in roots if r is not None))
        self.items = {}

    def identities(self, value, *, strict=True):
        paths = set()
        self._walk(value, paths, strict)
        return {str(path): _identity(self.items[path]) for path in sorted(paths)}

    def _capture(self, path):
        if path not in self.items:
            if not any(path == root or path.is_relative_to(root) for root in self.roots):
                return False
            if not path.is_file() and not path.is_dir():
                return False
            self.items[path] = (self.capture.tree(path, git=is_git(path, self.capture))
                                if path.is_dir() else self.capture.file(path))
        return True

    def _walk(self, value, paths, strict):
        if isinstance(value, dict):
            for item in value.values():
                self._walk(item, paths, strict)
            return
        if isinstance(value, (list, tuple)):
            for item in value:
                self._walk(item, paths, strict)
            return
        if not isinstance(value, str):
            return
        if '\x00' in value:
            raise CaptureError('input_not_captured:option_path', 'NUL in a path value')
        aliases = {}
        for root in self.roots:
            aliases[str(root)] = root
            relative = os.path.relpath(root, self.cwd)
            aliases[relative] = root
            if not relative.startswith('../'):
                aliases['./' + relative] = root
        rest = value
        if aliases:
            names = '|'.join(re.escape(name) for name in sorted(aliases, key=len, reverse=True))
            pattern = re.compile(r'(?<![\w./-])(?P<root>' + names + r')(?=$|[/' + SEPARATORS
                                 + r'])(?P<suffix>(?:/[^' + SEPARATORS + r']*)?)')

            def replace(match):
                path = aliases[match['root']]
                if match['suffix']:
                    path = path / match['suffix'].lstrip('/')
                if '..' in path.parts or not self._capture(path):
                    raise CaptureError('input_not_captured:option_path', match.group())
                paths.add(path)
                return '\x00'

            rest = pattern.sub(replace, value)
        if strict:
            # Bare scalar names stay values unless they name a live filesystem entry. Check the
            # full value and a flag payload too: a relative file name can contain spaces.
            full_values = [rest, rest.partition('=')[2]] if '=' in rest else [rest]
            for word in [*full_values, *re.split('[' + SEPARATORS + '=]+', rest)]:
                if not word or '\x00' in word:
                    continue
                try:
                    exists = (self.cwd / word).exists()
                except OSError as exc:
                    raise CaptureError('input_not_captured:option_path', word) from exc
                if '/' in word or exists:
                    raise CaptureError('input_not_captured:option_path', word)
