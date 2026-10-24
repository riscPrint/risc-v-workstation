"""C8 immutable result generations with one atomic ``current`` pointer switch.

The builder must finish all writes before returning. Published directories are
never reused, changed or removed by this module. A reader never follows current twice.
"""
from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import stat
import uuid

from rvw.common.capture import canonical_json, read_stable, _stamp

GenerationId = str
_MANIFEST = 'generation.json'


class GenerationError(ValueError):
    """Missing, unsupported or changed result evidence; never accept it."""


def _relative(name: str | Path) -> Path:
    path = Path(name)
    if path.is_absolute() or '..' in path.parts or not path.parts:
        raise GenerationError(f'invalid generation path: {name}')
    return path


def _regular(path: Path) -> bytes:
    return read_stable(path, keep=True, single_link=True)[3]


def _root(out_dir: Path, *, create=False) -> Path:
    root = Path(out_dir).absolute()
    if create:
        root.mkdir(parents=True, exist_ok=True, mode=0o700)
    if root.is_symlink() or not root.is_dir():
        raise GenerationError(f'not a result directory: {root}')
    return root.resolve(strict=True)


def _inventory(path: Path) -> tuple[list[dict], list[str]]:
    files, directories = [], []

    def visit(directory):
        for child in sorted(directory.iterdir(), key=lambda p: p.name):
            relative = child.relative_to(path).as_posix()
            info = child.lstat()
            if stat.S_ISDIR(info.st_mode):
                directories.append(relative)
                visit(child)
            elif stat.S_ISREG(info.st_mode) and info.st_nlink == 1:
                if relative == _MANIFEST:
                    continue
                digest, size, read_info, _ = read_stable(child, single_link=True)
                if _stamp(info) != _stamp(read_info):
                    raise GenerationError(f'generation entry changed: {relative}')
                files.append({'path': relative, 'sha256': digest, 'size': size,
                              'executable': stat.S_IMODE(info.st_mode) & 0o111})
            else:
                raise GenerationError(f'generation contains a symlink, hardlink or special file: {relative}')

    visit(path)
    return sorted(files, key=lambda item: item['path']), sorted(directories)


def _read_pointer(root: Path) -> dict:
    record = json.loads(_regular(root / 'current'))
    if (not isinstance(record, dict) or set(record) != {'schema', 'id', 'manifest_sha256'}
            or record['schema'] != 'rvw.generation-pointer/1'
            or not isinstance(record['id'], str) or not re.fullmatch('[0-9a-f]{32}', record['id'])
            or not isinstance(record['manifest_sha256'], str)
            or not re.fullmatch('[0-9a-f]{64}', record['manifest_sha256'])):
        raise GenerationError('invalid generation pointer')
    return record


