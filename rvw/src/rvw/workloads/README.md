# Open workloads

`rvw workloads` builds pinned application kernels and checks their outputs with
Spike or QEMU. It does not run a core or issue a gate verdict. See
[the comparison](../../../../docs/WORKLOADS.md) for selection and sampling limits.

## Default build recipe

The default is six Embench-IoT 1.0 kernels: crc32, matmult-int, slre,
nettle-aes, minver and nbody. The source commit, full compiler version line,
flags, input policy and checker policy are in [default.json](assets/default.json).
This is a smoke set. It is not a compliant Embench score or a SPEC substitute.
Sources are not vendored. Preserve upstream notices when distributing binaries.

```sh
git clone https://github.com/embench/embench-iot.git /path/to/embench
rvw workloads list --json
nice -n 10 rvw workloads build --source /path/to/embench --out /path/to/build
nice -n 10 rvw workloads verify --build /path/to/build/build.json \
  --out /path/to/reference --oracle spike --timeout 120
```

Use `--bench crc32,nbody` to select kernels. Each output directory must be new.
Git archive captures the pinned commit. Working-tree changes have no effect.
The build records source and runtime hashes, compiler path/version/hash,
commands, ELF hashes and sizes. Verification checks the source and ELF hashes,
then requires reference exit 0 and the exact expected stdout hash.
The bare-metal wrapper calls the upstream checker and requires exactly 1.
It sends failure to HTIF for 0 or -1. Stdout must be empty.
FP uses the upstream tolerances. Fast math and FP contraction are disabled.
Startup clears BSS, sets the stack and global pointer, and enables FP.
It supports one active hart. It uses an HTIF exit, not Linux syscalls.

## Local Linux or licensed SPEC hook

Pass `--manifest /path/to/local.json` to `list` or `build`. The same `verify`
command accepts the resulting build report. Linux mode requires a static
RV64 Linux executable and `--oracle qemu-riscv64` (or qemu-riscv64-static).
This user-mode engine is not available in the native macOS QEMU package.
Use a native Linux host. Dynamic sysroots are not supported by this first flow.

The JSON manifest has schema `rvw.workloads/1`, a nonempty `compiler_version`
(full first `CC --version` line), and a nonempty `workloads` list.
Pin sources with a full Git `revision`, or a `source_sha256` tree hash.
Use `rvw.workloads.core.tree_hash(Path(...))` on an extracted source tree.
This hash includes relative file names, contents, execute bits and internal
symlink targets. External and broken symlinks are errors.
Each workload has:

| Field | Meaning |
|---|---|
| `id` | Unique lowercase name; letters, digits, underscore and hyphen |
| `mode` | `bare` for Spike or `linux` for QEMU user mode |
| `build` | Nonempty argv array; no shell evaluation |
| `args` | Run argv array; paths are relative to the captured source tree |
| `stdout_sha256` | Exact expected stdout SHA-256; reference exit must be 0 |

Build arguments support `{cc}`, `{source}`, `{out}` and `{assets}`.
Write the executable to `{out}/workload.elf`. Keep generated files under
`{out}`. Source files must stay unchanged. Use a checked-in build script for
multi-step builds. Pin the script, input data and checker in the source tree.
Run inputs get a separate copy for each workload. Generated databases and
other run outputs cannot change the captured input tree.

For SPEC CPU2017, keep all licensed sources, inputs, result files and manifests
outside this repository. Supply a local wrapper and pin its complete source
and input tree. The wrapper builds the selected benchmark for RV64GC Linux.
Run the application through a guest driver that invokes the official output
validator. Make the driver return nonzero on any invalid or absent output.
Have it print a fixed validation line. Pin that line's hash in the manifest.
Do not hash timing text or use a successful compiler exit as a result check.
No SPEC files are downloaded or distributed. No SPEC scores are calculated.
The hook is the same manifest flow; it does not implement or qualify `runcpu`.

## Decisions and limits

- Keep the runner generic. No core signals or presets are embedded.
- No implicit downloads, compiler substitution or cache reuse occur.
- A failed command leaves an incomplete directory without build.json.
  Use a new output path for the next attempt.
- The default compiler is RV64 GCC 15.1.0 with the exact build line in the pin.
  A different build needs a separate explicit manifest. The report hashes its
  executable. Keep the complete toolchain distribution with the experiment.
  GCC's assembler, linker, newlib and sysroot are not independently captured.
- A local build script's host dependencies are the caller's responsibility.
  The manifest hook is not a complete C8 build capture or sandbox.
