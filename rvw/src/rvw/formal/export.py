"""Export a selected module from committed project sources through query.build."""
from __future__ import annotations

import json
import os
from pathlib import Path
import subprocess
import tarfile
import time
import sys

from rvw.common import lock
from rvw.common.proc import run_group
from rvw.common.project import load_project
from rvw.regress.config import load_config
from . import common


def git(repo, *args):
    try:
        return subprocess.check_output(['git', '-C', str(repo), *args], text=True, stderr=subprocess.PIPE).strip()
    except subprocess.CalledProcessError as exc:
        raise ValueError(f'git revision/export input failed: {exc.stderr.strip()}') from exc


def export_revision(project_path, revision, config, top, out, timeout):
    """Build an archived revision, then let Yosys select its hierarchy.

    The project owns query.build and its generator dependencies. This does not
    infer dependencies from a cached JVM classpath.
    """
    deadline = time.monotonic() + timeout
    def budget():
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            raise TimeoutError("revision export time limit")
        return remaining
    project = load_project(project_path)
    if project is None or not project.get('query', 'build'):
        raise ValueError('revision export requires project query.build')
    core = load_config(project=project.path)
    if not core.source_repo or not core.source_env:
        raise ValueError('revision export requires core.source_repo and source_env')
    dependencies = project.get('formal', 'export_dependencies', [])
    if not dependencies:
        raise ValueError('declare formal.export_dependencies (generator repositories)')
    records = []
    for repo in dependencies:
        root = Path(git(repo, 'rev-parse', '--show-toplevel'))
        if git(root, 'status', '--porcelain', '--untracked-files=normal'):
            raise ValueError(f'generator repository must be clean: {root}')
        records.append({'repository': str(root), 'revision': git(root, 'rev-parse', 'HEAD')})
    commit = git(core.source_repo, 'rev-parse', '--verify', revision + '^{commit}')
    common.check_ident('module', top)
    out = Path(out).resolve()
    out.mkdir(parents=True, exist_ok=False)
    # Keep the source snapshot and generated RTL for reproduction and inspection.
    archive = out / 'source.tar'
    with archive.open('wb') as stream:
        subprocess.run(['git', '-C', str(core.source_repo), 'archive', commit], stdout=stream, check=True)
    source = out / 'source'
    source.mkdir()
    with tarfile.open(archive) as bundle:
        bundle.extractall(source, filter='data')
    archive.unlink()
    rtl = out / 'rtl'
    env = os.environ.copy()
    env[core.source_env] = str(source)
    command = [*project.get('query', 'build'), config or core.default_config,
               str(out / 'design.db'), '--rtl', str(rtl), '--no-pdg', '--no-blocks', '--no-hgldd']
    launch = command
    if core.lock:
        # Keep lock acquisition inside the cancellable process-group budget.
        launch = [sys.executable, '-I', lock.__file__, core.lock, *command]
        if core.lock_dir:
            env['RVW_LOCK_DIR'] = str(core.lock_dir)
    with (out / 'build.log').open('w') as log:
        process = run_group(launch, cwd=project.root, env=env, stdout=log, stderr=log, timeout=budget())
    if process.returncode:
        raise ValueError(f'revision build failed ({process.returncode}); see {out}/build.log')
    files = sorted([*rtl.rglob('*.v'), *rtl.rglob('*.sv')])
    if not files:
        raise ValueError('project build produced no Verilog')
    # Quote paths for the Yosys parser, independently of shell quoting.
    script = '\n'.join('read_verilog -sv ' + json.dumps(str(p)) for p in files)
    script += f'\nhierarchy -check -top {top}\nproc\n'
    script += f'write_verilog -noattr {json.dumps(str(out / "module.v"))}\n'
    (out / 'select.ys').write_text(script)
    with (out / 'select.log').open('w') as log:
        process = run_group(['yosys', '-Q', '-s', str(out / 'select.ys')], stdout=log, stderr=log, timeout=budget())
    if process.returncode:
        raise ValueError(f'module selection failed ({process.returncode}); see {out}/select.log')
    from .snapshot import digest
    record = {'revision': commit, 'module': top, 'config': config or core.default_config,
              'generator_dependencies': records, 'command': command,
              'rtl': [{'path': str(p.relative_to(out)), 'sha256': digest(p)} for p in files],
              'module_sha256': digest(out / 'module.v'), 'lock': core.lock}
    (out / 'export.json').write_text(json.dumps(record, indent=2) + '\n')
    return out / 'module.v', record
