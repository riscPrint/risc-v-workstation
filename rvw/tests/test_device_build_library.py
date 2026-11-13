import importlib.util
from pathlib import Path
import pytest

pytestmark = pytest.mark.fast


def helper():
    path = Path(__file__).parents[2] / 'RiscvSim/scripts/build-devices.py'
    spec = importlib.util.spec_from_file_location('device_build', path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.mark.parametrize('framework', [False, True])
def test_python_shared_library_layout(tmp_path, framework):
    config = {'LIBDIR': str(tmp_path / 'lib'), 'LDLIBRARY': 'libpython.so'}
    expected = tmp_path / 'lib/libpython.so'
    if framework:
        config.update(LDLIBRARY='Python.framework/Versions/3.15/Python',
                      PYTHONFRAMEWORKPREFIX=str(tmp_path / 'Frameworks'))
        expected = tmp_path / 'Frameworks/Python.framework/Versions/3.15/Python'
    expected.parent.mkdir(parents=True)
    expected.write_bytes(b'fixture')
    assert helper().python_library(config.get) == expected


def test_missing_python_library_is_refused(tmp_path):
    with pytest.raises(ValueError, match='shared CPython library required'):
        helper().python_library({'LIBDIR': str(tmp_path), 'LDLIBRARY': 'missing'}.get)


@pytest.mark.parametrize('name', ['libpython3.13.dylib', 'Python'])
def test_python_linked_name(tmp_path, name):
    library = tmp_path / name
    listing = f'plugin.so:\n\t@rpath/{name} (compatibility version 1.0.0)\n\t/usr/lib/libSystem.B.dylib (compatibility version 1.0.0)\n'
    assert helper().python_load_name(listing, library) == '@rpath/' + name


def test_python_linked_name_missing(tmp_path):
    with pytest.raises(ValueError, match='Python library is absent'):
        helper().python_load_name('plugin.so:\n', tmp_path/'Python')
