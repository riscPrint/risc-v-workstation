"""C8 command inputs for debug runs and stable replay programs."""
from __future__ import annotations

import json
import os
from pathlib import Path
import re
import shutil
import sys
import uuid

from rvw.common.capture import Capture, CaptureError, _resolve, _stamp
from rvw.common.interpreter import bind_interpreter, script_interpreter
from rvw.results.generation import publish
from rvw.wave.capture import WaveInputs
from .result import Run, tools_root


def new_capture() -> Capture:
    # Retain these private inputs for saved replays. Staging must not sit beneath
    # the requested output, which can be an input checkout or a read-only archive.
    root = Path.home() / '.cache' / 'rvw' / 'debug-inputs'
    root.mkdir(parents=True, exist_ok=True, mode=0o700)
    return Capture(root / f'inputs-{uuid.uuid4().hex}' / 'capture')


def snapshot_elf(run: Run, out: Path, capture: Capture | None = None, *, root=None) -> Path:
    """Capture the program once and verify those bytes against its recorded C1 identity."""
    expected = run.get('elf_sha256')
    if not isinstance(expected, str) or not re.fullmatch(r'[0-9a-fA-F]{64}', expected):
        raise ValueError(f'{run.dir}: a recorded elf_sha256 is required to verify the ELF; re-run the test')
    name = run.get('elf')
    if not isinstance(name, str) or not name:
        raise ValueError(f'{run.dir}: no recorded ELF path')
    src = Path(name)
    if not src.is_absolute():
        src = (root or tools_root()) / src
    capture = capture or new_capture()
    item = capture.file(src)
    if item.sha256 != expected.lower():
        raise ValueError(f'{run.dir}: ELF sha256 mismatch for {item.source}: recorded {expected}, copied '
                         f'{item.sha256}; restore the recorded ELF or re-run the test')
    if run.capture is capture:
        return item.copy
    # Compatibility API: content-addressed path keeps existing replay users stable.
    out.mkdir(parents=True, exist_ok=True)
    saved = out / f'input-{item.sha256}.elf'
    try:
        os.link(item.copy, saved)  # Publish the complete captured bytes atomically.
    except FileExistsError:
        if saved.is_symlink() or not saved.is_file() or saved.read_bytes() != item.copy.read_bytes():
            raise ValueError(f'{saved}: saved ELF sha256 mismatch or not a regular file') from None
    return saved.resolve()


