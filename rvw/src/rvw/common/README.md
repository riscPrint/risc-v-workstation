# rvw.common

Helpers shared by every rvw package. Standard library only.

| Module | What |
|--------|------|
| `project.py` | Project discovery, captured rvw.project/1 parsing and tool paths. |
| `capture.py` | C8 input copies, pinned git refs and tools, explicit environment values and complete cache keys. See the API below. |
| `proc.py` | `run_group` / `kill_group`: run a subprocess in its own process group; a timeout, an error or a cancel stops the whole tree. The run ends when the leader exits, not when its pipes close: then the rest of the group is stopped and captured output is drained for at most `DRAIN_S` (2 s). Children inherit the heavy-job lock descriptors this process holds. |
| `jsonout.py` | `--json` output: `write(obj)` serializes the whole document (strict JSON: no NaN or Infinity) before one write to stdout, else raises `JsonOutputError` (a `ValueError`) with nothing written; `say(prefix, msg)` writes a progress line to stderr. |
| `lock.py` | The machine-wide heavy-job lock (`held(name)`, CLI behind `scripts/with-lock.sh`). Protocol: module docstring and `docs/PLATFORM_CONTRACTS.md` Resources. Runs with any `python3` >= 3.9. |

## Input capture and result generations

```python
from rvw.common.capture import Capture, CaptureError
from rvw.results.generation import publish, open_current, GenerationError

capture = Capture(out / "command-inputs")  # must be a new directory
trace = capture.file(trace_path)            # raw bytes, including gzip/FST
source = capture.tree(source_path)          # git file list, private materialized tree
base = capture.git_ref(repo, "HEAD~1")       # use this full ID in later git commands
solver = capture.tool("yosys")              # invoke str(solver.path), never "yosys"
env = capture.env("SPINAL_VERILATOR_FLAGS")  # use these saved values in the child environment
options = {"depth": 20, "seed": 1}
key = capture.cache_key(options, complete=True)
# complete=True asserts that all inputs, options and relevant environment values are listed.
# Keep complete=False if a tool can read an input or environment value you cannot enumerate.

def build(directory):
    # Read trace.copy and source.copy. Run solver.path through proc.run_group.
    # Write results, the capture record and the cache key in directory.
    # Finish all writes and child processes before returning.
    capture.verify_tools()

identifier = publish(out / "results", build)
reader = open_current(out / "results")       # resolves current once; validates all artifacts
# reader.read_bytes("result.json") checks the bytes against that generation's manifest.
# Record reader.id in a C4 verdict. Keep all later reads on this reader.
```

### API

```python
Capture(root: Path, *, max_tree_bytes: int = 268435456, max_tree_files: int = 100000)
Capture.file(path: Path, name: str | None = None) -> Captured
Capture.files(paths: Iterable[Path]) -> list[Captured]
Capture.tree(path: Path, *, git: bool = True) -> CapturedTree
Capture.git_ref(repo: Path, ref: str) -> str
Capture.tool(name_or_path: str | Path, *, identity_only: bool = False) -> CapturedTool
Capture.env(*names: str) -> dict[str, str | None]
Capture.record() -> dict
Capture.cache_key(options: Mapping, *, complete: bool = False) -> str | None
Capture.verify_tools() -> None
sha256_file(path: str | Path) -> str  # generated files; use Captured.sha256 for inputs
canonical_json(value) -> bytes
read_stable(path, destination=None, limit=None, *, keep=False, single_link=False)

publish(out_dir: Path, build: Callable[[Path], None]) -> GenerationId  # str
open_current(out_dir: Path) -> Generation
Generation.path: Path
Generation.id: str
Generation.manifest_sha256: str
Generation.read_bytes(name: str | Path) -> bytes
Generation.verify() -> None
```

`Captured` is frozen. It exposes `copy: Path`, `sha256: str`, `size: int`,
`source: str`, `resolved: str`, `executable: int`, and
`symlinks: tuple[tuple[str, str], ...]` (lookup path, literal link target).
`source` is the first path as given. `copy` is absolute. `name` sets a safe leaf name.
Repeated calls for the same absolute lookup path return the first capture, including its name.

`CapturedTree` exposes `copy`, `sha256`, `size`, `source`, `resolved`,
`files: tuple[Captured, ...]`,
`directories: tuple[str, ...]`, `symlinks`, `git: bool`, and `deleted: tuple[str, ...]`.
File copies keep their tree paths. `deleted` lists absent tracked paths relative to the tree.
`CapturedTool` exposes `path: Path` (resolved executable), `copy: Path` (saved binary),
`sha256`, `size`, `source` (first name or path), `resolved`, `version: str`, and `symlinks`.
`version` is the combined stdout and stderr text from `--version`.
Use `identity_only=True` for tools without a version command. This records the executable
without running it and sets `version` to an empty string. The first call for a name selects
the mode for that Capture. The tool still appears in `record()["tools"]` and `verify_tools()`.
`read_stable` returns `(sha256, size, stat, data)`. It streams by default. `keep=True`
also returns the bytes. `single_link=True` refuses hardlinks.