@dataclass(frozen=True)
class Generation:
    id: GenerationId
    manifest_sha256: str
    _path: Path
    _identity: tuple[int, int]
    _manifest: bytes
    _files: tuple[tuple[str, str, int, int], ...]
    _directories: tuple[str, ...]

    @property
    def files(self) -> tuple[tuple[str, str, int, int], ...]:
        """Read-only (path, sha256, size, execute bits) inventory."""
        return self._files

    def entry(self, name: str | Path) -> tuple[str, str, int, int] | None:
        relative = _relative(name).as_posix()
        return next((item for item in self._files if item[0] == relative), None)

    @property
    def path(self) -> Path:
        """Pinned directory. Refuse if it vanished or was replaced; never reopen current."""
        try:
            info = self._path.lstat()
            if not stat.S_ISDIR(info.st_mode) or (info.st_dev, info.st_ino) != self._identity:
                raise GenerationError(f'generation vanished or was replaced: {self.id}')
            return self._path
        except OSError as exc:
            raise GenerationError(f'generation vanished: {self.id}') from exc

    def read_bytes(self, name: str | Path) -> bytes:
        """Read and hash one artifact from this generation, with no live-pointer lookup."""
        try:
            relative = _relative(name)
            entry = self.entry(relative)
            if entry is None:
                raise GenerationError(f'file is not in generation {self.id}: {name}')
            path = self.path
            for part in relative.parts[:-1]:
                path /= part
                if not stat.S_ISDIR(path.lstat().st_mode):
                    raise GenerationError(f'generation directory changed: {path}')
            digest, size, _, data = read_stable(path / relative.name, keep=True, single_link=True)
            if size != entry[2] or digest != entry[1]:
                raise GenerationError(f'generation artifact changed: {name}')
            _ = self.path
            return data
        except (OSError, ValueError) as exc:
            if isinstance(exc, GenerationError):
                raise
            raise GenerationError(f'cannot read generation {self.id}: {exc}') from exc

    def verify(self) -> None:
        """Refuse missing, changed or extra evidence in the pinned generation."""
        try:
            path = self.path
            if _regular(path / _MANIFEST) != self._manifest:
                raise GenerationError(f'generation manifest changed: {self.id}')
            files, directories = _inventory(path)
            expected = [{'path': name, 'sha256': digest, 'size': size, 'executable': executable}
                        for name, digest, size, executable in self._files]
            if files != expected or tuple(directories) != self._directories:
                raise GenerationError(f'generation contents changed: {self.id}')
            _ = self.path
        except (OSError, ValueError) as exc:
            if isinstance(exc, GenerationError):
                raise
            raise GenerationError(f'cannot verify generation {self.id}: {exc}') from exc


def _open(root: Path, identifier: str, expected_hash: str | None = None) -> Generation:
    if not isinstance(identifier, str) or not re.fullmatch('[0-9a-f]{32}', identifier):
        raise GenerationError('invalid generation ID')
    parent = root / 'generations'
    if parent.is_symlink() or not parent.is_dir():
        raise GenerationError('generation store is missing or is a symlink')
    path = parent / identifier
    info = path.lstat()
    if not stat.S_ISDIR(info.st_mode):
        raise GenerationError('generation is not a private directory')
    raw = _regular(path / _MANIFEST)
    digest = hashlib.sha256(raw).hexdigest()
    if expected_hash is not None and digest != expected_hash:
        raise GenerationError('generation manifest hash differs from the pointer')
    manifest = json.loads(raw)
    if (not isinstance(manifest, dict) or set(manifest) != {'schema', 'id', 'files', 'directories'}
            or manifest['schema'] != 'rvw.generation/1' or manifest['id'] != identifier
            or not isinstance(manifest['files'], list) or not isinstance(manifest['directories'], list)):
        raise GenerationError('invalid generation manifest')
    files = []
    for item in manifest['files']:
        if (not isinstance(item, dict) or set(item) != {'path', 'sha256', 'size', 'executable'}
                or not isinstance(item['path'], str) or not isinstance(item['sha256'], str)
                or not re.fullmatch('[0-9a-f]{64}', item['sha256'])
                or type(item['size']) is not int or item['size'] < 0
                or type(item['executable']) is not int or item['executable'] & ~0o111):
            raise GenerationError('invalid generation file entry')
        relative = _relative(item['path'])
        if relative.as_posix() != item['path'] or item['path'] == _MANIFEST:
            raise GenerationError('non-canonical generation file path')
        files.append((item['path'], item['sha256'], item['size'], item['executable']))
    if files != sorted(set(files)) or len({item[0] for item in files}) != len(files):
        raise GenerationError('unsorted or duplicate generation entries')
    directories = manifest['directories']
    if any(not isinstance(name, str) or _relative(name).as_posix() != name for name in directories):
        raise GenerationError('invalid generation directory entry')
    if directories != sorted(set(directories)):
        raise GenerationError('unsorted or duplicate generation directories')
    generation = Generation(identifier, digest, path, (info.st_dev, info.st_ino),
                            raw, tuple(files), tuple(directories))
    generation.verify()
    return generation


def open_current(out_dir: Path) -> Generation:
    """Resolve current once, validate the whole manifest, and return a pinned reader."""
    try:
        root = _root(out_dir)
        record = _read_pointer(root)
        return _open(root, record['id'], record['manifest_sha256'])
    except (OSError, ValueError) as exc:
        if isinstance(exc, GenerationError):
            raise
        raise GenerationError(f'cannot open result generation: {exc}') from exc


