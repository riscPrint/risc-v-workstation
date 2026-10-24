"""The machine-wide heavy-job lock, one implementation for `scripts/with-lock.sh` and rvw.

    scripts/with-lock.sh boom sbt -batch ...          # shell: runs the command holding `boom`
    python3 -m rvw.common.lock boom CMD...            # the same, without the shell wrapper
    python3 -m rvw.common.lock --status boom          # who holds it, who waits
    with rvw.common.lock.held("boom"): ...            # Python: holds it for the block

How it works (files in `$RVW_LOCK_DIR`, default `~/.cache/rvw-locks`):

- `<name>.flock` is locked with flock(2). The kernel drops the lock when the last descriptor of
  that open file is closed, so the lock lives exactly as long as the processes that hold the
  descriptor: no pid files, no stale-lock recovery. The command started by `with-lock.sh` is
  exec'd with the descriptor open, and its children inherit it; killing the wrapper kills the
  job (same process), and children that outlive it keep the lock until they exit.
- `<name>.queue/` holds one ticket file per waiter, each locked by its waiter. Waiters take the
  lock in arrival order; tickets of dead waiters are unlocked, and are skipped and removed.
- `<name>.owner` (JSON: pid, command, start time) says who holds the lock. Waiters print it.
- Re-entry: a job that holds the lock does not wait for itself. A process counts as holding
  `<name>` when (1) the same thread already holds it, or (2) `RVW_LOCKS_HELD` has an entry
  `<name>:<pid>:<fd>:<dev>:<ino>` whose descriptor is open in this process and is the one that
  holds the (busy) lock (with-lock.sh sets it for the command; `held()` sets it for later
  children); re-entry is decided before the caller opens a descriptor of its own. Being a child
  of the holder is not enough (review 4): without the inherited descriptor, the child's work would
  not keep the lock once the parent releases it, so such a child waits like anyone else. Callers
  that start children which take the lock again pass the descriptors and the variable together
  (`child_env()` for `env` and `pass_fds`, as `rvw.common.proc.run_group`, `rvw.mcp.jobs.Job.run`
  and the regress runner do; a shell command inherits both through exec). A lock belongs to the
  thread that took it: a child of another thread gets only inherited locks, not it (review 10).
- Compatibility: checkouts that still run the old `with-lock.sh` use a directory
  `<name>.lock/pid` (mkdir lock). After taking the flock, a holder also waits for and takes that
  directory (marked with a `flock` file), so old and new users exclude each other. Set
  `RVW_LOCK_LEGACY=0` to skip this once no old checkout is left.

Standard library only and Python >= 3.9, so `with-lock.sh` can run it with any `python3`.
"""
from __future__ import annotations

import contextlib
import fcntl
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import threading
import time
from pathlib import Path

ENV = "RVW_LOCKS_HELD"
REPORT_EVERY_S = 300.0
_NAME = re.compile(r"^[A-Za-z0-9_.-]+$")

_state = threading.Lock()
_mine: dict = {}               # fd -> (dev, ino): lock descriptors this process image opened and holds
_owner: dict = {}              # fd -> thread ident that took it (a lock belongs to its thread)
_local = threading.local()     # .depth: {(dev, ino): n} for same-thread nesting


def lock_dir(override=None) -> Path:
    if override:
        return Path(override)
    return Path(os.environ.get("RVW_LOCK_DIR") or Path.home() / ".cache" / "rvw-locks")


class _Paths:
    def __init__(self, name: str, directory=None):
        if not _NAME.match(name or ""):
            raise ValueError(f"bad lock name {name!r} (letters, digits, '_', '.', '-')")
        self.name = name
        self.dir = lock_dir(directory)
        self.dir.mkdir(parents=True, exist_ok=True)
        self.file = self.dir / f"{name}.flock"
        self.owner = self.dir / f"{name}.owner"
        self.queue = self.dir / f"{name}.queue"
        self.legacy = self.dir / f"{name}.lock"


# ------------------------------------------------------------------------------------ helpers

def _say(log, text: str) -> None:
    if log:
        print(f"rvw-lock: {text}", file=log, flush=True)


def _alive(pid: int) -> bool:
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    return True


