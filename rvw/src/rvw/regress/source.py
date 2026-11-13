"""Core and tool source revisions: what a result was produced from, and checkouts of other revisions."""
from __future__ import annotations

import contextlib
import fcntl
import hashlib
import os
import shutil
import tempfile
from dataclasses import dataclass
from pathlib import Path

from ..common.capture import Capture
from ..common.proc import run_group
from ..common.capture import run_git

WORKTREE = "WORKTREE"


# git runs in its own process group (rvw.common.proc): a timeout or a cancel also stops what it
# started (hooks, filters, credential helpers).
GIT_TIMEOUT_S = 60
GIT_BYTES_TIMEOUT_S = 300
CLONE_TIMEOUT_S = 900


def _git(repo: Path, *args: str) -> str | None:
    try:
        r = run_git(repo, *args, timeout=GIT_TIMEOUT_S, run=run_group)
    except OSError:
        return None
    return r.stdout.strip() if r.returncode == 0 and not r.timed_out else None


def _git_bytes(repo: Path, *args: str) -> bytes | None:
    try:
        r = run_git(repo, *args, text=False, timeout=GIT_BYTES_TIMEOUT_S, run=run_group)
    except OSError:
        return None
    return r.stdout if r.returncode == 0 and not r.timed_out else None


def _hash_file(h, p: Path) -> None:
    if p.is_symlink():
        h.update(b"link:" + os.readlink(p).encode())
        return
    try:
        with open(p, "rb") as f:
            h.update(f"mode:{os.fstat(f.fileno()).st_mode & 0o111}\0".encode())
            for chunk in iter(lambda: f.read(1 << 20), b""):
                h.update(chunk)
    except OSError as e:
        h.update(f"unreadable:{e.errno}".encode())


# Limits for hashing the content behind symbolic links. Past them the content is "not covered" and
# results are not reused (review 10): hashing must stay cheap, and a guess is not an identity.
LINK_MAX_FILES = 100_000
LINK_MAX_BYTES = 1 << 30


class _Uncovered(Exception):
    """The content behind a link cannot be identified (cycle, limits, unreadable)."""


def _content(h, p: Path, budget: list[int], seen: frozenset) -> None:
    """Hash what `p` resolves to: a file's bytes or a directory's tree (names and bytes). A link
    inside the tree that stays inside it is hashed as its text (its target is hashed in place);
    a link that leaves it is followed. Raises _Uncovered on a cycle or past the limits."""
    real = Path(os.path.realpath(p))
    if real in seen:
        raise _Uncovered(f"symbolic link cycle at {p}")
    seen = seen | {real}
    if not real.exists():
        h.update(b"missing")
        return

    def charge(f: Path) -> None:
        budget[0] -= 1
        try:
            budget[1] -= f.stat().st_size
        except OSError:
            pass
        if budget[0] < 0 or budget[1] < 0:
            raise _Uncovered(f"more than {LINK_MAX_FILES} files or {LINK_MAX_BYTES} bytes behind links")

    if real.is_file():
        charge(real)
        h.update(b"file\0")
        _hash_file(h, real)
        return
    h.update(b"dir\0")
    for top, dirs, files in os.walk(real, followlinks=False):
        dirs.sort()
        for name in sorted(dirs + files):
            q = Path(top) / name
            h.update(b"\0" + q.relative_to(real).as_posix().encode() + b"\0")
            if q.is_symlink():
                target = Path(os.path.realpath(q))
                if target == real or real in target.parents:
                    h.update(b"link:" + os.readlink(q).encode())
                else:
                    h.update(b"follow:")
                    _content(h, q, budget, seen)
            elif q.is_file():
                charge(q)
                _hash_file(h, q)


def content_hash(p: Path) -> str | None:
    """Hash of the content behind `p` (following links that leave it), or None when not covered."""
    h = hashlib.sha256()
    try:
        _content(h, p, [LINK_MAX_FILES, LINK_MAX_BYTES], frozenset())
    except (_Uncovered, OSError):
        return None
    return h.hexdigest()


