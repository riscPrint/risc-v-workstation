# Compiler scheduling models

This first slice generates partial LLVM and GCC target fragments. It measures
integer streams through a project's C1 adapter. It reports cycle errors for
each class against a built-in llvm-mca CPU. It does not validate the generated
model with stock llvm-mca. See [the design](../docs/design/sched-models.md).

```sh
rvw arch sched-generate examples/vexriscv/sched/rv32im.json --out /tmp/sched-gen --json
rvw arch sched-measure examples/vexriscv/sched/rv32im.json \
  --project /path/to/VexRiscv/rvw.toml --out /tmp/sched-vex \
  --mca /opt/homebrew/opt/llvm/bin/llvm-mca --timeout 900 --json
```

Use a fresh output directory. Set `RVW_HOME`, `RVW_PYTHON`, the native tool PATH
and JDK 21 as required by the project adapter. Use the current example adapter
build, which consumes RiscvSim through `ProjectRef`. An older source-copy build
cannot resolve the current RiscvSim dependencies. Keep adapter data in a separate
project directory if the core checkout is shared.

`--cc` selects native bare-metal GCC. `--count` selects the smaller stream size
(default 32, range 16 to 256). The larger stream has twice that count. Each class
runs in dependent and independent modes. Independent mode rotates eight result
registers. Each result register is also a source; this avoids false throughput
claims from discarded outputs. Only add, xor, and, or and mul are supported.
MCA sees the exact ROI assembly with one iteration. RTL measures the span between
the first and last ROI retirement. The report subtracts smaller from larger
spans and divides by count. It includes raw spans and signed percent cycle error.
Fetch stalls and retirement behavior remain in these measurements. Two points
cannot establish linear scaling or isolated execution-unit latency.

The runner uses fixed memory latency 0, seed 1 and 100000 maximum cycles per ELF.
The wall timeout includes machine-lock waits. Cancellation stops the process
group. RTL runs serially under the project's lock. Keep BOOM small bounded with
`--timeout 900`. Use `examples/boom/sched/small.json` with the BOOM project.

The shipped descriptions are declared seed models. ALU latency 1, multiply
latency 3 and occupancy 1 are starting assumptions, not fitted measurements.
BOOM small uses its dispatch width 1 as the effective LLVM dispatch limit.
Its source architecture data report issueWidth 5. These limits are different;
this seed does not model all five issue resources. Resource counts are partial.
VexRiscv uses the simple-bus, bypass-enabled example with MulSimplePlugin.
The MCA CPUs are built-in comparison baselines, not aliases for these cores.

## Decisions and limits

- Keep configuration, mappings and encodings in project data.
- Keep result latency distinct from occupancy. Occupancy/count gives the
  resource-only reciprocal throughput. Issue width can impose another bound.
- LLVM fragments use exact opcode patterns and `CompleteModel = 0`.
  Register the model with the RISC-V target and rebuild LLVM before use.
- GCC fragments reserve a selected unit instance for the full occupancy.
  Include them only for the intended target CPU. Add the target issue-rate
  hook. Native GCC target/DFA integration is not checked by this slice.
- Validate complete C1/C2 and exact instruction words before reporting slopes.
  No C4 acceptance or C8 completeness claim is made.
- Report generated-model accuracy as `inconclusive`. MCP, held-out kernels,
  bypasses, memory classes, variable latency and parameter fitting remain open.

## Repeated three-size studies

Use `rvw arch sched-study DESCRIPTION --out NEW_DIRECTORY --count 32 --repeats 3`.
The matching cancellable MCP tool is `arch_sched_study`. This is an explicit
RTL job. It uses the existing project adapter and lock. Do not run it as a
static check.

The study measures lengths N, 2N and 4N with at least three seeds. It reuses
the existing two-size runner twice per seed. The middle length therefore has
two observations per seed. All runs keep `mem_latency=0`. The trace checker
requires the requested seed. The existing `sched-measure` path keeps seed 1.

For each class and dependent/independent mode, the report fits a line to mean
cycles at each length. It reports the intercept, slope, adjacent slopes and
maximum residual. Adjacent slope deviation above five percent is marked
nonlinear. This threshold describes stream scaling; it is not a fidelity
budget. Repeated seed slopes and signed MCA errors have bootstrap intervals.
Zero variation remains inconclusive. It does not establish timing accuracy.

The independent stream uses eight register chains. A study is refused if the
declared latency and initiation throughput need more than eight chains.
Branch, load, mixed held-out, bypass and operand-dependent kernels remain
open. Stock llvm-mca still uses the named built-in CPU. Generated scheduling
fragments are not loaded into that tool. Native LLVM/GCC target integration
and RTL accuracy qualification remain separate work.

## Export from a shared project description

`rvw arch compiler-export CORE.json --out NEW_DIRECTORY --json` projects an
O3 `rvw.arch-core/1` file into partial LLVM `model.td`, GCC `model.md`,
`tune.h`, `scheduling.json` and a report. `arch_compiler_export` is the matching
cancellable MCP tool. Run `rvw arch compiler-check DIRECTORY --json` or
`arch_compiler_check` to parse widths, resources, class latencies, occupancy
and GCC reservations back. The checker also checks the restricted generated
syntax and issue-rate include. It refuses modified mappings.

The own-model latency table supplies operation latencies. The shared CPU supplies
issue width and ROB capacity. An explicit own-model class port limit supplies
the resource count. Without one, the exporter assumes one independent resource
per class. Occupancy is one. Shared execution-port topology is not projected.
Mappings cover a subset of base integer ALU, multiply, divide, load and store
opcodes. Unsupported classes stay explicit in the report. Compressed, FP and
vector mappings are absent. Names are scoped to the selected project config.

These are target fragments. CPU registration, target guards, issue-rate hooks
and compiler builds remain separate work under #367. The checker establishes
restricted file round-trip consistency. It does not run TableGen, GCC's DFA,
llvm-mca, a compiler or RTL. It gives no scheduling-accuracy verdict.
