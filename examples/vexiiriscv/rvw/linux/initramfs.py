"""Write a minimal newc archive with a static init and a console node."""
import argparse
from pathlib import Path
import stat


def archive(init: bytes) -> bytes:
    result = bytearray()
    def entry(name, mode, data=b'', major=0, minor=0):
        name = name.encode() + b'\0'
        fields = [1, mode, 0, 0, 1, 0, len(data), 0, 0, major, minor, len(name), 0]
        result.extend(b'070701' + ''.join(f'{v:08x}' for v in fields).encode())
        result.extend(name)
        result.extend(b'\0' * (-len(result) % 4))
        result.extend(data)
        result.extend(b'\0' * (-len(result) % 4))
    entry('dev', stat.S_IFDIR | 0o755)
    entry('dev/console', stat.S_IFCHR | 0o600, major=5, minor=1)
    entry('init', stat.S_IFREG | 0o755, init)
    entry('TRAILER!!!', 0)
    return bytes(result)


if __name__ == '__main__':
    p = argparse.ArgumentParser(__doc__)
    p.add_argument('init', type=Path)
    p.add_argument('out', type=Path)
    args = p.parse_args()
    args.out.write_bytes(archive(args.init.read_bytes()))