def links_key(repo: Path, pathspec: list[str] | None = None, _depth: int = 0) -> tuple[str | None, bool]:
    """Identity of the content behind every tracked symbolic link of a git checkout (or of
    `pathspec`): git records only the link text, so a changed target keeps the revision and a
    clean status. Links inside initialized submodules count. Returns (hash, or None when there is
    no link; covered). Not covered: git failed, a link cycle, more content than
    LINK_MAX_FILES/LINK_MAX_BYTES, or a submodule that cannot be read."""
    out = _git_bytes(repo, "ls-files", "-s", "-z", *(["--", *pathspec] if pathspec else []))
    if out is None:
        return None, False
    h, n = hashlib.sha256(), 0
    for entry in sorted(x for x in out.split(b"\0") if x):
        meta, _, name = entry.partition(b"\t")
        if meta.startswith(b"160000 "):      # a submodule: the links inside it count too
            sub = _submodule(repo, name)
            if sub is False:
                return None, False
            if sub is not None:
                if _depth >= SUBMODULE_MAX_DEPTH:
                    return None, False
                k, covered = links_key(sub, None, _depth + 1)
                if not covered:
                    return None, False
                if k:
                    n += 1
                    h.update(b"\0submodule:" + name + b"\0" + k.encode())
            continue
        if not meta.startswith(b"120000 "):
            continue
        n += 1
        p = repo / os.fsdecode(name)
        h.update(b"\0" + name + b"\0")
        if not p.is_symlink():       # replaced in the working tree: git status shows it as dirty
            h.update(b"not-a-link")
            continue
        sub = content_hash(p)
        if sub is None:
            return None, False
        h.update(sub.encode())
    return (h.hexdigest() if n else None), True


# Submodules (review 11): the parent's status and diff show a dirty submodule but not its changed
# bytes, and `.gitmodules` (`ignore = dirty|all`) or the user's config can hide it entirely. Every
# status and diff therefore uses --ignore-submodules=none, and each initialized submodule is
# fingerprinted on its own, recursively.
SUBMODULE_MAX_DEPTH = 8
_NO_IGNORE = "--ignore-submodules=none"


def _submodule(repo: Path, name: bytes) -> Path | None | bool:
    """The checkout of submodule `name` (a gitlink entry of `repo`): its path when initialized,
    None when not checked out (an empty directory or none; the recorded commit is in the parent's
    tree), False when it cannot be identified (files there but no repository of its own)."""
    p = repo / os.fsdecode(name)
    if (p / ".git").exists():
        top = _git(p, "rev-parse", "--show-toplevel")
        return p if top and Path(top).resolve() == p.resolve() else False
    if not p.exists() or (p.is_dir() and not any(p.iterdir())):
        return None
    return False


def tree_key(path: Path) -> str | None:
    """Content of a tree outside git (names, bytes, content behind outgoing links); None when not covered."""
    return content_hash(path)


def _check_git_features(repo: Path) -> None:
    """Refuse Git features whose object or checkout semantics we do not verify."""
    why = None
    if _git(repo, "config", "--bool", "core.sparseCheckout") == "true":
        why = "sparse checkout"
    elif _git(repo, "rev-parse", "--is-shallow-repository") == "true":
        why = "shallow history"
    elif _git(repo, "for-each-ref", "--format=%(refname)", "refs/replace/"):
        why = "replace refs"
    elif any(os.environ.get(k) for k in ("GIT_REPLACE_REF_BASE", "GIT_GRAFT_FILE")):
        why = "alternate replacement refs or grafts"
    if not why and _git(repo, "config", "--get-regexp", r"^filter\."):
        names = _git_bytes(repo, "ls-files", "-z")
        if names:
            attrs = run_git(repo, "check-attr", "-z", "--stdin", "filter", input=names,
                            text=False, timeout=GIT_BYTES_TIMEOUT_S, run=run_group)
            if attrs.returncode != 0 or attrs.timed_out:
                why = "filter attributes (Git failed)"
            elif any(v not in (b"unspecified", b"unset")
                     for v in attrs.stdout.split(b"\0")[2::3]):
                why = "clean/smudge filters"
    for name in ("info/grafts", "info/attributes"):
        loc = _git(repo, "rev-parse", "--git-path", name)
        if loc:
            p = Path(loc)
            p = p if p.is_absolute() else repo / p
            if p.is_file() and any(line.strip() and not line.lstrip().startswith("#")
                                   for line in p.read_text().splitlines()):
                why = name
    if why:
        raise ValueError(f"{repo}: source identity cannot verify {why}; remove this Git feature")