class DebugInputs(WaveInputs):
    def __init__(self):
        super().__init__(new_capture())
        # Freeze the whole inherited environment. Caches remain disabled because arbitrary
        # adapters can have undeclared dependencies. Lock descriptors are supplied at execution.
        self.environment = dict(os.environ)
        names = {'PATH', 'HOME', 'JAVA_HOME', 'RISCV_OBJDUMP', 'SPINALTRACE_CLI', 'RVW_CORE_CONFIG',
                 'RVW_ROOT', 'RVW_NO_LOCK', 'RVW_NO_RUN_MANY', 'COURSIER_CACHE', 'SBT_OPTS', 'JAVA_OPTS'}
        names.update(key for key in os.environ if key.startswith(('SPINAL_', 'RISCVSIM_', 'FAKE_')))
        self.saved_env = self.capture.env(*sorted(names))
        self.root = tools_root()
        self.source = None
        self.source_revision = None
        self.tools_tree = None
        self.python_tree = None
        self.tree_stamps = {}
        self.launcher_descriptors = {}
        self.python_environments = {}
        self.interpreter_guards = []
        self.adapter_trees = {}
        self.adapter_registry = None
        self.adapter_registry_tree = None

    def interpreter(self, name, *, env=None):
        def guard(item):
            self.interpreter_guards.append((item.source, item.resolved, item.symlinks,
                                            self.capture._stamps[item.source]))
        return bind_interpreter(self.capture, name, environments=self.python_environments,
                                env=self.environment if env is None else env, guard=guard)

    def config(self, core, explicit=None, project=None):
        self.adapter_registry = None
        self.adapter_registry_tree = None
        from rvw.bundle import coreconf
        from rvw.common.project import load_project
        selected = explicit
        if selected is None:
            selected_project = load_project(project, capture=self.capture)
            if selected_project:
                if selected_project.name != core:
                    raise ValueError(f"project core {selected_project.name!r} differs from recorded core {core!r}")
                selected = selected_project.get("debug", "config")
                if selected is None:
                    raise ValueError(f"{selected_project.path}: missing debug.config")
        selected = selected or self.saved_env.get('RVW_CORE_CONFIG') or None
        if selected is None and core:
            candidate = self.root / 'RiscvSim' / core / 'debug.toml'
            selected = str(candidate) if candidate.exists() else None
        if selected is None:
            return {}, None
        cfg, path = coreconf.load(selected, capture=self.capture)
        registry = (cfg.get('core') or {}).get('adapter_versions')
        if registry:
            original = (path.parent / registry).resolve(strict=True)
            self.adapter_registry_tree = self.build_tree(original.parent, git=False)
            self.adapter_registry = self.adapter_registry_tree.copy / original.name
        return cfg, path

    def live_command(self, run):
        """Capture request bytes for the original live session, without a source checkout.

        The bundle separately requires the original session and RTL identity.
        No adapter executable or copied source tree is launched on this path.
        """
        from . import adapter
        import hashlib
        cmd = adapter.command_for(run, root=self.root)
        if cmd.sub != 'run':
            raise ValueError('live rerun requires a single-run command')
        cmd = cmd.set(elf=str(snapshot_elf(run, self.capture.root.parent, self.capture, root=self.root)))
        for name in ('boot_payloads', 'hart_images', 'fault'):
            if cmd.get(name) is not None:
                raise ValueError('live bundle does not capture this structured input: ' + name)
        if cmd.get('soc_map') is not None:
            original = run.artifact('soc_map')
            if original is None:
                raise ValueError('live bundle needs the captured simulation map')
            saved = self.file(original)
            expected = run.get('soc_map_sha256')
            if not expected or hashlib.sha256(saved.read_bytes()).hexdigest() != expected:
                raise ValueError('captured simulation map digest differs')
            cmd = cmd.set(soc_map=str(saved))
        cmd.inputs = self
        return cmd

    def command(self, run, cfg, *, source=True):
        from . import adapter
        cmd = adapter.command_for(run, root=self.root)
        cmd = cmd.set(elf=str(snapshot_elf(run, self.capture.root.parent, self.capture, root=self.root)))
        self.capture.env(*cmd.env, *cmd.unset)
        cmd.env = {**{key: value for key, value in self.saved_env.items()
                      if value is not None and key not in cmd.unset}, **cmd.env}
        cmd.environment = dict(self.environment)
        # A replay can carry a previous launcher's descriptor. This command owns
        # a new capture and must describe its own execution paths instead.
        for name in ('RVW_CAPTURE_INPUTS', 'RVW_CAPTURE_SOURCE'):
            cmd.env.pop(name, None)
            cmd.environment.pop(name, None)
        cmd.inputs = self
        if source:
            var = (cfg.get('core') or {}).get('source_env')
            if var:
                self.capture.env(var)
                if var not in cmd.env and var in self.environment:
                    cmd.env[var] = self.environment[var]
            src = (run.get('source') or {}).get('core_repo') or (cmd.env.get(var) if var else None)
            if src:
                if not var:
                    raise CaptureError('input_not_captured:core', 'core source_env is required')
                is_git = (Path(src) / '.git').exists()
                self.source_revision = self.capture.git_ref(Path(src), 'HEAD') if is_git else None
                self.source = self.build_tree(Path(src), git=is_git)
                cmd.env[var] = str(self.source.copy)
            elif var and any('RiscvSim' in Path(arg).parts for arg in cmd.exe):
                raise CaptureError('input_not_captured:core', 'core source is unavailable')
        return self.bind_adapter(cmd)

    def bind_adapter(self, cmd):
        """Freeze adapter scripts and pin their interpreter. Keep repo-relative support files."""
        root = self.root
        c = cmd.set()
        if c.environment is None:
            c.environment = dict(self.environment)
        # rvw and its lock helper use the worker's Python, independently of replay
        # assignments. Adapter executables and imports use the child environment.
        python = self.interpreter(sys.executable)
        c.env['RVW_PYTHON'] = c.env['RVW_LOCK_PYTHON'] = str(python)
        # Imports must not replace captured sibling __pycache__ files. The directories
        # stay writable for adapter build outputs, but captured input bytes stay fixed.
        c.env['PYTHONDONTWRITEBYTECODE'] = '1'
        c.unset = [key for key in c.unset if key not in ('RVW_PYTHON', 'RVW_LOCK_PYTHON')]
        c.exe = []
        for i, arg in enumerate(cmd.exe):
            if arg.startswith('-'):
                c.exe.append(arg)
                continue
            path = Path(arg)
            if not path.is_file():
                if i:
                    raise CaptureError('input_not_captured:adapter', f'unsupported executable argument: {arg}')
                selected = shutil.which(arg, path=c.child_environment().get('PATH', os.defpath))
                if selected is None:
                    raise CaptureError('input_not_captured:adapter', f'adapter not found: {arg}')
                path = Path(selected)
            if 'RiscvSim' in path.parts and path.is_relative_to(root):
                # The launcher reads sibling scripts and build sources. Preserve their layout.
                if self.tools_tree is None:
                    self.tools_tree = self.build_tree(root)
                c.exe.append(str(self.tools_tree.copy / path.relative_to(root)))
            else:
                saved = self.file(path)
                with saved.open('rb') as stream:
                    script = stream.read(2) == b'#!'
                if path.suffix == '.py' and path.is_relative_to(root / 'rvw'):
                    if self.python_tree is None:
                        self.python_tree = self.build_tree(root / 'rvw/src')
                    c.env['PYTHONPATH'] = str(self.python_tree.copy)
                if script or path.suffix in ('.py', '.sh'):
                    c.exe.append(str(self.adapter_script(path)))
                elif i == len(cmd.exe) - 1:
                    # C1 adapters need no --version interface, including native adapters.
                    c.exe.append(self.program(path))
                else:
                    c.exe.append(str(self.interpreter(path, env=c.child_environment())))
        # Pin shebang interpreters too, including /usr/bin/env python3.
        if c.exe:
            first = Path(c.exe[0])
            with first.open('rb') as stream:
                line = stream.readline(4096)
            if line.startswith(b'#!'):
                shebang = script_interpreter(line)
                interpreter = self.interpreter(shebang[0], env=c.child_environment())
                c.exe[:0] = [str(interpreter), *shebang[1:]]
        if self.source is not None:
            c = self.launcher_command(c, self.source, revision=self.source_revision)
        return c

    def adapter_script(self, path):
        """Use the captured source layout, or capture the adapter directory as its root."""
        path = path.absolute()
        trees = [self.source, self.tools_tree, self.python_tree, *self.adapter_trees.values()]
        for tree in trees:
            if tree is None:
                continue
            for root in (Path(tree.source).absolute(), Path(tree.resolved)):
                if path.is_relative_to(root):
                    saved = tree.copy / path.relative_to(root)
                    if not saved.is_file():
                        raise CaptureError('input_not_captured:adapter', f'not in captured tree: {path}')
                    return saved
        directory = path.parent
        # Respect Git's file list for a directory within a checkout. Plain directories
        # have no ignore rules. The directory is the adapter's dependency root.
        git = any((parent / '.git').exists() for parent in (directory, *directory.parents))
        tree = self.build_tree(directory, git=git)
        self.adapter_trees[directory] = tree
        saved = tree.copy / path.name
        if not saved.is_file():
            raise CaptureError('input_not_captured:adapter', f'not in captured tree: {path}')
        return saved

    def launcher_command(self, cmd, source, *, revision=None):
        """Bind the launcher's private source layout to hashes from the C8 copies.

        Bisect supplies a different source and pinned revision for each trial.
        Each descriptor is immutable and stays available to saved shell replays.
        """
        from .versions import resolve
        try:
            selected = resolve(source.copy, revision, manifest=self.adapter_registry)
        except (OSError, ValueError, KeyError, TypeError) as exc:
            c = cmd.set()
            c.env['RVW_ADAPTER_RESOLUTION_ERROR'] = str(exc)
            return c
        key = (source.copy, revision)
        if key not in self.launcher_descriptors:
            identity = {'core_repo': str(source.copy), 'core_rev': revision[:7] if revision else None,
                        'core_rev_full': revision, 'core_dirty': True,
                        'core_sha256': source.sha256, 'core_fingerprint': source.sha256}
            if selected is not None:
                identity['adapter_selection'] = selected[1]
            # Do not assert a clean Git tree: the captured set can include local edits.
            trees = [source, *([self.tools_tree] if self.tools_tree is not None else []),
                     *([self.adapter_registry_tree] if self.adapter_registry_tree is not None else [])]
            descriptor = {'source': identity, 'files': [
                {'path': str(item.copy), 'sha256': item.sha256}
                for tree in trees for item in tree.files]}
            generated = self.capture.root.parent / f'launcher-{uuid.uuid4().hex}.json'
            generated.write_text(json.dumps(descriptor, sort_keys=True) + '\n')
            item = self.capture.file(generated)
            self.tree_stamps[item.copy] = _stamp(item.copy.stat())
            self.launcher_descriptors[key] = (item.copy, identity)
        path, identity = self.launcher_descriptors[key]
        c = cmd.set()
        if selected is not None:
            c.exe = list(selected[0])
            with Path(c.exe[0]).open('rb') as stream:
                first_line = stream.readline(4096)
            if first_line.startswith(b'#!'):
                shebang = script_interpreter(first_line)
                interpreter = self.interpreter(shebang[0], env=c.child_environment())
                c.exe[:0] = [str(interpreter), *shebang[1:]]
            else:
                c.exe[0] = self.program(Path(c.exe[0]))
        c.env.pop('RVW_ADAPTER_RESOLUTION_ERROR', None)
        c.env['RVW_CAPTURE_INPUTS'] = str(path)
        c.env['RVW_CAPTURE_SOURCE'] = json.dumps(identity, sort_keys=True)
        return c

    def build_tree(self, path, *, git=True):
        tree = self.capture.tree(path, git=git)
        self.allow_build_outputs(tree)
        return tree

    def allow_build_outputs(self, tree):
        # Source files stay read-only. sbt and adapters may create build directories.
        for directory, _, _ in os.walk(tree.copy):
            Path(directory).chmod(0o755)
        for item in tree.files:
            self.tree_stamps.setdefault(item.copy, _stamp(item.copy.stat()))

    def verify(self):
        super().verify()
        for source, resolved, links, stamp in self.interpreter_guards:
            try:
                current, current_links = _resolve(Path(source))
                if str(current) != resolved or current_links != links or _stamp(current.stat()) != stamp:
                    raise ValueError('Python environment config changed')
            except (OSError, ValueError) as exc:
                raise CaptureError('input_not_captured:python_environment', source) from exc
        for path, stamp in self.tree_stamps.items():
            try:
                if _stamp(path.stat()) != stamp:
                    raise ValueError('captured source changed')
            except (OSError, ValueError) as exc:
                raise CaptureError('input_not_captured:source', str(exc)) from exc

    def source_metadata(self):
        result = {}
        if self.source is not None:
            result.update(core_repo=self.source.source, core_capture=str(self.source.copy),
                          core_tree_sha256=self.source.sha256)
        tools = self.tools_tree or self.python_tree
        if tools is not None:
            result.update(tools_repo=tools.source, tools_tree_sha256=tools.sha256)
        return result

    def record(self):
        return {**self.capture.record(), 'python_environments': list(self.python_environments.values())}

    def publish(self, out, names, *, source=None):
        """Publish an immutable report set. Root files remain compatibility views only."""
        names = sorted(set(names))
        source = source or out
        def build(directory):
            for name in names:
                src = source / name
                if src.is_file():
                    shutil.copyfile(src, directory / name)
                    (directory / name).chmod(src.stat().st_mode & 0o777)
            (directory / 'capture.json').write_text(json.dumps(self.record(), indent=1) + '\n')
            self.verify()
        identifier = publish(out, build)
        # Old clients use root filenames. New readers use current and its sealed generation.
        generation = out / 'generations' / identifier
        for name in names:
            src = generation / name
            if src.is_file():
                temporary = out / f'.view-{uuid.uuid4().hex}'
                shutil.copyfile(src, temporary)
                temporary.chmod(src.stat().st_mode & 0o777)
                temporary.replace(out / name)
        return identifier