- Only stdout and exit status are checked automatically. Use a guest checker
  for file outputs. A driver that prints success without checking is invalid.
- The Linux and SPEC hooks have unit tests. Native Linux application builds,
  SPEC runs, RTL runs and sampling restore are not qualified by those tests.
- MCP bindings and automatic sampling are not implemented.

Use `verify --trace` with Spike to retain its instruction log in each stderr
file and add dynamic opcode categories to verify.json. Counts include startup,
checker and compressed instructions. FP memory instructions occur in both the
FP and load/store categories. Conditional branch transitions give taken counts,
not predictor misses. The profile leaves cache and predictor miss fields null.
Instruction logs can use much more disk space than the ELFs.

## Additional open recipes

Use `--recipe embench|riscv-tests|coremark|zstd` with `list` or `build`.
A recipe and a local `--manifest` are mutually exclusive. Sources stay outside
the workstation. Recipes pin full source revisions and the compiler line.
They do not download sources. Use the matching source checkout, including
its declared dependencies. Each output directory must be new.

```sh
rvw workloads list --recipe riscv-tests
rvw workloads build --recipe riscv-tests --source /path/to/riscv-tests \
  --bench median,dhrystone --out /path/to/bench-build
rvw workloads build --recipe coremark --source /path/to/coremark \
  --out /path/to/coremark-build
rvw workloads build --recipe zstd --source /path/to/zstd \
  --out /path/to/zstd-build
rvw workloads verify --build /path/to/bench-build/build.json \
  --out /path/to/bench-check --oracle spike --timeout 60
```

The riscv-tests recipe includes median, qsort, rsort, towers, vvadd, memcpy,
multiply, Dhrystone and spmv. It reuses the existing architecture Makefile and
runtime patch. Those files are copied into the captured assets before use.
The manifest pins the environment repository separately. The local source's
`env` checkout must contain that revision. Console output is suppressed by
the existing runtime. Upstream self-checks still determine the HTIF exit.

The CoreMark recipe is a short algorithm workload. It calls the upstream
list, matrix and state kernels for one iteration with the 6k reference seeds.
It checks the upstream CRCs `d4b0`, `be52` and `5e47`. The only port-header
change selects a pointer-sized integer for RV64. The upstream algorithms stay
unchanged. This driver omits the official timing flow. It produces no
CoreMark score and is not a compliant CoreMark measurement.

The zstd recipe builds the pinned v1.5.7 compression and decompression library.
It compresses a deterministic 256 KiB input with a static level-1 context. It
requires compressed size below half the input size, then checks every restored
byte. Static contexts avoid a bare-metal heap. This is a round-trip self-check,
not independent decoder validation. No SPEC source or licensed input is used.

Manifests can add `dependencies`, mapping source-relative Git repository paths
to full revisions. Build archives each dependency into the source capture.
`runtime_files` can name workstation-relative files to copy into
`assets/workstation/`. The assets hash includes those copies. Source and
runtime paths cannot escape their roots. Builders use Python 3 and the pinned
compiler. Python and host build utilities remain local dependencies.

The cancellable MCP tools are `workloads_list`, `workloads_build` and
`workloads_verify`. They select the same recipes and checkers as the CLI.

## Default evaluation set

`rvw workloads evaluate` uses the default evaluation manifest in
`assets/evaluation.json`. It selects Embench crc32, matmult-int and slre,
CoreMark's checked algorithm driver, qsort, rsort and zstd compression and
decompression. SLRE supplies a regular-expression interpreter-style kernel.
The source revisions and compiler pins come from the existing recipes.
The CoreMark driver is not a compliant CoreMark score.

```sh
nice -n 10 rvw workloads evaluate \
  --source embench=/path/to/embench --source coremark=/path/to/coremark \
  --source riscv-tests=/path/to/riscv-tests --source zstd=/path/to/zstd \
  --out /path/to/evaluation --timeout 1800 --json
```

Sources stay outside this repository. The command does not download them.
Use `--build RECIPE=BUILD_JSON` to reuse a verified recipe build. Default-set
build manifests must match the pinned recipes. Use `--trace WORKLOAD=C2` to
reuse a complete existing Spike capture. The C2 ELF path must match the
verified workload. An ELF hash is also checked when the producer supplies it.
Otherwise the report states `trace_elf_binding: producer_path`.

The command checks outputs with Spike. It then captures complete C2 from the
Spike shim. The additive `RVW_SPIKE_MEMORY_LOG=1` mode keeps diagnostic text in
memory during these captures. The normal shim path still uses its file log.
Both modes produced identical C2 bytes in the chain and ECALL controls.

