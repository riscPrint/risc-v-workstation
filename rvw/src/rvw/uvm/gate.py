"""Bind a pure SV UVM build to an existing C4 build-suite adapter.

The existing regression runner owns source, interpreter and tool capture.
This bridge binds declared native dependencies and refuses a different source image.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import sys
import tempfile
from . import flow
from rvw.sim.uvm import sha


def identity(build_dir, source_root, selected_root, seeds):
    build_dir,source_root,selected_root=map(lambda p:Path(p).resolve(),(build_dir,source_root,selected_root))
    built=json.loads((build_dir/'build.json').read_text())
    manifest=built['manifest']
    if built['status']!='pass' or not built.get('binary_sha256'):
        raise ValueError('UVM build did not pass')
    custom = manifest.get('build_args') or any(Path(p).suffix.lower() not in ('.sv','.v') for p in manifest['sources'])
    native = built.get('native_dependency_sha256', {})
    if custom and not native:
        raise ValueError('C4 bridge supports pure SV or explicit native dependencies')
    from .native_inputs import verify
    verify(native)
    if not seeds or any(type(s) is not int or not 1<=s<2**31 for s in seeds) or len(set(seeds))!=len(seeds):
        raise ValueError('unique positive seeds required')
    if sha(build_dir/'obj/simulation')!=built['binary_sha256']:
        raise ValueError('UVM binary changed')
    bound={}
    for original,digest in built['input_sha256'].items():
        path=Path(original).resolve()
        if not path.is_relative_to(source_root):
            if native.get(str(path)) == digest:
                continue
            raise ValueError('every UVM source input must be in source_repo or a declared native dependency: '+str(path))
        relative=path.relative_to(source_root)
        if sha(path)!=digest or sha(selected_root/relative)!=digest:
            raise ValueError('UVM build does not match selected source: '+str(relative))
        bound[str(relative)]=digest
    for original, digest in native.items():
        path=Path(original)
        if path.is_relative_to(source_root):
            relative=path.relative_to(source_root)
            if sha(selected_root/relative)!=digest:
                raise ValueError('native dependency does not match selected source: '+str(relative))
            bound[str(relative)]=digest
    payload=dict(build=built,inputs=bound,binary_sha256=built['binary_sha256'],
        tests=manifest['tests'],seeds=seeds,uvm_commit=built['uvm_commit'],
        uvm_archive_sha256=built['uvm_archive_sha256'])
    digest=hashlib.sha256(json.dumps(payload,sort_keys=True).encode()).hexdigest()
    return digest,built


def configure(build_dir, source_repo, out, *, seeds=(1,3)):
    build_dir,source_repo,out=map(lambda p:Path(p).resolve(),(build_dir,source_repo,out))
    seeds=list(seeds)
    digest,built=identity(build_dir,source_repo,source_repo,seeds)
    module=Path(__file__).resolve()
    package=module.parents[1]
    adapter=module.with_name('gate_adapter.py')
    paths=[package,build_dir/'build.json',build_dir/'obj/simulation',
           *map(Path,built['input_sha256']), *map(Path,built.get('native_dependency_sha256', {}))]
    # Capture all generated library bytes as well as the binary and source inputs.
    if (build_dir/'library').is_dir(): paths.append(build_dir/'library')
    q=json.dumps
    text='\n'.join([
      '[core]', 'name = '+q(built['manifest']['name']),
      'adapter = '+q([sys.executable,str(adapter),str(build_dir),str(source_repo),json.dumps(seeds)]),
      'source_repo = '+q(str(source_repo)), 'source_env = "RVW_UVM_SOURCE"',
      'configs = ["uvm"]', 'default_config = "uvm"',
      'identity = true', 'identity_capture = true', 'input_complete = true',
      'build_first = false', 'jobs = 1',
      'cache_paths = '+q(list(dict.fromkeys(map(str,paths)))),
      '[suites.uvm]', 'kind = "build"', 'configs = ["uvm"]', 'timeout_s = 300',
      '[tiers.quick]', 'runs = [{suite = "uvm"}]', ''])
    with out.open('x') as f: f.write(text)
    return dict(config=str(out),uvm_identity_sha256=digest,tests=built['manifest']['tests'],seeds=seeds)


def adapter_main(argv=None):
    p=argparse.ArgumentParser()
    p.add_argument('build_dir',type=Path);p.add_argument('source_root',type=Path)
    p.add_argument('seeds');p.add_argument('action',choices=['identity','build'])
    p.add_argument('--config',default='uvm');p.add_argument('--options');p.add_argument('--json',action='store_true')
    a=p.parse_args(argv)
    try:
        if a.config!='uvm': raise ValueError('unsupported UVM config')
        source=json.loads(os.environ['RVW_CAPTURE_SOURCE'])
        seeds=json.loads(a.seeds)
        digest,built=identity(a.build_dir,a.source_root,os.environ['RVW_UVM_SOURCE'],seeds)
        if a.action=='identity':
            report=dict(schema='rvw.adapter-capture/2',complete=True,source=source,
                result_claims={'build.uvm_identity_sha256':digest})
        else:
            out=Path(tempfile.mkdtemp(prefix='rvw-uvm-gate-'))/'regression'
            regression=flow.regress(a.build_dir,out,seeds=seeds,timeout=120)
            if not regression['tests'] or any(t['status']!='pass' for t in regression['tests']):
                raise ValueError('UVM regression failed: '+str(out/'results.json'))
            report=dict(core=built['manifest']['name'],config='uvm',
                uvm_identity_sha256=digest,results=str(out/'results.json'),tests=regression['tests'])
        print(json.dumps(report));return 0
    except (OSError,ValueError,KeyError) as exc:
        print(str(exc),file=sys.stderr);return 2