def _untracked(repo: Path, spec: list[str]) -> bytes | None:
    # Per-directory .gitignore rules may omit build products from source identity.
    # info/exclude and core.excludesFile are private, mutable rules that can hide source files.
    return _git_bytes(repo, "ls-files", "--others", "--exclude-per-directory=.gitignore", "-z", *spec)


def _tracked_state(repo: Path, pathspec: list[str] | None = None,
                   depth: int = 0) -> tuple[str | None, bool]:
    """Raw tracked bytes and executable bits, independent of index flags, filters and stat cache.

    Compare raw blob hashes with the index. Status/diff separately detect changes to the index
    against HEAD. A normalized checkout (autocrlf, eol, ident or encoding attributes) therefore
    counts as dirty when its actual bytes differ. No Git clean filter runs here.
    """
    _check_git_features(repo)
    top = _git(repo, "rev-parse", "--show-toplevel")
    algorithm = _git(repo, "rev-parse", "--show-object-format")
    if not top or algorithm not in ("sha1", "sha256"):
        return None, True
    root = Path(top)
    specs = pathspec or [str(repo.resolve())]
    entries = _git_bytes(root, "ls-files", "--stage", "--full-name", "-z", "--", *specs)
    if entries is None:
        return None, True
    h, dirty = hashlib.sha256(), False
    budget = [LINK_MAX_FILES, LINK_MAX_BYTES]
    try:
        for entry in sorted(e for e in entries.split(b"\0") if e):
            meta, name = entry.split(b"\t", 1)
            mode, expected, stage = meta.split()
            p = root / os.fsdecode(name)
            h.update(b"\0" + entry + b"\0")
            if stage != b"0":
                return None, True
            if mode == b"160000":
                sub = _submodule(root, name)
                if sub is False or depth >= SUBMODULE_MAX_DEPTH:
                    return None, True
                if sub is not None:
                    child = describe(sub, _depth=depth + 1)
                    if not child.reusable:
                        return None, True
                    dirty |= child.dirty or child.rev != expected.decode()
                    h.update(str((child.rev, child.fingerprint, child.links)).encode())
                continue
            if not p.exists() and not p.is_symlink():
                dirty = True
                h.update(b"missing")
                continue
            if p.is_symlink():
                data = os.fsencode(os.readlink(p))
                actual_mode = b"120000"
                blob = hashlib.new(algorithm, b"blob " + str(len(data)).encode() + b"\0" + data)
            elif p.is_file():
                st = p.stat()
                budget[0] -= 1
                budget[1] -= st.st_size
                if min(budget) < 0:
                    return None, True
                actual_mode = b"100755" if st.st_mode & 0o111 else b"100644"
                blob = hashlib.new(algorithm, b"blob " + str(st.st_size).encode() + b"\0")
                with p.open("rb") as f:
                    for chunk in iter(lambda: f.read(1 << 20), b""):
                        blob.update(chunk)
            else:
                return None, True
            actual = blob.hexdigest().encode()
            dirty |= actual != expected or actual_mode != mode
            h.update(actual_mode + b" " + actual)
    except OSError:
        return None, True
    return h.hexdigest(), dirty


