# Native bare-metal benchmarks

Use a local `riscv64-unknown-elf-gcc` built with newlib. Set `SRC` to the
`benchmarks` directory of a riscv-tests checkout. The build uses that checkout's
runtime, startup code and linker script. It does not download sources.

```sh
nice -n 10 make -C Arch/bench SRC=/path/to/riscv-tests/benchmarks \
  BARE_CC=/path/to/riscv64-unknown-elf-gcc BENCHES='median vvadd'
```

The default output is `Arch/bench/build/bare/NAME.riscv`. Set
`BUILD=/absolute/output/directory` to choose another output directory.
`MARCH` defaults to `rv64gc`. Set `MARCH` and `CFLAGS` when the
target needs other compiler settings. A changed compiler, source path or set
of flags forces a rebuild. Use the same ELF bytes for RTL and gem5 runs.

The runtime patch removes HTIF console traffic. It keeps the upstream
`setStats` counter reads. At ROI end, it stores the cycle and instruction
deltas as two 64-bit words at `bench_stats`. It preserves the odd `tohost`
exit encoding. The patch refuses source files whose expected lines changed.

```sh
nice -n 10 scripts/with-lock.sh gem5 /path/to/gem5.opt --outdir=/path/to/run \
  Arch/model.py --description /path/to/core.json --max-ticks 10000000000 \
  Arch/bench/build/bare/median.riscv
```

The description requires `schema: "rvw.arch-core/1"`, `config`, `isa` and
`kind: "o3"`. See the model docstring for its parameter fields. The model
uses a 1 GHz clock and 512 MiB of RAM at `0x80000000`. `memory_latency` is
in cycles. Each tick is 1 ps. The ELF must have `tohost`, `tohost_exit`,
`setStats` and `bench_stats` symbols. Exactly two `setStats` entries must
occur before exit. The model writes `bare.json` with `exit_code` and positive
`bench_stats.cycles` and `bench_stats.instret` on a complete run. Incomplete
runs write a null exit code and an error. The model returns nonzero for an
incomplete run or a nonzero guest exit code.

## Limits and decisions

The model supports one RV64 hart with an O3 CPU. The `isa` field records the
core's ISA. It does not change gem5's ISA support. CPU and cache parameters
must be scalar gem5 parameters. Queue placement follows gem5's operation
classes. Use explicit operation classes for each functional unit.

The default benchmark list contains single-hart workloads with one ROI.
Compiler versions can change code layout and timing. Rebuild and rerun both
sides after a compiler change. gem5 shows trends; RTL is the truth.

## Limit ownership

RV32/in-order runtime: [#13](https://github.com/riscPrint/risc-v-workstation/issues/13). Fitting and measurement work: [#12](https://github.com/riscPrint/risc-v-workstation/issues/12).

Retained limit: The bare-metal ROI runtime and documented compiler/runtime assumptions remain required. Benchmarks do not prove cycle accuracy.

`ftq-branches` is an RV64 RVC microbenchmark for BAC/FTQ experiments. It uses
compressed and full-width conditional branches and checks the path sum. It
requires a RISC-V compiler. It has no host C timing substitute. Its ROI uses
the same two `setStats` markers as the other benchmarks. Compare the same ELF
with coupled and decoupled descriptions. FTQ activity is the required behavior
change. There is no required IPC gain.