def _ancestors() -> set:
    """Strict ancestors of this process (one `ps` call)."""
    parents = {}
    try:
        out = subprocess.run(["ps", "-A", "-o", "pid=,ppid="], capture_output=True, text=True,
                             timeout=10).stdout
        for line in out.splitlines():
            parts = line.split()
            if len(parts) == 2:
                parents[int(parts[0])] = int(parts[1])
    except (OSError, ValueError, subprocess.TimeoutExpired):
        pass
    seen, pid = set(), os.getppid()
    while pid > 1 and pid not in seen:
        seen.add(pid)
        pid = parents.get(pid, 0)
    return seen


def _try_flock(fd: int) -> bool:
    try:
        fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        return True
    except OSError:
        return False


def _ident(fd: int):
    st = os.fstat(fd)
    return (st.st_dev, st.st_ino)


def _read_owner(paths: _Paths):
    try:
        return json.loads(paths.owner.read_text())
    except (OSError, ValueError):
        return None


def _write_owner(paths: _Paths, cmd: str) -> None:
    tmp = paths.dir / f".{paths.name}.owner.{os.getpid()}.{threading.get_ident()}"
    tmp.write_text(json.dumps({"pid": os.getpid(), "cmd": cmd[:300],
                               "since": time.strftime("%Y-%m-%d %H:%M:%S")}) + "\n")
    os.replace(tmp, paths.owner)


def _busy(paths: _Paths) -> bool:
    """True when some open file description holds the flock (checked through a fresh one)."""
    return _busy_file(paths.file)


def _fd_path(fd: int) -> str | None:
    """The path of an open descriptor (macOS F_GETPATH, Linux /proc), or None."""
    try:
        if hasattr(fcntl, "F_GETPATH"):
            return fcntl.fcntl(fd, fcntl.F_GETPATH, bytes(1024)).rstrip(b"\0").decode()
        return os.readlink(f"/proc/self/fd/{fd}")
    except (OSError, ValueError):
        return None


def _busy_file(path) -> bool:
    fd = os.open(path, os.O_RDWR | os.O_CREAT, 0o666)
    try:
        if _try_flock(fd):
            fcntl.flock(fd, fcntl.LOCK_UN)
            return False
        return True
    finally:
        os.close(fd)


def _command() -> str:
    return " ".join(sys.argv) or "python"


# ------------------------------------------------------------------------------------ re-entry

def _tokens():
    for tok in os.environ.get(ENV, "").split(","):
        parts = tok.split(":")
        if len(parts) == 5:
            try:
                yield parts[0], int(parts[1]), int(parts[2]), (int(parts[3]), int(parts[4]))
            except ValueError:
                continue


def _inherited_fd(paths: _Paths, ident):
    """A descriptor of the locked file that this process inherited (rule 2), or None.

    An entry counts only while the lock is busy (checked through a fresh open file description)
    and its descriptor can re-lock it: flock on the holding description is a no-op that succeeds,
    on any other one it fails. With the lock free, a leaked entry whose descriptor happens to be
    open on the lock file (or reuses that number) would otherwise "re-lock" a free lock and be
    taken as re-entry (review 2, N2)."""
    with _state:
        own = set(_mine)
    for tname, _pid, fd, tident in _tokens():
        if tname == paths.name and tident == ident and fd not in own:
            if _valid_inherited(fd, ident, paths.file):
                return fd
    return None


def _valid_inherited(fd, ident, path) -> bool:
    """Check descriptor identity, a busy lock and a no-op flock on the holding description."""
    try:
        if _ident(fd) != ident or path is None:
            return False
        info = os.stat(path)
        return ((info.st_dev, info.st_ino) == ident and _busy_file(path) and _try_flock(fd))
    except OSError:
        return False


def _depth() -> dict:
    d = getattr(_local, "depth", None)
    if d is None:
        d = _local.depth = {}
    return d


def _reentrant(paths: _Paths, ident) -> str | None:
    """Why this process already holds the lock, or None."""
    if _depth().get(ident):
        return "same thread"
    if _inherited_fd(paths, ident) is not None:
        return f"inherited descriptor ({ENV})"
    return None