def fingerprint(repo: Path, pathspec: list[str] | None = None, _depth: int = 0) -> str | None:
    """Content identity of a git checkout (or of `pathspec` inside it) beyond HEAD: the status,
    the diff against HEAD and the bytes of every untracked, not ignored file. Equal fingerprints
    mean equal working trees at the same HEAD. A changed or untracked path that is a symbolic link
    adds the content behind it (tracked links: `links_key`). Each initialized submodule adds its own
    fingerprint and links, recursively. None when git fails or that content is not covered."""
    spec = ["--", *pathspec] if pathspec else []
    tracked, _ = _tracked_state(repo, pathspec, _depth)
    if tracked is None:
        return None
    h = hashlib.sha256(tracked.encode())
    for args in (("rev-parse", "HEAD"),
                 ("status", "--porcelain=v1", "-z", "--untracked-files=all", _NO_IGNORE, *spec),
                 ("diff", "HEAD", "--binary", "--no-color", "--no-ext-diff", _NO_IGNORE, *spec)):
        out = _git_bytes(repo, *args)
        if out is None:
            return None
        h.update(b"\0" + out)
    names = _untracked(repo, spec)
    if names is None:
        return None
    for n in sorted(x for x in names.split(b"\0") if x):  # paths relative to `repo`
        h.update(b"\0untracked:" + n + b"\0")
        _hash_file(h, repo / os.fsdecode(n))
    changed = _git_bytes(repo, "diff", "HEAD", "--relative", "--name-only", "-z", _NO_IGNORE, *spec)
    if changed is None:
        return None
    for n in sorted(set(x for x in (changed + b"\0" + names).split(b"\0") if x)):
        p = repo / os.fsdecode(n)
        if p.is_symlink():
            sub = content_hash(p)
            if sub is None:
                return None
            h.update(b"\0behind:" + n + b"\0" + sub.encode())
    staged = _git_bytes(repo, "ls-files", "-s", "-z", *spec)
    if staged is None:
        return None
    for entry in sorted(x for x in staged.split(b"\0") if x):
        meta, _, n = entry.partition(b"\t")
        if not meta.startswith(b"160000 "):
            continue
        sub = _submodule(repo, n)
        if sub is False or (sub is not None and _depth >= SUBMODULE_MAX_DEPTH):
            return None
        if sub is None:
            h.update(b"\0submodule-absent:" + n)
            continue
        fp = fingerprint(sub, None, _depth + 1)
        links, covered = links_key(sub, None, _depth + 1)
        if fp is None or not covered:
            return None
        h.update(b"\0submodule:" + n + b"\0" + fp.encode() + b"\0" + (links or "").encode())
    return h.hexdigest()


@dataclass
class Source:
    path: Path | None  # what the adapter builds from (None: the adapter's own default)
    rev: str | None  # full commit hash
    dirty: bool  # tracked changes or untracked (not ignored) files
    fingerprint: str | None = None  # content identity when dirty (see `fingerprint`)
    links: str | None = None  # content behind tracked symbolic links (see `links_key`)
    reusable: bool = True  # False when the content identity is not covered: no cache, no resume

    @property
    def short(self) -> str | None:
        return self.rev[:7] if self.rev else None

    def to_dict(self) -> dict:
        d = {"core_repo": str(self.path) if self.path else None, "core_rev": self.short,
             "core_rev_full": self.rev, "core_dirty": self.dirty}
        if self.dirty and self.fingerprint:
            d["core_fingerprint"] = self.fingerprint
        if self.links:
            d["core_links"] = self.links
        if not self.reusable:
            d["core_identity_covered"] = False
        return d


def describe(path: Path | None, *, _depth: int = 0) -> Source:
    """Revision, dirtiness and (when dirty) content fingerprint of a source tree (a git checkout).
    Untracked files count: a new source file changes what the adapter builds."""
    if path is None:
        return Source(None, None, True)
    if _git(path, "rev-parse", "--show-toplevel"):
        _check_git_features(path)
    rev = _git(path, "rev-parse", "HEAD")
    if rev is None:
        fp = tree_key(path) if path.is_dir() else None
        return Source(path, None, True, fp, reusable=fp is not None)
    status = _git(path, "status", "--porcelain", "--untracked-files=normal", _NO_IGNORE)
    tracked, raw_dirty = _tracked_state(path, depth=_depth)
    names = _untracked(path, [])
    dirty = bool(status) or status is None or raw_dirty or bool(names) or names is None
    fp = fingerprint(path, None, _depth) if dirty else None
    links, covered = links_key(path)
    return Source(path, rev, dirty, fp, links, reusable=tracked is not None and names is not None and covered and (fp is not None or not dirty))


def resolve_rev(repo: Path, rev: str) -> str:
    with tempfile.TemporaryDirectory(prefix="rvw-source-ref-") as directory:
        capture = Capture(Path(directory) / "capture")
        sha = capture.git_ref(repo, rev)
        capture.verify_tools()
        return sha