`CaptureError` has `status = "inconclusive"` and `cause = "input_not_captured:<name>"`.
A capture error poisons the command's cache key. `record()` is a detached JSON object with
schema `rvw.capture/1`. Its paths under the capture root are relative, so a different private
root does not change the key. Records have stable ordering. They perform no live reads.
`GenerationError` means result evidence is missing, changed or unsupported. Map it to an
error or `inconclusive`. Never accept a partial result after either error.

## Decisions

- A Capture has one command owner and one thread. Consumers read its private copies.
  Files stream through one checked, nonblocking regular-file descriptor into a copy and SHA-256.
  Parse-only JSON readers can keep the checked bytes in memory without a disk copy.
- `tree(git=True)` copies tracked and untracked-not-ignored working-tree files. It does not
  claim a clean commit. `git=False` copies all entries. Both record symlinks, execute bits,
  empty directories and tracked deletions. Broken links, submodules, cycles, special files
  and overlap with the capture root refuse capture. Deleted paths count toward the entry limit.
  Defaults are 256 MiB and 100000 entries. Command copies can double the byte storage.
- Tools run at their resolved installed paths to keep relative library and data lookups valid.
  Version commands must succeed unless `identity_only=True`. `verify_tools()` checks the
  recorded executable before publication. Capture result-changing dependencies separately.
- Git refs resolve once to full commit IDs. Git commands ignore `GIT_*` redirection and
  replacement objects. Capture ignored and external inputs separately when tools read them.
- Cache keys require `complete=True` and a complete input, option and environment inventory.
  Capture failures disable caching. Keys use strict canonical JSON. Object keys must be strings.
  Unset environment values differ from empty strings. Execute with the saved values.
- Results use sealed `generations/<32-hex-id>` directories and an atomic `current` pointer.
  The pointer binds the manifest hash. Explicit ID reads validate the selected generation.
  Readers pin one directory and verify its full inventory. Artifact reads check content hashes.
  Symlinks and hardlinks refuse publication. A failed builder leaves `current` unchanged.
  Builders must finish all writes and child processes before return. Resume creates a new
  generation. Concurrent publishers use the last pointer switch. Old generations remain.
- Process setup and cancellation share the cleanup scope. Cleanup stops the group, reaps the
  leader and closes streams, including after partial selector setup. KILL still follows TERM
  when the leader exits first. Pipe draining is bounded. SIGKILL cannot run Python cleanup.
- Heavy-job locks use `flock` and arrival-order tickets. Dead waiters do not block the queue.
  The wrapper execs its command. Children keep inherited lock descriptors after parent exit.
  A copied environment variable alone cannot re-enter a lock: descriptor identity, a busy
  lock and a no-op flock must agree. Children receive only their starting thread's locks
  and inherited locks. Helper threads must take their own locks before starting children.
- Call `child_env()` for both `env` and `pass_fds` when a child can take the same lock.
  A child without the descriptor must wait. Legacy mkdir-lock compatibility remains enabled
  until old checkouts are retired. Waiters poll every 0.5 s by default.
- The RISC-V decoder checks XLEN, operand positions, selectors and shift widths for Zba,
  Zbb and Zbs. Unknown encodings retain unknown sources.

## Tests

`rvw/.venv/bin/python -m pytest rvw/tests/test_capture.py rvw/tests/test_generation.py -q`

## Known limits

- Callers must enumerate tool dependencies. Legacy run sets use the output ownership lock
  and captured JSON; they do not gain generation content binding.
- Publication does not claim crash durability or collect old generations.
- Read-only permissions protect against ordinary accidental writes. These APIs do not sandbox
  a hostile process with the same user ID. An external removal of a pinned generation refuses
  the reader. Raw reads through `Generation.path` pin the directory but do not validate the
  bytes; use `read_bytes` for claim-bearing reads and `verify` for a full integrity check.

- Re-entry through an inherited descriptor (`RVW_LOCKS_HELD`) checks that the lock is busy, then
  takes it on that descriptor. If the holder releases the lock between the two steps, a stale
  descriptor that a process inherited by mistake can take the lock and keep it until that process
  exits. The window is a few microseconds, and only processes that inherited a lock descriptor are
  affected; ordinary waiters are not.
