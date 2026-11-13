#!/usr/bin/env python3
"""Reuse a completed private sbt classpath only while source and bytecode match."""
import argparse
import hashlib
import json
import os
from pathlib import Path

SKIP = {'.git', '.venv', 'target', 'out', 'simWorkspace', 'node_modules', '__pycache__'}
SOURCE = {'.scala', '.java', '.sbt', '.properties', '.sh', '.py'}


def digest(paths):
    h = hashlib.sha256()
    for path in sorted(set(paths)):
        h.update(str(path.absolute()).encode() + b'\0')
        with path.open('rb') as stream:
            for chunk in iter(lambda: stream.read(1024 * 1024), b''):
                h.update(chunk)
        h.update(b'\0')
    return h.hexdigest()


def files(root, sources=False):
    for directory, children, names in os.walk(root):
        if sources:
            children[:] = [name for name in children if name not in SKIP]
        for name in names:
            path = Path(directory) / name
            if path.is_file() and (not sources or path.suffix in SOURCE or '/src/main/resources/' in path.as_posix()):
                yield path


def sources(roots):
    return digest(path for root in roots for path in files(Path(root).resolve(), True))


def runtime(classpath):
    paths = []
    for entry in classpath.split(os.pathsep):
        path = Path(entry)
        if path.is_file():
            paths.append(path)
        elif path.is_dir():
            paths.extend(files(path))
        else:
            raise ValueError('missing classpath entry: ' + entry)
    return digest(paths)


def load(cache, roots):
    data = json.loads(Path(cache).read_text())
    if data['sources'] != sources(roots) or data['runtime'] != runtime(data['classpath']):
        raise ValueError('classpath inputs changed')
    return data['classpath']


def save(cache, roots, before, classpath):
    after = sources(roots)
    if before != after:
        raise ValueError('sources changed during compilation')
    data = dict(sources=after, runtime=runtime(classpath), classpath=classpath)
    path = Path(cache)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data) + '\n')


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('action', choices=['sources', 'load', 'save'])
    p.add_argument('--root', action='append', required=True)
    p.add_argument('--cache', type=Path)
    p.add_argument('--before')
    p.add_argument('--classpath')
    a = p.parse_args()
    try:
        if a.action == 'sources':
            print(sources(a.root))
        elif a.action == 'load':
            print(load(a.cache, a.root))
        else:
            save(a.cache, a.root, a.before, a.classpath)
    except (OSError, ValueError, KeyError):
        return 1
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