def src_cache_dir() -> Path:
    return Path(os.environ.get("RVW_SRC_CACHE", Path.home() / ".cache" / "rvw" / "src"))


DONE_MARK = "rvw-checkout-complete"  # inside .git, so it never shows as a change


@contextlib.contextmanager
def _dest_lock(dest: Path):
    """Exclusive right to publish `dest` (`<cache>/<core>/<sha12>`): an flock on
    `<cache>/.locks/<core>-<sha12>.lock`, outside the core's directory, which then lists only
    checkouts. Each call opens its own file description, so threads of one process exclude each
    other too."""
    locks = dest.parent.parent / ".locks"
    locks.mkdir(parents=True, exist_ok=True)
    f = open(locks / f"{dest.parent.name}-{dest.name}.lock", "a+")
    try:
        fcntl.flock(f.fileno(), fcntl.LOCK_EX)
        yield
    finally:
        f.close()


def _published(dest: Path, sha: str) -> bool:
    """True when `dest` is a finished checkout of `sha`. A finished checkout of another commit
    (two commits sharing the 12-digit prefix) is refused: it would be a wrong tree, not a miss."""
    mark = dest / ".git" / DONE_MARK
    if not mark.is_file():
        return False
    have = mark.read_text().strip()
    if have != sha:
        raise RuntimeError(f"{dest} holds a checkout of {have}, not {sha} (12-digit prefix clash); "
                           f"set RVW_SRC_CACHE to another directory")
    return True


CHECKOUT_SLOTS = 16  # `<sha12>`, `<sha12>-2`, ...: fresh checkouts beside modified ones


def _unusable(s: Source, sha: str) -> str | None:
    """Why a published checkout cannot stand for `sha` (review 15): the done mark says only that the
    clone once finished. Someone may have moved HEAD or edited, added or deleted files since (a
    build in the checkout, a debugging session); results would then be recorded under `sha` while
    coming from another tree. Untracked files count; ignored ones (build outputs) do not."""
    if s.rev != sha:
        return f"HEAD is {s.rev or 'unreadable'}, not {sha}"
    if s.dirty:
        return "it has local changes or untracked files (or git status failed)"
    if not s.reusable:
        return "the content behind its symbolic links cannot be identified"
    return None


def checkout(repo: Path, rev: str, core: str) -> Source:
    """A source tree for `rev`. WORKTREE is the repo as it is (maybe dirty). An explicit
    revision always uses a `git clone --shared` checked out at that
    commit in `$RVW_SRC_CACHE/<core>/<sha12>`: a real repository (adapters may key builds on
    `git rev-parse HEAD`), sharing the repo's objects, and the repo itself is never written to.

    Publication is serialized per destination (review 13): a published checkout may be in use by
    another caller (a build in it), so it is never deleted or replaced; a caller that finds it
    published discards its own temporary clone and uses it. Only an unfinished one (no done mark:
    an interrupted clone, never returned to anyone) is moved away under the lock.

    A published checkout is used only while its HEAD is `sha` and its tree is clean (review 15).
    A modified one is left as it is (it may be in use) and the next slot, `<sha12>-2`, `-3`, ...,
    gets a fresh clean checkout; past CHECKOUT_SLOTS modified ones, the call is refused."""
    if rev == WORKTREE:
        return describe(repo)
    _check_git_features(repo)
    repo = repo.resolve()
    repository = _git(repo, "rev-parse", "--show-toplevel")
    repository = Path(repository).resolve() if repository else repo
    subdirectory = repo.relative_to(repository)
    sha = resolve_rev(repository, rev)
    root = src_cache_dir() / core
    modified = []
    for n in range(CHECKOUT_SLOTS):
        dest = root / (sha[:12] if n == 0 else f"{sha[:12]}-{n + 1}")
        if not _published(dest, sha):
            root.mkdir(parents=True, exist_ok=True)
            with _dest_lock(dest):
                if not _published(dest, sha):
                    _publish(repository, sha, dest)
        try:
            s = describe(dest)
            why = _unusable(s, sha)
        except ValueError as e:
            why = str(e)
        if why is None:
            selected = dest / subdirectory
            if not selected.is_dir():
                raise RuntimeError(f"source directory {subdirectory} is absent at {sha}")
            return Source(selected, s.rev, s.dirty, s.fingerprint, s.links, s.reusable)
        modified.append(f"{dest}: {why}")
    raise RuntimeError(f"no clean checkout of {sha} is left in {root}: " + "; ".join(modified)
                       + ". Remove the modified checkouts once no run uses them, or set RVW_SRC_CACHE "
                       "to another directory")


