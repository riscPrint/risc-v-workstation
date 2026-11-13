# Portable action and resource scenarios

The scenario contract holds finite logical actions, resource capacities, data
dependencies, literal argument constraints and expected outcomes. Each backend
binds action kinds to operation names and timing costs. Planning does not execute
those operations. A project adapter must supply actual execution observations.

```sh
rvw formal scenario plan rvw/examples/formal/resource-scenario.json --backend model --out model-plan.json
rvw formal scenario plan rvw/examples/formal/resource-scenario.json --backend rtl --out rtl-plan.json
rvw formal scenario plan rvw/examples/formal/resource-scenario.json --backend fpga --out fpga-plan.json
rvw formal scenario check rtl-plan.json --observed rtl-observations.json --out check.json
```

The example's backend names declare bindings only. They do not establish a
model, RTL or FPGA execution result. MCP `formal_scenario_plan` and
`formal_scenario_check` expose the same operations.

## Contract

`rvw.scenario/1` has resource capacities, literal `inputs`, `actions` and
`backends`. An action has `id`, `kind`, optional `after`, `needs`, `produces`,
`claims`, `args`, `constraints` and `expect`. Data names have one producer or
one supplied input value. A consumer cannot start before its producer ends.
Claims reserve integer resource units for the full action interval.

Literal constraints compare an argument `field` with `value` using `eq`, `ne`,
`lt`, `le`, `gt` or `ge`. This does not solve symbolic or randomized constraints.
Each backend declares a timing `unit` and kind-to-`operation`/`duration` bindings.
A duration is a positive integer in that backend's unit.

Planning uses stable action-id order among ready actions. It chooses the first
resource-feasible start after dependencies. The plan is deterministic but is not
an optimal schedule. `scenario_id` identifies the logical actions and resources.
`plan_id` also identifies the backend schedule and timing. A plan reports
`status=planned`. It never reports executed, proven or accepted.

`rvw.scenario-observation/1` identifies `plan_id`, `backend`, `unit` and action
records. Each record contains `id`, `operation`, `start`, `end`, `outputs`,
produced `data` and consumed `inputs`. The checker compares expected output
fields and data transfers. It also checks dependency ordering and actual resource
occupancy. Missing action or data records are inconclusive. No expected outcome
comparisons is inconclusive. Faults are mismatches. A match covers only the
supplied records. The checker does not infer execution provenance or DUT proof.

## Native PSS reuse assessment

The evaluated source is
[pssc at 6dfac17](https://github.com/PSSTools/pssc/tree/6dfac17d82065324a013bb7dbeff5fb0f3a38ba8).
Its README describes a PSS parser, a Zuspec IR lowering path and several code
backends. This is a candidate for a future native PSS frontend and execution
adapter. The compiler is not installed in the local environment used for this
increment. No native PSS parsing, code generation or conformance test ran.

The local contract is a serialized finite action plan. It adds no PSS syntax or
embedded expression language. A future PSS adapter should resolve activity and
constraints through the native compiler, then supply concrete actions to this
planner or use native backend output. Native compiler integration, symbolic
constraints, random scenario generation and real model/RTL/FPGA execution remain
open under #150.

## Literal MMIO execution sources

`formal scenario-compile --source FILE --finisher ADDRESS --out NEW_DIR`
compiles two selected backend plans. Defaults are `baremetal` and `pyuvm`.
MCP: `formal_scenario_compile`. Both plans must use cycles and the same action
order. Bind operations to `read32` or `write32`. Supply aligned 32-bit literal
`args.address`, a write `args.value`, and each read's `expect.value`.

The command emits `program.S`, `scenario_sequence.py`, the two plans and
`operations.json`. `result.json` uses `rvw.scenario-compiled/1` and reports
`status=generated`. It does not run a compiler, simulator or checker.
The virtual sequence expects a project port with async `start`, `observe` and
`finish` methods. This route starts a CPU image and observes its transfers.
It is not an independent bus-master backend. Dynamic data flow needs a project
execution binding and is refused by this compiler.

The [real VexRiscv SoC example](../../../../examples/vexriscv/scenarios/README.md)
executes a 12-action scenario in native RTL. Bare-metal APB capture and the
CPU-backed pyuvm sequence each recorded 12 matching values. Both records pass
through the existing scenario checker. Read the example's limits and measured
inputs before using this as execution evidence.
