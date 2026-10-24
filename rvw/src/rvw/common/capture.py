"""C8 input capture. Consumers read copies and take all identity from ``record()``.

A Capture belongs to one command and one thread. It never refreshes an input.
CaptureError means inconclusive; a failed capture cannot produce a cache key.
"""
from __future__ import annotations

from collections import deque
from collections.abc import Iterable, Mapping
from contextlib import contextmanager
from dataclasses import dataclass
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import stat

from .proc import run_group


def run_git(repo, *args, tool='git', env=None, timeout=30, text=True, run=run_group, **kwargs):
    """Run Git without caller overrides, using the selected tool and timeout."""
    env = os.environ if env is None else env
    env = {k: v for k, v in env.items() if not k.startswith('GIT_')}
    env.update(GIT_NO_REPLACE_OBJECTS='1', GIT_OPTIONAL_LOCKS='0')
    command = [str(tool), '--no-replace-objects']
    if repo is not None:
        command += ['-C', str(repo)]
    return run([*command, *args], env=env, capture=True, text=text, timeout=timeout, **kwargs)


class CaptureError(ValueError):
    status = 'inconclusive'

    def __init__(self, cause: str, detail: str):
        self.cause = cause
        super().__init__(f'{cause}: {detail}')


def canonical_json(value) -> bytes:
    # json.dumps coerces integer/bool/None object keys to strings, losing identity.
    seen = set()

    def check(item):
        if not isinstance(item, (dict, list, tuple)) or id(item) in seen:
            return
        seen.add(id(item))
        if isinstance(item, dict):
            if any(not isinstance(key, str) for key in item):
                raise ValueError('JSON object keys must be strings')
            children = item.values()
        else:
            children = item
        for child in children:
            check(child)

    check(value)
    return json.dumps(value, sort_keys=True, separators=(',', ':'), ensure_ascii=True,
                      allow_nan=False).encode('ascii')


_json = canonical_json  # Compatibility for existing identity writers.


def _absolute(path: Path | str) -> Path:
    # Keep .. until after symlink resolution. abspath would change link/.. semantics.
    path = Path(path)
    return path if path.is_absolute() else Path.cwd() / path


def _resolve(path: Path) -> tuple[Path, tuple[tuple[str, str], ...]]:
    pending = deque(_absolute(path).parts[1:])
    resolved, links = Path('/'), []
    while pending:
        name = pending.popleft()
        if name == '..':
            resolved = resolved.parent
            continue
        candidate = resolved / name
        info = candidate.lstat()
        if stat.S_ISLNK(info.st_mode):
            if len(links) >= 40:
                raise ValueError('symlink cycle or more than 40 symlinks')
            target = os.readlink(candidate)
            links.append((str(candidate), target))
            parts = Path(target).parts
            if Path(target).is_absolute():
                resolved, parts = Path('/'), parts[1:]
            pending.extendleft(reversed(parts))
        else:
            resolved = candidate
            if pending and not stat.S_ISDIR(info.st_mode):
                raise ValueError(f'not a directory: {candidate}')
    return resolved, tuple(links)


def _stamp(info: os.stat_result) -> tuple[int, ...]:
    return (info.st_dev, info.st_ino, info.st_mode, info.st_size, info.st_mtime_ns, info.st_ctime_ns)


def _tree_path_deleted(root: Path, relative: Path) -> bool:
    """Confirm absence without mistaking an unresolved symlink for a deletion."""
    path = root
    for part in relative.parts:
        path = path / part
        try:
            info = path.lstat()
        except FileNotFoundError:
            return True
        if stat.S_ISLNK(info.st_mode):
            # Let the normal capture path resolve links, including broken links.
            return False
    return False


def _open_read(path: Path) -> int:
    """Do not follow a symlink introduced into an already resolved parent path."""
    directory = os.open('/', os.O_RDONLY | os.O_DIRECTORY)
    try:
        for part in path.parts[1:-1]:
            next_directory = os.open(part, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW,
                                     dir_fd=directory)
            os.close(directory)
            directory = next_directory
        return os.open(path.name, os.O_RDONLY | os.O_NONBLOCK | os.O_NOFOLLOW, dir_fd=directory)
    finally:
        os.close(directory)


