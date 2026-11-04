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
