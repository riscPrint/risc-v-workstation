"""Project-declared Spike extension libraries, loaded only from captured copies."""
import ctypes
from pathlib import Path


def validate_extensions(items):
    if not isinstance(items, list):
        raise ValueError('reference_extensions must be a list')
    names = set()
    for item in items:
        if not isinstance(item, dict) or set(item) != {'library', 'name'}:
            raise ValueError('reference extension requires library and name')
        if not all(isinstance(item[k], str) and item[k] for k in item):
            raise ValueError('reference extension paths and names must be nonempty strings')
        if item['name'] in names:
            raise ValueError('duplicate reference extension name')
        names.add(item['name'])
    return items


def capture_extensions(items, capture, platform_path):
    result = []
    for item in validate_extensions(items):
        path = Path(item['library'])
        if not path.is_absolute():
            path = Path(platform_path).resolve().parent / path
        library = capture.file(path)
        result.append(dict(name=item['name'], library=str(library.copy)))
    return result


def load_extensions(items):
    # Hold these handles for the lifetime of the reference. C++ factories live here.
    return [ctypes.CDLL(item['library'], mode=ctypes.RTLD_GLOBAL)
            for item in validate_extensions(items)]
