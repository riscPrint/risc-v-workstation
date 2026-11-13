"""Identity and build command for project-owned Verilator C1 harnesses.

The manifest is the single source of build arguments. Preprocessing includes
transitive HDL includes. The regression input collector owns native tool capture.
"""
from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import sys

from rvw.common.proc import run_group
from rvw.regress.source import describe


def native_identity():
    path = Path(__file__).resolve().parents[4] / 'RiscvSim/scripts/native-identity.py'
    spec = importlib.util.spec_from_file_location('rvw_hdl_native_identity', path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.collect(include_java=False)


def digest(value):
    return hashlib.sha256(value).hexdigest()


def collect(manifest, *, preprocess=None):
    manifest = Path(manifest).resolve()
    root = manifest.parent.parent
    spec = json.loads(manifest.read_text())
    sources = [str(root / p) for p in spec['sources']]
    harness = [root / p for p in spec['harness_sources']]
    includes = ['-I' + str(root / p) for p in spec.get('include_dirs', [])]
    defines = ['-D' + p for p in spec.get('defines', [])]
    flags = spec.get('verilator_flags', [])
    args = ['verilator', *flags, '--top-module', spec['top'], *includes, *defines, *sources]
    if preprocess is None:
        result = run_group([*args, '-E'], cwd=root, capture=True, timeout=60)
        if result.returncode or result.timed_out:
            raise ValueError('Verilator preprocessing failed: ' + (result.stderr or ''))
        preprocessed = result.stdout.encode()
    else:
        preprocessed = preprocess(args)
    # Include manifest, ordered source bytes, harness bytes, and included RTL.
    inputs = {str(p.relative_to(root)) if p.is_relative_to(root) else str(p): digest(p.read_bytes())
              for p in [manifest, *map(Path, sources), *harness]}
    native = native_identity()
    rtl = digest(preprocessed)
    model = digest(json.dumps(dict(inputs=inputs, rtl=rtl, spec=spec, native=native['sha256']), sort_keys=True).encode())
    source = (json.loads(os.environ['RVW_CAPTURE_SOURCE']) if os.environ.get('RVW_CAPTURE_SOURCE')
              else describe(root).to_dict())
    tools_root = Path(__file__).resolve().parents[4]
    rev = run_group(['git', 'rev-parse', 'HEAD'], cwd=tools_root, capture=True, timeout=10)
    state = run_group(['git', 'status', '--porcelain', '--untracked-files=normal', '--',
                       'rvw/src', 'RiscvSim/scripts'], cwd=tools_root, capture=True, timeout=10)
    if rev.returncode or state.returncode:
        raise ValueError('cannot identify installed HDL adapter code')
    source.update(tools_repo=str(tools_root), tools_rev=rev.stdout.strip(),
                  tools_dirty=bool(state.stdout.strip()))
    claims = {'rtl_sha256': rtl, 'tools.hdl_model_sha256': model,
              'tools.native_build.sha256': native['sha256'],
              'source.tools_rev': source['tools_rev'], 'source.tools_dirty': source['tools_dirty']}
    document = dict(schema='rvw.adapter-capture/2', complete=native['cache_enabled'], source=source,
                    result_claims=claims, inputs=inputs, manifest=spec, native_build=native)
    command = [*args, '--cc', '--exe', '--build', '-MAKEFLAGS', '-B', '-Mdir', str(root / spec['build_dir']),
               *map(str, harness), '-o', 'sim']
    return document, command


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('manifest')
    parser.add_argument('action', choices=['identity', 'build'])
    parser.add_argument('--config', default='default')
    parser.add_argument('--options')
    args, extra = parser.parse_known_args()
    try:
        if args.config != 'default':
            raise ValueError('unknown config: ' + args.config)
        document, command = collect(args.manifest)
        if args.action == 'build':
            spec = document['manifest']
            root = Path(args.manifest).resolve().parent.parent
            (root / spec['build_dir']).mkdir(parents=True, exist_ok=True)
            result = run_group(command, cwd=root, capture=True, timeout=120)
            print(result.stdout or '', file=sys.stderr)
            print(result.stderr or '', file=sys.stderr)
            if result.returncode or result.timed_out:
                return 2
            (root / spec['build_dir'] / 'identity.json').write_text(json.dumps(document))
            document = dict(schema='rvw.build/1', status='built',
                            model=str(root / spec['build_dir'] / 'sim'), identity=document)
        print(json.dumps(document, sort_keys=True))
        return 0
    except (OSError, ValueError, KeyError) as exc:
        print(str(exc), file=sys.stderr)
        return 2


if __name__ == '__main__':
    sys.exit(main())
