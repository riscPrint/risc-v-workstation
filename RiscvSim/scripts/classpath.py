#!/usr/bin/env python3
"""Compile external adapters once; invalidate for source or classpath edits."""
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys

EXCLUDE = {'target', '.git', '.venv', 'out', 'run', 'simWorkspace', 'node_modules', '__pycache__'}


def digest(paths):
    h = hashlib.sha256()
    for root in paths:
        root = Path(root)
        if not root.exists():
            h.update(f'missing:{root}'.encode())
            continue
        entries = []
        if root.is_dir():
            for directory, dirs, files in os.walk(root):
                dirs[:] = sorted(d for d in dirs if d not in EXCLUDE)
                entries.extend(Path(directory) / f for f in sorted(files))
        else:
            entries = [root]
        for p in entries:
            h.update(str(p).encode())
            h.update(p.read_bytes())
    return h.hexdigest()


def classpath(here, core, repo, lock):
    roots = [core / 'src', core / 'project', core / 'build.sbt', here / 'src', here / 'project', here / 'build.sbt']
    for library in ('RiscvSim', 'SpinalChecks', 'SpinalDB/spinaldb', 'SpinalProbes', 'SpinalTrace/spinaltrace', 'SpinalWaves/spinalwaves'):
        base = repo / library
        roots += [base / 'src', base / 'project', base / 'build.sbt']
    key = digest(roots)
    key += json.dumps({k: v for k, v in os.environ.items() if k.startswith(('SBT_', 'COURSIER_', 'JAVA_', 'JDK_')) or k in ('RVW_HOME', 'RVW_CORE_SOURCE', 'PATH', 'HOME', 'JVM_OPTS', '_JAVA_OPTIONS')}, sort_keys=True)
    state = here / 'target/rvw-classpath.json'
    try:
        cached = json.loads(state.read_text())
        if cached['key'] == key and all(Path(p).exists() for p in cached['cp'].split(os.pathsep)) and cached['runtime'] == digest(cached['cp'].split(os.pathsep)):
            return cached['cp']
    except (OSError, ValueError, KeyError):
        pass
    process = subprocess.Popen([str(repo / 'scripts/with-lock.sh'), lock, 'nice', '-n', '10', 'sbt', '-J-Xmx3g', '-batch', 'root/compile', 'export root/Runtime/fullClasspath'], cwd=here, stdout=subprocess.PIPE, text=True)
    output = []
    for line in process.stdout:
        print(line, file=sys.stderr, end='', flush=True)
        output.append(line)
    if process.wait():
        raise RuntimeError('sbt compilation failed')
    candidates = [line.strip() for line in ''.join(output).splitlines() if not line.startswith('[') and 'scala-library' in line]
    if not candidates:
        raise RuntimeError('No classpath in sbt output')
    cp = candidates[-1]
    if not all(Path(p).exists() for p in cp.split(os.pathsep)):
        raise RuntimeError('Classpath contains missing entries')
    state.parent.mkdir(parents=True, exist_ok=True)
    state.write_text(json.dumps(dict(key=key, cp=cp, runtime=digest(cp.split(os.pathsep)))))
    return cp


if __name__ == '__main__':
    try:
        print(classpath(*map(Path, sys.argv[1:4]), sys.argv[4]))
    except (OSError, RuntimeError) as exc:
        print(str(exc), file=sys.stderr)
        sys.exit(2)