def read_stable(path: Path, destination: Path | None = None, limit: int | None = None,
                *, keep: bool = False, single_link: bool = False):
    """Return (sha256, size, stat, bytes or None) from one checked descriptor.

    Stream into destination when set. Buffer bytes only with keep=True.
    Resolve symlinks before calling; this reader refuses them.
    """
    path = _absolute(path)
    fd = _open_read(path)
    try:
        before = os.fstat(fd)
        if not stat.S_ISREG(before.st_mode):
            raise ValueError(f'not a regular file: {path}')
        if single_link and before.st_nlink != 1:
            raise ValueError(f'not a private regular file: {path}')
        if limit is not None and before.st_size > limit:
            raise ValueError('tree size limit exceeded')
        digest, size = hashlib.sha256(), 0
        blocks = [] if keep else None
        stream = destination.open('xb') if destination is not None else None
        try:
            while block := os.read(fd, 1024 * 1024):
                size += len(block)
                if limit is not None and size > limit:
                    raise ValueError('tree size limit exceeded')
                if stream is not None:
                    stream.write(block)
                if blocks is not None:
                    blocks.append(block)
                digest.update(block)
            after = os.fstat(fd)
            if _stamp(before) != _stamp(after) or size != after.st_size:
                raise ValueError(f'file changed during capture: {path}')
            return digest.hexdigest(), size, before, b''.join(blocks) if keep else None
        finally:
            if stream is not None:
                stream.close()
    finally:
        os.close(fd)


def _read_into(path: Path, destination: Path | None = None, limit: int | None = None):
    return read_stable(path, destination, limit)[:3]


def sha256_file(path: str | Path) -> str:
    """Hash a generated file. Use Captured.sha256 for captured input identity."""
    return read_stable(Path(path).resolve(strict=True))[0]


@dataclass(frozen=True)
class Captured:
    copy: Path
    sha256: str
    size: int
    source: str
    resolved: str
    executable: int = 0
    symlinks: tuple[tuple[str, str], ...] = ()


@dataclass(frozen=True)
class CapturedTree:
    copy: Path
    sha256: str
    size: int
    source: str
    resolved: str
    files: tuple[Captured, ...]
    directories: tuple[str, ...]
    symlinks: tuple[tuple[str, str], ...]
    git: bool
    deleted: tuple[str, ...] = ()


@dataclass(frozen=True)
class CapturedTool:
    path: Path
    copy: Path
    sha256: str
    size: int
    source: str
    resolved: str
    version: str
    symlinks: tuple[tuple[str, str], ...]