def _clone_submodules(repo: Path, dest: Path, sha: str, depth: int = 0) -> None:
    """Check out, inside the clone `dest` of `repo` at `sha`, each submodule that `repo` has
    initialized, at the commit recorded in `sha`'s tree. The objects come from `repo`'s own
    submodule checkout (`clone --shared`); nothing is fetched. A submodule `repo` has not
    initialized stays empty, as in `repo` itself. A recorded commit that the local submodule
    lacks is an error: the checkout would not be the requested tree."""
    if depth > SUBMODULE_MAX_DEPTH:
        raise RuntimeError(f"submodules nested deeper than {SUBMODULE_MAX_DEPTH} levels")
    listing = run_git(dest, "ls-tree", "-r", "-z", sha, run=run_group)
    if listing.returncode != 0:
        raise RuntimeError(f"git ls-tree {sha} failed: {(listing.stderr or '').strip()}")
    for entry in (listing.stdout or "").split("\0"):
        meta, _, name = entry.partition("\t")
        if not meta.startswith("160000 "):
            continue
        commit = meta.split()[2]
        source = _submodule(repo, os.fsencode(name))
        if source is None:
            continue
        if source is False:
            raise RuntimeError(f"submodule {name} in {repo} has files but no repository of its own")
        target = dest / name
        if target.exists():
            target.rmdir()      # git leaves an empty directory for an uninitialized submodule
        for args in (["clone", "-q", "--shared", "--no-checkout", str(source), str(target)],
                     ["-C", str(target), "checkout", "-q", "--detach", commit]):
            r = run_git(None, *args, timeout=CLONE_TIMEOUT_S, run=run_group)
            if r.returncode != 0 or r.timed_out:
                why = f"timed out after {CLONE_TIMEOUT_S}s" if r.timed_out else (r.stderr or "").strip()
                raise RuntimeError(f"submodule {name}: git {' '.join(args[:2])} failed: {why}")
        _clone_submodules(source, target, commit, depth + 1)


def _publish(repo: Path, sha: str, dest: Path) -> None:
    """Clone `repo` at `sha` into a temporary directory and rename it to `dest`. The caller holds
    `_dest_lock(dest)` and has checked that `dest` is not published."""
    tmp = Path(tempfile.mkdtemp(prefix=f".{dest.name}.", dir=dest.parent))
    try:
        for args in (["clone", "-q", "--shared", "--no-checkout", str(repo), str(tmp)],
                     ["-C", str(tmp), "checkout", "-q", "--detach", sha]):
            r = run_git(None, *args, timeout=CLONE_TIMEOUT_S, run=run_group)
            if r.returncode != 0 or r.timed_out:
                why = f"timed out after {CLONE_TIMEOUT_S}s" if r.timed_out else (r.stderr or "").strip()
                raise RuntimeError(f"git {' '.join(args[:2])} failed: {why}")
        _clone_submodules(repo, tmp, sha)
        (tmp / ".git" / DONE_MARK).write_text(sha + "\n")
        if _published(dest, sha):    # only a caller that skips the lock (an older rvw) gets here
            shutil.rmtree(tmp, ignore_errors=True)
            return
        if dest.exists() or dest.is_symlink():
            # Unfinished: move it aside first, so a rename never lands on a non-empty directory.
            stale = Path(tempfile.mkdtemp(prefix=f".{dest.name}.stale.", dir=dest.parent))
            dest.rename(stale / "tree")
            shutil.rmtree(stale, ignore_errors=True)
        tmp.rename(dest)
    except BaseException:
        shutil.rmtree(tmp, ignore_errors=True)
        raise