The command selects up to three SimPoint-style intervals of 2,000 instructions
with seed 1. Each point gets up to 200 warmup instructions. Both reference
models use those same points and weights. The sampler validates the complete
C2 stream but decodes only selected warmup and measurement windows. It retains
those windows in memory. It does not retain the full decoded instruction list.
The optional raw `source_c2_sha256` binds points directly to complete C2 bytes.
Older point files still use the normalized ComponentSims hash.

`report.json` and `report.md` give sampled IPC for the Zen-5-like and M1-like
reference descriptions. These are approximate RISC-V timing configurations.
They do not emulate either commercial ISA or establish measured commercial
CPU performance. Their CSR and fence latencies are explicit one-cycle
estimates. Sampling error against full timing remains unmeasured. The MCP job
is `workloads_evaluate`. A custom `--manifest` can select another workload set.
Its model paths resolve beside that manifest.

The own-model projection uses the shared CPU dimensions and the explicit
`ooo` table. It does not use gem5-only cache and predictor tables. These two
reference files currently share fixed execution latencies and the sequential
branch policy. Their capacity differences need not change a sampled result.

The [seven-workload native sample](../../../../Arch/ooo/evaluation/README.md)
contains complete Spike traces from 2026-11-13 and sampled timing for both
reference descriptions. Input hashes and source pins accompany the table.
Sampling error against full timing remains unmeasured.

Evaluation models with the same custom instruction definitions now share one
complete C2 validation and decoded sample windows. Each model gets fresh timing
and component state. A raw source hash check precedes reuse. Different custom
instruction definitions get separate validation. Report formats stay unchanged.

## Checked RTL benchmark table

`rvw workloads run --project CORE --source RISCV_TESTS --out RUN_ROOT`
builds the pinned riscv-tests recipe for the project. Put project settings in
`rvw/bench.json`, or use `--settings FILE`. Settings use schema
`rvw.rtl-bench-settings/1`, `programs` (recipe IDs), and `target` with `march`,
`abi`, `ram_base` and `ram_size`. Optional fields are `cc`, `source`,
`max_cycles` and `probes`. RAM values are linker integer expressions.
The linker checks program size plus 128 KiB for runtime stacks.

The command runs one C1 adapter at a time. It requires a C1 pass from the
program self-check and matching C1 input fields. Dhrystone is `no_checks`
until its printed expected values have an executable checker.
The table includes failed programs and diagnostics. IPC covers startup,
program work and the checker. It is not an official benchmark score.
`--repeats 2` checks exact instruction and cycle repeatability.
`--resume` reuses completed rows only with the same settings, tracked
revision and edits, declared environment, options and unchanged ELF hashes.
Untracked core inputs are outside this resume identity. Keep them fixed.
Interrupted builds need a fresh output directory. Completed builds and rows
resume after interruption. Each adapter has a wall limit below 120 seconds.
Builds can need a separate warm compile before the campaign on a loaded host.

Keep RUN_ROOT outside Git. `report.json` and `report.md` are the result tables.
No waves or instruction traces are requested. Optional probe events are
summarized with the existing top-down reader, then removed. Missing top-down
bindings remain explicit. MCP tool: `workloads_run`.

Set `bounded: true` for the example RTL smoke sizes. These variants use the
first 128 pinned sort inputs, Python-sorted expected results, the first eight
SpMV rows with unchanged expected values, and ten Dhrystone iterations.
Override `sort_size`, `spmv_rows` and `dhrystone_runs` in `target`.
The Dhrystone variant checks all printed final scalar, record and string
values. It runs one fixed loop count. It is not an official Dhrystone score.
`runtime: user-counters` uses a CSR-free single-hart startup and user counter
reads for cores without machine CSRs. C1 still supplies the full-run counts.

The runner reuses C1 `run-many` with one worker. Each manifest entry has its
own wall limit. The launch budget also covers adapter setup. Completed table
rows resume; raw results from an interrupted batch are not reused.

## Compare RTL tables

`rvw workloads compare A/report.json B/report.json` reports per-program IPC
changes and top-down fraction changes. MCP tool: `workloads_compare`.
Both tables need at least two passing samples with identical cycles and
instructions for each program. The command checks the samples itself.
A stored `deterministic` flag alone is not sufficient. Missing or failed
programs and changed instruction counts are inconclusive. IPC differences
can still be shown with an unverified noise check. Exit 3 means inconclusive.
Different ELF hashes are explicit, so two compiled revisions can be compared.
Use the same program inputs and ISA. Compare top-down fractions only when the
project uses the same slot partition. Differences are fractions, not percent.