def open_generation(out_dir: Path, identifier: str) -> Generation:
    """Open and fully verify an explicit generation without reading current."""
    try:
        return _open(_root(out_dir), identifier)
    except (OSError, ValueError) as exc:
        if isinstance(exc, GenerationError):
            raise
        raise GenerationError(f'cannot open result generation: {exc}') from exc


def has_store(directory: Path) -> bool:
    return ((directory / 'generations').exists() or (directory / 'current').is_file()
            or (directory / 'current').is_symlink())


def locate(path: Path, *, readers: dict | None = None) -> tuple[Path, Generation | None]:
    """Select a store/member path. An optional command-owned cache pins each selection once."""
    path = Path(path).absolute()
    store = next((p for p in (path, *path.parents) if has_store(p)), None)
    if store is None:
        return path, None
    relative = path.relative_to(store)
    explicit = relative.parts[:1] == ('generations',) and len(relative.parts) >= 2
    identifier = relative.parts[1] if explicit else 'current'
    key = (str(store.resolve()), identifier)
    if readers is None:
        readers = {}
    if key not in readers:
        readers[key] = open_generation(store, identifier) if explicit else open_current(store)
    reader = readers[key]
    member = Path(*relative.parts[2:]) if explicit else relative
    return reader.path / member, reader


def _discard(path: Path) -> None:
    if not path.exists():
        return
    for directory, _, _ in os.walk(path):
        Path(directory).chmod(0o700)
    shutil.rmtree(path)


def publish(out_dir: Path, build: Callable[[Path], None]) -> GenerationId:
    """Build in a new directory, seal it, and atomically replace the current pointer.

    Resume calls publish again. Old generations remain available to existing readers.
    A failed build or cancellation leaves current unchanged. Concurrent writers are safe;
    the last atomic pointer switch wins, with no ordering promise between writers.
    """
    stage = pointer = None
    try:
        root = _root(out_dir, create=True)
        store = root / 'generations'
        store.mkdir(mode=0o700, exist_ok=True)
        if store.is_symlink() or not store.is_dir():
            raise GenerationError('generation store is not a private directory')
        identifier = uuid.uuid4().hex
        stage = store / f'.building-{identifier}'
        stage.mkdir(mode=0o700)
        build(stage)
        if (stage / _MANIFEST).exists() or (stage / _MANIFEST).is_symlink():
            raise GenerationError(f'{_MANIFEST} is reserved for the generation manifest')
        files, directories = _inventory(stage)
        raw = canonical_json({'schema': 'rvw.generation/1', 'id': identifier,
                     'files': files, 'directories': directories}) + b'\n'
        (stage / _MANIFEST).write_bytes(raw)
        for entry in files:
            (stage / entry['path']).chmod(0o444 | entry['executable'])
        (stage / _MANIFEST).chmod(0o444)
        for directory in reversed(directories):
            (stage / directory).chmod(0o555)
        stage.chmod(0o555)
        final = store / identifier
        stage.rename(final)
        # An unpublished orphan is safe if the process stops after this rename.
        stage = None
        record = {'schema': 'rvw.generation-pointer/1', 'id': identifier,
                  'manifest_sha256': hashlib.sha256(raw).hexdigest()}
        _open(root, identifier, record['manifest_sha256'])  # detect writes while sealing
        pointer = root / f'.current-{identifier}'
        with pointer.open('xb') as stream:
            stream.write(canonical_json(record) + b'\n')
        pointer.chmod(0o444)
        os.replace(pointer, root / 'current')
        return identifier
    except (OSError, ValueError) as exc:
        if isinstance(exc, GenerationError):
            raise
        raise GenerationError(f'cannot publish result generation: {exc}') from exc
    finally:
        if pointer is not None:
            pointer.unlink(missing_ok=True)
        if stage is not None:
            _discard(stage)