# ------------------------------------------------------------------------------------ queue

def _enqueue(paths: _Paths):
    paths.queue.mkdir(exist_ok=True)
    tid = threading.get_ident()
    tmp = paths.queue / f".new-{os.getpid()}-{tid}-{time.time_ns()}"
    fd = os.open(tmp, os.O_RDWR | os.O_CREAT | os.O_EXCL, 0o644)
    fcntl.flock(fd, fcntl.LOCK_EX)
    # Locked before it becomes visible, so nobody can take a live ticket for a dead one.
    ticket = paths.queue / f"{time.time_ns():020d}-{os.getpid()}-{tid}"
    os.rename(tmp, ticket)
    return fd, ticket


def _ticket_live(path: Path, min_age_s: float = 0.0) -> bool:
    """A ticket is live while its waiter holds its flock. Dead ones are removed."""
    try:
        fd = os.open(path, os.O_RDONLY)
    except FileNotFoundError:
        return False
    try:
        if not _try_flock(fd):
            return True
        if min_age_s:
            try:
                if time.time() - os.fstat(fd).st_mtime < min_age_s:
                    return True
            except OSError:
                return True
        with contextlib.suppress(FileNotFoundError):
            os.unlink(path)
        return False
    finally:
        os.close(fd)


def _ahead(paths: _Paths, mine: str) -> int:
    n = 0
    for entry in sorted(os.listdir(paths.queue)):
        if entry.startswith("."):
            _ticket_live(paths.queue / entry, min_age_s=10.0)   # half-created by a dead waiter
            continue
        if entry >= mine:
            break
        if _ticket_live(paths.queue / entry):
            n += 1
    return n


def _holder_text(paths: _Paths) -> str:
    owner = _read_owner(paths)
    if isinstance(owner, dict) and isinstance(owner.get("pid"), int):
        what = f"pid {owner['pid']} since {owner.get('since', '?')}: {owner.get('cmd', '?')}"
        return what if _alive(owner["pid"]) else f"children of exited {what}"
    return "an unknown process (no owner record)"


def _wait_turn(paths: _Paths, fd: int, poll_s: float, log) -> None:
    tfd, ticket = _enqueue(paths)
    try:
        said, said_at = None, 0.0
        while True:
            ahead = _ahead(paths, ticket.name)
            if ahead == 0 and _try_flock(fd):
                return
            text = f"waiting for {paths.name}: held by {_holder_text(paths)}; {ahead} ahead in queue"
            if text != said or time.monotonic() - said_at > REPORT_EVERY_S:
                _say(log, text)
                said, said_at = text, time.monotonic()
            time.sleep(poll_s)
    finally:
        with contextlib.suppress(FileNotFoundError):
            os.unlink(ticket)
        os.close(tfd)


# ------------------------------------------------------------------------------------ legacy

def _legacy_enabled() -> bool:
    return os.environ.get("RVW_LOCK_LEGACY", "1") not in ("0", "", "no", "false")


def _legacy_take(paths: _Paths, poll_s: float, log) -> bool:
    """Called holding the flock. Takes `<name>.lock/` from old-style users. Returns True when this
    process owns the directory (and must remove it), False when an old-style ancestor holds it."""
    said = None
    while True:
        prepared = Path(tempfile.mkdtemp(prefix=f'.{paths.name}-legacy-', dir=paths.dir))
        try:
            (prepared / "flock").write_text("")
            (prepared / "pid").write_text(f"{os.getpid()}\n")
            # symlink(2) installs a complete directory view without replacing any
            # existing owner, including an empty old-style directory. A stop before
            # this call can leave only a private orphan, never an empty public lock.
            paths.legacy.symlink_to(prepared.name, target_is_directory=True)
            return True
        except FileExistsError:
            pass
        finally:
            if not paths.legacy.is_symlink() or os.readlink(paths.legacy) != prepared.name:
                shutil.rmtree(prepared, ignore_errors=True)
        if (paths.legacy / "flock").exists():
            # Left by a flock holder; we hold the flock now, so that holder is gone.
            (paths.legacy / "pid").write_text(f"{os.getpid()}\n")
            return True
        try:
            pid = int((paths.legacy / "pid").read_text().strip())
        except (OSError, ValueError):
            pid = None
        if pid is not None and not _alive(pid):
            shutil.rmtree(paths.legacy, ignore_errors=True)
            continue
        if pid is not None and pid in _ancestors():
            return False
        if pid is None:
            try:
                if time.time() - paths.legacy.stat().st_mtime > 30:
                    shutil.rmtree(paths.legacy, ignore_errors=True)   # never got a pid
                    continue
            except OSError:
                continue
        text = f"waiting for {paths.name}: held by pid {pid} through the old mkdir lock {paths.legacy}"
        if text != said:
            _say(log, text)
            said = text
        time.sleep(poll_s)