class Capture:
    def __init__(self, root: Path, *, max_tree_bytes: int = 256 * 1024 * 1024,
                 max_tree_files: int = 100_000):
        if max_tree_bytes < 0 or max_tree_files < 1:
            raise ValueError('tree limits must be non-negative bytes and positive files')
        try:
            root = _absolute(root)
            root.parent.mkdir(parents=True, exist_ok=True)
            self.root = root.parent.resolve(strict=True) / root.name
            self.root.mkdir(mode=0o700)  # exclusive: do not adopt another command's directory
        except (OSError, ValueError) as exc:
            raise CaptureError('input_not_captured:root', str(exc)) from exc
        self.max_tree_bytes, self.max_tree_files = max_tree_bytes, max_tree_files
        self._files: dict[str, Captured] = {}
        self._stamps: dict[str, tuple[int, ...]] = {}
        self._trees: dict[tuple[str, bool], CapturedTree] = {}
        self._refs: dict[tuple[str, str], dict] = {}
        self._repos: dict[str, tuple[Path, tuple]] = {}
        self._tools: dict[str, CapturedTool] = {}
        self._environment: dict[str, str | None] = {}
        self._problems: set[str] = set()

    @contextmanager
    def _operation(self, name):
        try:
            yield
        except BaseException as exc:
            cause = exc.cause if isinstance(exc, CaptureError) else f'input_not_captured:{name}'
            self._problems.add(cause)
            if isinstance(exc, (OSError, ValueError, RuntimeError)) and not isinstance(exc, CaptureError):
                raise CaptureError(cause, str(exc)) from exc
            raise

    def _file(self, path: Path, name: str | None, limit: int | None = None,
              resolution=None) -> Captured:
        key = str(_absolute(path))
        if key in self._files:
            item = self._files[key]
            if limit is not None and item.size > limit:
                raise ValueError('tree size limit exceeded')
            return item
        leaf = path.name if name is None else name
        if not isinstance(leaf, str) or not leaf or leaf in ('.', '..') or '/' in leaf or '\x00' in leaf:
            raise ValueError('capture name must be a single file name')
        resolved, links = _resolve(path) if resolution is None else resolution
        if resolved.is_relative_to(self.root):
            raise ValueError('a live input is inside the capture directory')
        target = self.root / 'files' / hashlib.sha256(os.fsencode(key)).hexdigest() / leaf
        target.parent.mkdir(parents=True)
        try:
            digest, size, info = _read_into(resolved, target, limit)
            executable = stat.S_IMODE(info.st_mode) & 0o111
            target.chmod(0o444 | executable)
            item = Captured(target, digest, size, str(path), str(resolved), executable, links)
        except BaseException:
            target.unlink(missing_ok=True)
            target.parent.rmdir()
            raise
        self._files[key], self._stamps[key] = item, _stamp(info)
        return item

    def file(self, path: Path, name: str | None = None) -> Captured:
        with self._operation(name or str(path)):
            return self._file(Path(path), name)

    def files(self, paths: Iterable[Path]) -> list[Captured]:
        with self._operation('files'):
            return [self.file(path) for path in paths]

    def tree(self, path: Path, *, git: bool = True) -> CapturedTree:
        key = (str(_absolute(path)), git)
        with self._operation(str(path)):
            if key in self._trees:
                return self._trees[key]
            resolved, root_links = _resolve(Path(path))
            if not resolved.is_dir() or self.root.is_relative_to(resolved) or resolved.is_relative_to(self.root):
                raise ValueError('tree is not a directory or overlaps the capture directory')
            target = self.root / 'trees' / hashlib.sha256(_json(key)).hexdigest()
            target.mkdir(parents=True)
            entries, links, size = [], set(root_links), 0
            directories, deleted, count = set(), [], 0

            def save(original, relative, resolution=None):
                nonlocal size
                item = self._file(original, None, self.max_tree_bytes - size, resolution)
                links.update(item.symlinks)
                saved = target / relative
                # git lists files, so implicit parent directories also belong to identity.
                directories.update(parent.as_posix() for parent in relative.parents if parent.parts)
                if len(entries) + 1 + len(directories) + len(deleted) > self.max_tree_files:
                    raise ValueError('tree entry-count limit exceeded')
                saved.parent.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(item.copy, saved)
                saved.chmod(0o444 | item.executable)
                entries.append(Captured(saved, item.sha256, item.size, item.source, item.resolved,
                                        item.executable, item.symlinks))
                size += item.size

            def visit(original, relative, ancestors, listed=False, opened=None, inherited=()):
                nonlocal count
                count += 1
                if count > self.max_tree_files:
                    raise ValueError('tree entry-count limit exceeded')
                if str(_absolute(original)) in self._files:
                    save(original, relative)
                    return
                real, chain = _resolve(original if opened is None else opened)
                chain = tuple(dict.fromkeys((*inherited, *chain)))
                links.update(chain)
                info = real.lstat()
                if stat.S_ISDIR(info.st_mode):
                    if listed and not any(link == str(original) for link, _ in chain):
                        raise ValueError(f'git directory entry is unsupported (submodule): {original}')
                    if real in ancestors or self.root.is_relative_to(real) or real.is_relative_to(self.root):
                        raise ValueError(f'cyclic or self-referencing tree: {original}')
                    (target / relative).mkdir(parents=True, exist_ok=True)
                    directories.add(relative.as_posix())
                    for child in sorted(real.iterdir(), key=lambda p: p.name):
                        # Traverse the pinned target, not its possibly retargeted logical alias.
                        visit(original / child.name, relative / child.name, ancestors | {real},
                              opened=real / child.name, inherited=chain)
                else:
                    save(original, relative, (real, chain))

            try:
                if git:
                    # One list fixes the input set. No later read uses this checkout.
                    # Match source identity: only repository .gitignore rules may omit inputs.
                    # Private info/exclude and core.excludesFile must not hide source changes.
                    names = self._git(resolved, ['ls-files', '-z', '--cached', '--others',
                                                 '--exclude-per-directory=.gitignore'])
                    missing = set(self._git(resolved, ['ls-files', '-z', '--deleted']).split(b'\x00'))
                    for raw in sorted(set(names.split(b'\x00')) - {b''}):
                        relative = Path(os.fsdecode(raw))
                        if relative.is_absolute() or '..' in relative.parts or not relative.parts:
                            raise ValueError('invalid git file path')
                        if raw in missing and _tree_path_deleted(resolved, relative):
                            count += 1
                            if count > self.max_tree_files:
                                raise ValueError('tree entry-count limit exceeded')
                            deleted.append(relative.as_posix())
                            continue
                        visit(resolved / relative, relative, {resolved}, listed=True)
                else:
                    for child in sorted(resolved.iterdir(), key=lambda p: p.name):
                        visit(resolved / child.name, Path(child.name), {resolved})
                entries.sort(key=lambda item: item.copy.relative_to(target).as_posix())
                identities = [{'path': item.copy.relative_to(target).as_posix(), 'sha256': item.sha256,
                               'size': item.size, 'executable': item.executable} for item in entries]
                if len(entries) + len(directories) + len(deleted) > self.max_tree_files:
                    raise ValueError('tree entry-count limit exceeded')
                identities += [{'path': name, 'deleted': True} for name in deleted]
                digest = hashlib.sha256(_json({'files': identities, 'directories': sorted(directories),
                                               'symlinks': sorted(links)})).hexdigest()
                for directory, _, _ in os.walk(target, topdown=False):
                    Path(directory).chmod(0o555)
                tree = CapturedTree(target, digest, size, str(path), str(resolved), tuple(entries),
                                    tuple(sorted(directories)), tuple(sorted(links)), git, tuple(deleted))
                self._trees[key] = tree
                return tree
            except BaseException:
                for directory, _, _ in os.walk(target):
                    Path(directory).chmod(0o700)
                shutil.rmtree(target)
                raise

    def _git(self, repo: Path, args: list[str]) -> bytes:
        tool = self.tool('git')
        self._check_tool(tool)
        result = run_git(repo, *args, tool=tool.path, text=False, run=run_group)
        self._check_tool(tool)
        if result.timed_out or result.returncode:
            raise ValueError(f'git command failed: {os.fsdecode(result.stderr or b"").strip()}')
        return result.stdout or b''

    def git_ref(self, repo: Path, ref: str) -> str:
        key = (str(_absolute(repo)), ref)
        with self._operation(f'git_ref:{ref}'):
            if key in self._refs:
                return self._refs[key]['commit']
            if not isinstance(ref, str) or not ref or '\x00' in ref:
                raise ValueError('invalid git ref')
            if key[0] not in self._repos:
                self._repos[key[0]] = _resolve(Path(repo))
            resolved, links = self._repos[key[0]]
            commit = self._git(resolved, ['rev-parse', '--verify', '--end-of-options', f'{ref}^{{commit}}']).decode('ascii').strip()
            if not re.fullmatch(r'(?:[0-9a-f]{40}|[0-9a-f]{64})', commit):
                raise ValueError('git did not return one full commit ID')
            self._refs[key] = {'source': str(repo), 'resolved': str(resolved), 'ref': ref,
                               'commit': commit, 'symlinks': self._links(links)}
            return commit

    def tool(self, name_or_path: str | Path, *, identity_only: bool = False) -> CapturedTool:
        """Record one executable. identity_only skips --version and records an empty version.

        The first call for a name selects its mode for the whole Capture.
        """
        key = str(name_or_path)
        with self._operation(f'tool:{key}'):
            if key in self._tools:
                return self._tools[key]
            selected = shutil.which(key)
            if selected is None:
                raise ValueError(f'tool not found or not executable: {key}')
            item = self._file(Path(selected), None)
            if not item.executable:
                raise ValueError(f'tool is not executable: {key}')
            pending = CapturedTool(Path(item.resolved), item.copy, item.sha256, item.size, key,
                                   item.resolved, '', item.symlinks)
            self._check_tool(pending)
            version = ''
            if not identity_only:
                result = run_group([item.resolved, '--version'], capture=True, timeout=10)
                if result.timed_out or result.returncode:
                    raise ValueError(f'tool --version failed: {key}')
                version = (result.stdout or '') + (result.stderr or '')
            tool = CapturedTool(Path(item.resolved), item.copy, item.sha256, item.size, key,
                                item.resolved, version, item.symlinks)
            self._check_tool(tool)
            self._tools[key] = tool
            return tool

    def _check_tool(self, tool: CapturedTool) -> None:
        # A content-only check misses an edit-and-revert. Keep inode and ctime too.
        original = next(key for key, item in self._files.items() if item.copy == tool.copy)
        try:
            digest, size, info = _read_into(tool.path)
            if digest != tool.sha256 or size != tool.size or _stamp(info) != self._stamps[original]:
                raise ValueError('tool content or metadata changed')
        except (OSError, ValueError) as exc:
            raise CaptureError(f'input_not_captured:tool:{tool.source}', str(exc)) from exc

    def verify_tools(self) -> None:
        with self._operation('tools'):
            for tool in self._tools.values():
                self._check_tool(tool)

    def env(self, *names: str) -> dict[str, str | None]:
        for name in names:
            if name not in self._environment:
                self._environment[name] = os.environ.get(name)
        return {name: self._environment[name] for name in names}

    @staticmethod
    def _links(links):
        return [{'path': path, 'target': target} for path, target in links]

    def _file_record(self, item):
        return {'copy': item.copy.relative_to(self.root).as_posix(), 'sha256': item.sha256,
                'size': item.size, 'source': item.source, 'resolved': item.resolved,
                'executable': item.executable, 'symlinks': self._links(item.symlinks)}

    def record(self) -> dict:
        trees = []
        for _, item in sorted(self._trees.items()):
            trees.append({'copy': item.copy.relative_to(self.root).as_posix(), 'sha256': item.sha256,
                          'size': item.size, 'source': item.source, 'resolved': item.resolved,
                          'git': item.git, 'symlinks': self._links(item.symlinks),
                          'directories': list(item.directories),
                          'deleted': list(item.deleted),
                          'files': [self._file_record(file) for file in item.files]})
        tools = [{'path': str(item.path), 'copy': item.copy.relative_to(self.root).as_posix(),
                  'sha256': item.sha256, 'size': item.size, 'source': item.source,
                  'resolved': item.resolved, 'version': item.version, 'symlinks': self._links(item.symlinks)}
                 for _, item in sorted(self._tools.items())]
        return json.loads(_json({'schema': 'rvw.capture/1',
                                'files': [self._file_record(item) for _, item in sorted(self._files.items())],
                                'trees': trees, 'git_refs': [item for _, item in sorted(self._refs.items())],
                                'tools': tools, 'env': self._environment, 'problems': sorted(self._problems)}))

    def cache_key(self, options: Mapping, *, complete: bool = False) -> str | None:
        """Opt in only when every result input, option and environment value is enumerated."""
        if complete is not True or self._problems:
            return None
        return hashlib.sha256(_json({'capture': self.record(), 'options': dict(options)})).hexdigest()
