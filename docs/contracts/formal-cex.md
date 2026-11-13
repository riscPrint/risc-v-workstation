# Proof cores and counterexamples contracts

Part of the [platform contracts](../PLATFORM_CONTRACTS.md).

## Counterexample reduction

The optional `reduction` field in `rvw.formal.cex/1` has schema
`rvw.cex-reduction/1`. It records each exact-property replay check, removed input
events, the retained end time, and whether all earlier prefixes were tested.
`status=reproduced` is a simulation observation under the retained assumptions.
It is not a proof. Initial values remain. Reduction can stop at `max_checks`.
The optional `testbench` field records generated model and stimulus paths. Its
`status=generated` does not imply compilation or failure reproduction. The
optional `why` field contains SpinalDB drivers, fan-in and staleness diagnostics.
MMU scenarios may select `pointer_mask` as 0, 7 or 16. These bounded RV64
Smnpm cases tag bit 63 of the tested data pointer. They set and read back
menvcfg.PMM. They use MPRV with effective S privilege. Unmasked tags must
fault. Enabled masking must recover the declared canonical address and value.
The reference selects Smnpm explicitly. These cases do not check debug,
instruction-fetch or guest pointer-masking interactions. Their independent
walk and PMA checks remain inconclusive.

## Captured-model solver cores

`rvw.solver-core/1` can contain `bounded_model` with `top`, `depth` and `scope`.
These cores refer to an aggregate bounded assertion query exported from frozen
SBY RTLIL. Labels identify sample constraint groups. They are not cell coverage,
per-property proofs, or coverage exclusions. Generated SMT and bindings are retained.
The optional `environment_core` lists constraint labels when the environment
feasibility query is UNSAT. Such a run is inconclusive. `bounded_model.feasibility`
records this separate check. `--property` selects one top-module assertion cell;
the generated property ID is `TOP:CELL_NAME`, bound to the captured model.

## Pinned formal rechecks

`rvw.formal-recheck/1` records a bounded solver check over a captured BMC model.
`pins` lists each exact top-module net, width and integer value. Pins add
all-sample equality assumptions. Original drivers and formal cells remain.
`jobs.cover` must report PASS and exit zero for a new full-depth feasibility
cover. Otherwise the aggregate status is `inconclusive`. A legal BMC PASS with
exit zero reports `pass`; a legal BMC FAIL reports `fail`. All other outcomes
are `inconclusive`. `proof_kind` is always `bounded`. The input capture binds the
original result, captured model and tool identities. This schema does not
replace `rvw.formal/1` and does not authorize coverage exclusions.

## Shortest captured counterexamples and explanations

`rvw.shortest-cex/1` records increasing solver sample depths for a captured BMC
model with one assertion. `shortest=true` requires FAIL at the reported depth
and PASS at every smaller positive depth. Unknown depths stop the search.
All-PASS finite searches stay inconclusive. Restrictions and input hashes remain.
`rvw.cex-explanation/1` contains a `chain` from an actual SpinalTrace dynamic
graph. Node IDs refer to its vertex order. Each node records source location,
timestamp, observed value and `causes` with node ID, edge kind and clock flag.
Trace accuracy is retained. Missing accuracy becomes incomplete. These records
are not an unbounded proof or a repair certificate.

## Bounded cell core evidence and explicit obligations

The solver-core report can include `cell_coverage` with a mapped Boolean logic
inventory, `core_cells`, `outside_core`, status and scope. Every cell equation
is separately named for every bounded sample. `bounded_core` means that a
feasible bounded environment and an UNSAT assertion-failure query yielded a core.
It is not an unbounded proof or functional coverage percentage. Testplans can
list requirement obligations by stable property ID. `discharged_conditional`
requires every declared obligation's evidence. Missing obligations cannot pass.

Cell-core `logical_vacuity` rows retain exact assertion IDs, atom bits and both
replacement solver outcomes. Replacements change only the specification Boolean
expression. `replacement_vacuous_bounded` requires UNSAT for both constant
replacements in a feasible environment. `sensitive_bounded` requires a SAT
replacement. State-bit leaves and the finite bound limit the analysis.
`farm batch` accepts one explicit command and expected C1/C3 result paths per
shard. The same commands run locally or as batch/v1 Jobs. Project-supplied PVCs
hold inputs, caches and results. Collection validates schemas and declared C1
identity claims. Missing cells are explicit and inconclusive. Job process success
and collection completeness do not establish C4 acceptance. Kubernetes retries
are disabled; retry policy belongs to the controller.

## Multiple shortest counterexamples

`rvw.shortest-cex/1` can contain `properties`, with one independent shortest-depth
search per captured assertion. Other assertions are removed from each search;
assumptions remain. A shared timeout limits all searches. Single-property outputs
retain the scalar depth and shortest fields. Optional `typed_output` records
SpinalWaves conversion separately from solver evidence. Missing conversion tools
cannot produce a completed typed-output result.