def _legacy_release(paths: _Paths) -> None:
    try:
        if int((paths.legacy / "pid").read_text().strip()) == os.getpid() and (paths.legacy / "flock").exists():
            if paths.legacy.is_symlink():
                target = paths.legacy.resolve()
                paths.legacy.unlink()
                # Only remove a private directory created by this implementation.
                if target.parent == paths.dir.resolve() and target.name.startswith(f'.{paths.name}-legacy-'):
                    shutil.rmtree(target, ignore_errors=True)
            else:
                shutil.rmtree(paths.legacy, ignore_errors=True)
    except (OSError, ValueError):
        pass


# ------------------------------------------------------------------------------------ acquire

def _acquire(paths: _Paths, poll_s: float, log, cmd: str):
    """Returns (fd, ident, owns_legacy) holding the flock, or (None, ident, reason) on re-entry."""
    # Re-entry is decided before this call opens its own descriptor, so a leaked RVW_LOCKS_HELD
    # entry cannot name (by number) the descriptor about to be opened here (review 2, N2).
    os.close(os.open(paths.file, os.O_RDWR | os.O_CREAT, 0o666))
    st = os.stat(paths.file)
    ident = (st.st_dev, st.st_ino)
    why = _reentrant(paths, ident)
    if why:
        return None, ident, why
    fd = os.open(paths.file, os.O_RDWR | os.O_CREAT, 0o666)
    try:
        if _ident(fd) != ident:
            raise OSError(f"{paths.file} was replaced while taking the lock")
        _wait_turn(paths, fd, poll_s, log)
        owns_legacy = _legacy_take(paths, poll_s, log) if _legacy_enabled() else False
        _write_owner(paths, cmd)
        return fd, ident, owns_legacy
    except BaseException:
        with contextlib.suppress(OSError):
            os.close(fd)
        raise


def _token(name: str, fd: int, ident) -> str:
    return f"{name}:{os.getpid()}:{fd}:{ident[0]}:{ident[1]}"


def _env_add(token: str) -> None:
    cur = [t for t in os.environ.get(ENV, "").split(",") if t]
    os.environ[ENV] = ",".join(cur + [token])


def _env_remove(token: str) -> None:
    cur = [t for t in os.environ.get(ENV, "").split(",") if t and t != token]
    if cur:
        os.environ[ENV] = ",".join(cur)
    else:
        os.environ.pop(ENV, None)


_STDERR = object()


@contextlib.contextmanager
def held(name: str | None, directory=None, poll_s: float = 0.5, log=_STDERR):
    """Hold lock `name` for the duration of the block (`None`: no lock). Re-entrant (see module
    doc). While held, `RVW_LOCKS_HELD` in os.environ names it for children started later, and
    `held_fds()` lists the descriptor so `rvw.common.proc.run_group` children keep the lock."""
    if not name:
        yield
        return
    if log is _STDERR:
        log = sys.stderr
    paths = _Paths(name, directory)
    fd, ident, extra = _acquire(paths, poll_s, log, _command())
    depth = _depth()
    if fd is None:
        depth[ident] = depth.get(ident, 0) + 1
        try:
            yield
        finally:
            depth[ident] -= 1
            if not depth[ident]:
                del depth[ident]
        return
    token = _token(name, fd, ident)
    with _state:
        _mine[fd] = ident
        _owner[fd] = threading.get_ident()
        _env_add(token)
    depth[ident] = 1
    try:
        yield
    finally:
        depth.pop(ident, None)
        with _state:
            _mine.pop(fd, None)
            _owner.pop(fd, None)
            _env_remove(token)
        owner = _read_owner(paths)
        if isinstance(owner, dict) and owner.get("pid") == os.getpid():
            with contextlib.suppress(OSError):
                paths.owner.unlink()
        if extra is True:
            _legacy_release(paths)
        os.close(fd)   # no LOCK_UN: children that inherited the descriptor keep the lock


