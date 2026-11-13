# Resources

The machine has 10 cores and 32 GB. Wrap every heavy job in `scripts/with-lock.sh boom …`:
Verilator builds of BOOM, sbt compiles that touch `../spinal-boom-eda`, and BOOM simulations
longer than a minute. Use at most `-j4` for Verilator inside the lock. Small designs and unit tests
need no lock.

The lock (`rvw/src/rvw/common/lock.py`, used by `with-lock.sh`, `rvw regress` and the MCP workers):

- It is an OS file lock (flock) on `$RVW_LOCK_DIR/<name>.flock` (default `~/.cache/rvw-locks`).
  `with-lock.sh NAME CMD` execs CMD with the lock descriptor open, so CMD is the
  `with-lock.sh` process: killing it ends the job, and the lock lasts while CMD or any child that
  inherited the descriptor runs. Python holds it with `rvw.common.lock.held(name)`; children
  started with `rvw.common.proc.run_group` inherit the descriptor.
- Waiters are served in arrival order and print who holds the lock (pid, command, start time)
  and how many wait ahead. `python3 rvw/src/rvw/common/lock.py --status boom` prints the same.
- Re-entry: a job that holds the lock does not wait for itself. `RVW_LOCKS_HELD` lists
  `<name>:<pid>:<fd>:<dev>:<ino>` entries; an entry counts only when this process has that
  descriptor open on the locked file. Being a descendant of the holder without the descriptor
  does not count: such a child waits. Starters pass descriptors and entries together
  (`run_group`, `Job.run`, exec). An adapter that takes the lock again under rvw keeps the
  inherited descriptor open for that child (bash does; Python needs `close_fds=False` or
  `pass_fds`). Threads of one process exclude each other, and a lock belongs to the thread that
  took it: a child started by another thread gets only the locks the process inherited.
- Transition: until every checkout runs this version, holders also take the old mkdir lock
  `<name>.lock/` (marked with a `flock` file), so old and new users exclude each other.
  New holders atomically install a symlink to a private directory with both ownership markers.
  Installation never replaces an existing owner. A stop before installation leaves no public lock.
  `RVW_LOCK_LEGACY=0` turns this off.

The BOOM sources come from `SPINAL_BOOM` (default `../spinal-boom-eda`, a private clone at
`0cb0b69`). Never build or write anything in `../spinal-boom`: another agent works there. Test
ELFs may be read from `../spinal-boom/tests/vm/build`, `../ref/riscv-tests/build/isa`,
`../ref/act4/work/boom-rv64gc/elfs`; benchmark ELFs come from `rvw arch build` (`examples/boom/out/arch/bench`).
