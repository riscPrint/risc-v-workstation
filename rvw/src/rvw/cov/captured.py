"""Command-scoped C8 captures shared by coverage readers and proof checks."""
from contextvars import ContextVar
from functools import wraps
from pathlib import Path
from tempfile import TemporaryDirectory

from rvw.common.capture import Capture

_ACTIVE = ContextVar('coverage_capture', default=None)


def current():
    capture = _ACTIVE.get()
    if capture is None:
        raise RuntimeError('coverage read has no command capture')
    return capture


def command(function):
    @wraps(function)
    def call(*args, **kwargs):
        if _ACTIVE.get() is not None:
            return function(*args, **kwargs)
        with TemporaryDirectory(prefix='rvw-cov-') as directory:
            capture = Capture(Path(directory) / 'inputs')
            token = _ACTIVE.set(capture)
            environment()
            try:
                result = function(*args, **kwargs)
                verify_tools()
                if isinstance(result, dict) and 'schema' in result:
                    result.setdefault('capture', capture.record())
                    result['cache_key'] = None  # No assertion of external tool dependency closure.
                return result
            finally:
                _ACTIVE.reset(token)
    return call


def file(path):
    capture = current()
    aliases = getattr(capture, '_coverage_aliases', {})
    return aliases.get(str(Path(path).absolute())) or capture.file(Path(path))


def read_bytes(path):
    return file(path).copy.read_bytes()


def read_text(path, **kwargs):
    return file(path).copy.read_text(**kwargs)


def sha256(path):
    return file(path).sha256


def record(item, opened=None):
    """Keep the /7 lookup record shape, with identity from Captured only."""
    return {'opened': str(opened if opened is not None else item.source),
            'links': [list(link) for link in item.symlinks],
            'resolved': item.resolved, 'sha256': item.sha256}


def persistent(function):
    """Proof evidence retains its raw captures for the /7 reader."""
    @wraps(function)
    def call(config_path, database_path, out, timeout=60):
        out = Path(out).absolute()
        if out.exists():
            raise FileExistsError(f'{out}: proof output must be a fresh directory')
        from .proof import check_script_paths
        check_script_paths([], out)
        out.mkdir(parents=True, exist_ok=False)
        capture = Capture(out / 'input-capture')
        token = _ACTIVE.set(capture)
        environment()
        try:
            return function(config_path, database_path, out, timeout)
        except BaseException:
            if not (out / 'source-snapshot').exists():
                import shutil
                shutil.rmtree(out)
            raise
        finally:
            _ACTIVE.reset(token)
    return call


def tool(name):
    return current().tool(name, identity_only=name == 'mcy')


def verify_tools():
    current().verify_tools()


def seed(items):
    aliases = getattr(current(), '_coverage_aliases', {})
    for item in items:
        aliases.setdefault(item.resolved, item)
    current()._coverage_aliases = aliases


def environment():
    """Use only this saved environment for coverage-owned subprocesses."""
    names = ('PATH', 'HOME', 'TMPDIR', 'TMP', 'TEMP', 'LANG', 'LC_ALL',
             'PYTHONPATH', 'PYTHONHOME', 'YOSYS_DATDIR', 'LD_LIBRARY_PATH',
             'DYLD_LIBRARY_PATH', 'SYSTEMROOT')
    return {key: value for key, value in current().env(*names).items() if value is not None}
