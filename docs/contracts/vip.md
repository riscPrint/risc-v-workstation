# Protocol agents contracts

Part of the [platform contracts](../PLATFORM_CONTRACTS.md).

## Cocotb component runs

`rvw regress cocotb MANIFEST --out NEW_DIRECTORY --seed N --timeout SECONDS`
accepts a JSON `rvw.cocotb/1` manifest. Required fields are `schema`, `name`,
`backend`, `top`, nonempty `sources` and `test_module`. Optional fields are
`python_paths`, `requires`, `clock` and `reset`. Paths resolve from the manifest.
`clock` has `signal` and positive `period_ns`. `reset` needs a clock and has
`signal`, `active` (0/1), and positive `cycles`. Testbenches call the optional
`rvw.sim.bench.start` helper for clock/reset setup. The native runner receives
the recorded seed. Requirements must be in the backend profile's feature set.

The adapter writes standalone C3 with `kind: "cocotb"` entries, seed, semantic
profile, declared source/Python input hashes, timeout, log/XML/request artifacts,
and replay arguments. It does not produce C1, C8 completeness or C4 acceptance.
The output must be new. Missing/empty/invalid XML, skips, timeouts and runner
errors cannot pass. Exits are 0 for all pass, 1 for test failure, 2 for errors.
See `rvw/src/rvw/sim/README.md` for exact limits and artifact paths.

## Typed simple-bus monitor generation

Typed multichannel bus rows include `component_id`, `class_name`, `coverage`
and `limitations`. `coverage=channel_safety` means full payload stall stability,
channel valid persistence and the listed opcode/burst field rules only. It is
not transaction compliance. Burst beat accounting, ID response order,
exclusive operations and coherence state are not proved by these rows.
Hierarchical targets require locally resolved clock/reset controls. A missing
control stays unsupported. Known bus classes without a generator are listed
with a reason. A simple `Bus` class name is ambiguous and is not inferred.

`rvw.bus-checks/1` records generated or unsupported typed bundle rows, derived
ports, packed width, bind target and captured database provenance. `complete`
means all selected rows generated. It does not mean verification passed.
The aggregate is `no_checks` when no monitor generated, with exit 3. Otherwise
it is `generated`, with exit 0. Unsupported rows retain their reasons.
Only top-component APB3, AHB-Lite3 and AXI4-Stream types are selected.
Missing recorded clock/reset metadata is not inferred from signal names.