def held_fds() -> list:
    """Lock descriptors the calling thread may pass to a child, for `pass_fds` so children keep
    the lock as long as they run: the locks this thread took, and those this process inherited
    (with-lock.sh, a parent's `pass_fds`). A lock another thread of this process took is not
    included (review 10): that thread's work owns it, and a child of an unrelated thread (an MCP
    job, a worker) must wait for it like anyone else."""
    me = threading.get_ident()
    with _state:
        fds = {fd for fd, t in _owner.items() if t == me}
        others = set(_mine) - fds
    for tname, _pid, fd, tident in _tokens():
        if fd in fds or fd in others:
            continue
        if _valid_inherited(fd, tident, _fd_path(fd)):
            fds.add(fd)
    return sorted(fds)


def child_env(env=None) -> tuple:
    """(environment, pass_fds) for a child of the calling thread: `env` (default os.environ)
    with `RVW_LOCKS_HELD` holding exactly the entries of the descriptors in `held_fds()`. Entries
    of other threads' locks, stale entries and entries of an `env` snapshot are dropped; current
    entries are kept even when `env` was copied before the lock was taken (review 5)."""
    fds = held_fds()
    out = dict(os.environ if env is None else env)
    out.pop(ENV, None)
    keep = set(fds)
    mine = [f"{name}:{pid}:{fd}:{ident[0]}:{ident[1]}"
            for name, pid, fd, ident in _tokens() if fd in keep]
    if mine:
        out[ENV] = ",".join(mine)
    return out, fds


def status(name: str, directory=None) -> dict:
    paths = _Paths(name, directory)
    queue = []
    if paths.queue.is_dir():
        queue = [e for e in sorted(os.listdir(paths.queue)) if not e.startswith(".")
                 and _ticket_live(paths.queue / e)]
    busy = _busy(paths)
    d = {"name": name, "dir": str(paths.dir), "held": busy, "waiting": len(queue)}
    if busy:
        d["owner"] = _read_owner(paths)
    if paths.legacy.is_dir():
        d["legacy_dir"] = str(paths.legacy)
        try:
            pid = int((paths.legacy / "pid").read_text().strip())
        except (OSError, ValueError):
            pid = None
        if pid is not None and _alive(pid) and not (paths.legacy / "flock").exists():
            d["held"] = True   # an old-style with-lock.sh holds it; new users wait for it too
            d["legacy_pid"] = pid
    return d


# ------------------------------------------------------------------------------------ CLI

USAGE = "usage: with-lock.sh NAME CMD [ARGS...]   |   python3 -m rvw.common.lock --status NAME"


def main(argv=None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    if argv[:1] == ["--status"] and len(argv) == 2:
        print(json.dumps(status(argv[1]), indent=1))
        return 0
    if argv[:1] == ["--"]:
        argv = argv[1:]
    if len(argv) < 2 or argv[0].startswith("-"):
        print(USAGE, file=sys.stderr)
        return 2
    name, cmd = argv[0], argv[1:]
    try:
        paths = _Paths(name)
    except ValueError as e:
        print(f"rvw-lock: {e}", file=sys.stderr)
        return 2
    fd, ident, _ = _acquire(paths, float(os.environ.get("RVW_LOCK_POLL_S", "0.5")), sys.stderr,
                            " ".join(cmd))
    if fd is not None:
        os.set_inheritable(fd, True)
        _env_add(_token(name, fd, ident))
    sys.stdout.flush()
    try:
        os.execvp(cmd[0], cmd)     # same pid: the command holds the descriptor, nothing else does
    except OSError as e:
        print(f"rvw-lock: cannot run {cmd[0]}: {e}", file=sys.stderr)
        return 127
    return 0


if __name__ == "__main__":
    sys.exit(main())
