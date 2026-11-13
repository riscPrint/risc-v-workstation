# Reverse execution API

`reverse_step(manifest, snapshots, out, current=K, target=T, max_seconds=30)`
restores the nearest valid native checkpoint at or before T. It then executes
forward to T and saves a new stopped checkpoint. T must be less than K. The
snapshot port and identity rules are those of `rvw.snapshot-adapter/1`.

Every history entry must validate against the current native identities and
contain a nonnegative `counters.instructions` value. The result lists available
history, the selected checkpoint count, target and requested time limit. A
target before the oldest available checkpoint is refused. This operation does
not move a waveform cursor.

The project port must provide `replay_to_instruction(target, max_seconds=...)`.
It must enforce that budget and cancel native child processes when it expires.
Old ports without this method cannot silently ignore the limit. Position must
equal T before the new snapshot is saved. External effects remain refused.
No bundled Spinal port implements this method yet. Current tests use a fixture
port. Native reverse execution and C2 continuation qualification remain open.

## VexRiscv process port

`examples/vexriscv/rvw/checkpoint_port.py` connects the live Spinal bridge probe
to the shared checkpoint and reverse-step commands. A project manifest selects
this module and supplies absolute `elf` and `launcher` paths under `options`.
Its four `identity_files` groups must include the core RTL sources, native tool
executables, harness sources and ELF inputs. The inner payload also binds the
emitted RTL and compiled harness classes.

The port supports retired-instruction boundaries. It stores an immutable live
state payload while stopped. Forward replay starts a fresh JVM, installs that
state, then captures the target retirement. It never replays from reset to
rebuild the saved prefix. The process group wall budget includes lock waits,
compilation and the bounded suffix run. A timeout is an error.

This port serves checkpoint capture and reverse-step. It has no C1 `finish`
method. General `rvw sim resume` publication remains unsupported. The probe
runs the suffix to `tohost` after capture; the returned snapshot still records
the exact requested boundary. This adds cost but checks terminal completion.
