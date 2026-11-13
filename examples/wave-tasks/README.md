# Wave debug tasks

A head-to-head protocol for debug tools (`rvw.debug-tasks/1`, issue #297). Each task is one
question, the `rvw` command that answers it, and checks on its JSON output.

```sh
rvw wave bench examples/wave-tasks/tasks.json --var db=/path/to/gcd.db
```

`gcd.db` is the GCD design database used by the tests: build it from
`rvw/tests/data/gcd.sql` (`sqlite3 gcd.db < gcd.sql` after replacing `@REPO@` with this
checkout). The waves are small hand-written fixtures.

## Protocol

1. Answer each `question` with the other tool (for example Verdi) on the same files, without
   using rvw output. Record `tool`, wall `seconds` from opening the files to the answer, the
   number of `steps` (commands, clicks or dialogs), `solved` and `notes` in its `reference`.
2. Run `rvw wave bench`. It times each rvw command and checks the expectations.
3. A comparison is reported only for tasks with a recorded reference. rvw times are command
   wall time; reference times include human steps. Report both with the host and versions.

No reference results are recorded yet.
