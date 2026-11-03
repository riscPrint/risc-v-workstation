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

## Benchmark co-simulation

Build a small integer benchmark with `rvw arch build --bench vvadd --json`.
Run it with `--rvfi-trace`, then compare the trace with the same ELF:

```sh
RiscvSim/boom/run.sh run --elf vvadd.riscv --out /tmp/bench-run --config small \
  --seed 1 --mem-latency 20 --max-cycles 2000000 --wall-timeout 60 --rvfi-trace
rvw cosim check --core boom --elf vvadd.riscv --trace /tmp/bench-run/rvfi.jsonl --json
RVW_TEST_BENCHMARK_ELF=/absolute/path/vvadd.riscv \
  rvw/.venv/bin/python -m pytest rvw/tests/cosim/test_benchmark_native.py -q
```

The native test holds the BOOM lock. It bounds the whole adapter command,
including lock wait and compilation, to 900 seconds. It requires a conclusive
C1 pass and a nonempty, complete trace match with `end_status = pass`.
`RVW_TEST_BENCHMARK_CONFIG` selects the preset. Its default is `small`.
An absent ELF setting skips this expensive test. A selected missing ELF fails.
The usual Spike synchronization limits still apply. Counter reads in benchmark
timing code can synchronize. A match does not check FP register state or fflags.

## riscv-dv random programs

Generator ownership stays in [#33](https://github.com/riscPrint/risc-v-workstation/issues/33).
Use the upstream [riscv-dv](https://github.com/chipsalliance/riscv-dv) `pyflow`
backend for native Python generation. It needs PyVSC and Boolector. Its pinned
`pyboolector` source distribution must build on the host. If its build fails
with a missing `pyboolector_enums.pxd`, generation is blocked. Do not replace
the generator with an unreviewed random encoder or claim a generated test pass.
Pre-generated programs need their generator revision, target, options and seed.

After generation, compile for the selected core's ISA, ABI, linker layout and
termination protocol. Keep these settings in the core project. A bounded ELF
suite can use:

```toml
[suites.riscv-dv]
dir = "tests/riscv-dv/elfs"
glob = "**/*.elf"
strip_suffix = ".elf"
max_cycles = 1000000
timeout_s = 60
```

A generator's successful termination is not an independent correctness check.
For random streams, record C2 and compare against an independent reference
model. Keep program completion and comparison results separate. Report event
coverage separately. Random instruction counts do not prove queue, cache or
exception stress coverage. Reserved and disabled encodings need an explicit
selected encoding set and expected trap rules. Do not infer those rules from
the DUT. This suite declaration does not implement those campaigns.

## TestRIG

See the [RVFI-DII design](TESTRIG.md). The current ELF adapters do not provide
instruction injection. A new simulation-only core hook is required.
