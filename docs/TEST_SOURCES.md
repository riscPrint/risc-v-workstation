# Test sources through RiscvSim

Use the same C1 adapter for each ELF source. The adapter must load the ELF,
provide the platform it expects, and detect its pass/fail protocol. A file name
or a reference trace alone does not make a program self-checking.

## ACT4 and directed VM tests

Add these tables to any core project's `rvw.toml`. Keep its existing `[core]`
table. Select only tests and configurations that the core implements.

```toml
[suites.act4]
description = "ACT4 self-checking ELFs with Sail signatures"
dir = "tests/act4/elfs"
glob = "**/*.elf"
strip_suffix = ".elf"
max_cycles = 5000000
timeout_s = 900

[suites.vm-tests]
dir = "tests/vm/build"
exclude = ['\.dump$', '\.log$']
max_cycles = 200000
timeout_s = 300
```

```sh
rvw --project /path/to/core regress list --suite act4
rvw --project /path/to/core regress run --suite act4 --config CONFIG --out /tmp/act4-run
rvw --project /path/to/core regress run --suite vm-tests --config CONFIG --out /tmp/vm-run
```

Build ACT4 with that project's UDB configuration, linker script, model macros
and Sail configuration. Use ACT4's `ref_model_exe` to produce the expected
signature. The final ELF must check this independent signature before it
reports success. Never copy a DUT signature into the expected signature.
Do not run an unchecked signature-generation ELF as a self-checking test.
RiscvSim does not validate the build history of an arbitrary ELF.

For the BOOM example, use the core's `act4/build.sh ACT4_CHECKOUT` and select
`ACT4_ELFS=ACT4_CHECKOUT/work/boom-rv64gc/elfs`. Build VM tests with the
core's `tests/vm/build.sh` and set `VM_TESTS` to its output directory.
Build only in a private core checkout. The bundled default uses
`spinal-boom-eda/tests/vm/build`. Explicit `VM_TESTS` also supports a separate
build directory. The ISA, privilege modes, memory map and interrupt devices
must agree with the selected adapter. The suite name adds no device support.

Keep the ACT4 commit, configuration files, Sail version, compiler version,
build command, ELF hashes, execution rules and waivers in the external result
package. Keep C1 results and C3 suite results there too. A suite pass is not a
certification claim. Missing builds are errors, not skipped passes.

## BOOM preset correctness

The adapter maps `medium` and `large` to their own BOOM parameter sets.
Use `run.sh run --config medium` or `--config large` for direct C1 execution.
The bundled `presets` tier selects add, multiply and compressed tests on both:

```sh
rvw regress run --core boom --tier presets --jobs 1 --out /tmp/preset-run
```

A build pass proves elaboration and native compilation only. Each preset needs
its own execution result. A pass on `small` gives no result for another preset.
The short tier is a smoke check. It does not cover the full configuration matrix.
