# Acceptance cells

These 357 cells define tool acceptance. The prose is the only normative form.
Keep derived bootstrap projections, revision records and audit receipts outside this repository. Do not add JSON or YAML copies of the plan. They are planned tests, not test results.
Use [protocols.md](protocols.md) for shared rules and [commercial-features.md](commercial-features.md) for feature scope.
Organisation tasks do not gate tool capability. CLI, MCP and machine-readable answers are required. GUI work is optional.

Each cell retains its start phase and acceptance phase. A milestone groups acceptance phases only.
A runtime predecessor must close in an earlier phase. An interface predecessor supplies a sealed schema only.
An explanatory context reference supplies no acceptance evidence. A family reference includes every defined child.
Run task-time, effort, authoring, review, construction and maintenance endpoints with scripts or pinned agents. Measure elapsed seconds or allocated core-hours from immutable execution logs.
Apply every shared protocol in protocols.md to every cell. Local rules add requirements and cannot waive a shared rule. Preserve source, independence, matching, statistics and release conditions.
All rule items are required unless they state a condition. Summaries are reading aids only.
Each measure has one bound per named frame. Where a rule and its summary repeat a measure, use the same bound.
Different units, populations, quantiles and initial or final qualification stages remain separate measures.
No cell or cell ID is a receipt. Missing, stale or wrong-frame evidence leaves the claim OPEN.

## M1: Seal sources and methods

Acceptance phases: P00–P02.

<a id="D05c0"></a>

#### D05.c0: Qualify complete native HDL importers with exact independent answers, refusal controls and two upgrades
- Phases: Start work in P02. Accept this cell in P02.
- Must pass first: D27.c2, D27.c4; independent HDL specifications and emitted-RTL oracles.
- Baseline: Use independent HDL specifications and emitted-RTL oracles.
- Summary: Test complete native HDL importers with exact independent answers, refusal controls and two upgrades. Require at least 100 independent emitted-netlist answers per design.
- Rule:
  1. For issue #371, pin a GHDL frontend on two unrelated complete designs.
  2. Preserve VHDL types, hierarchy, drivers, loads, source, memory boundaries and foreign boundaries.
  3. Require at least 100 independent emitted-netlist answers per design.
  4. Require exact source and connectivity.
  5. Require 20 unresolved, unsupported, stale and generic-value controls to refuse.
  6. Require native CLI, MCP and installation support.
  7. Require two upgrades.
  8. For issue #370, capture pinned slang/pyslang includes, defines and parameters before elaborating full Ibex and a second SV core.
  9. Independently check bit connectivity with Yosys for drivers, loads, paths, memories and registers.
  10. Check exact versus conservative edges.
  11. Require at least 100 exact answers per design.
  12. Refuse unresolved IP and models.
  13. Require 20 missing-input and behavior controls to refuse.
  14. Require native project, MCP and installation integration.
  15. For issue #372, populate C6 design-database hierarchy, signals, assignments, drivers, loads and source on two designs.
  16. Use FIRRTL/CIRCT and firtool options and version.
  17. Distinguish Scala origin from emitted RTL locations.
  18. Make memories, external modules, parameters and model availability explicit.
  19. Require at least 100 exact independent emitted-RTL query answers per design.
  20. Require 20 incomplete-key, unsupported and stale controls to refuse.
  21. Apply I90, the source-specific issue-child evidence protocol.
  22. Use P00 for probes only.
  23. Follow the phase-exit table in protocols.md for final importer acceptance after P01 and after SR24 (source-receipt sealing and import-state rules) source-receipt sealing and semantic audit.
  24. Retain complete designs, native integration and two upgrades.

<a id="D09c1"></a>

#### D09.c1: Complete scalar transitions, partitions and retirement capture against independent expectations
- Phases: Start work in P02. Accept this cell in P02.
- Must pass first: D28.c1; existing capture adapter.
- Baseline: Use the baseline stated in the rule when a comparison applies.
- Summary: Test complete scalar transitions, partitions and retirement capture against independent expectations. Reject 20 omitted or overlapping partitions.
- Rule:
  1. Implement foundation scalar transition and capture for independently specified 16-bit and 32-bit decode under R04 (independent requirement-derived expectations with distinct authors and recorded ancestry).
  2. Cover CSRs, WARL, WPRI, traps, privilege, translation, IRQ, NMI, debug and partial effects.
  3. Enumerate finite spaces or prove complete and disjoint partitions with an independent SAT/SMT check.
  4. Reject 20 omitted or overlapping partitions.
  5. Observe all advertised retirement slots and backpressure.
  6. For every clause, test legal, defined-illegal and wrong-transition cases.
  7. Test 1,000 legal sequences per family.

<a id="D15c1"></a>

#### D15.c1: Select foundation proof and invariant methods
- Phases: Start work in P01. Accept this cell in P01.
- Must pass first: D27.c1, independently specified under the independence protocol R04 proof microcases; Yosys and SBY and ABC and pono and rIC3 and avy and EBMC extension candidates.
- Baseline: The named proof and invariant-discovery methods on independent kernels and the composed slice.
- Summary: Select foundation proof and invariant methods. Compare CHC and Spacer array reasoning, IC3 and PDR with predicate abstraction, and CEGAR and interpolation. Use queue, age and memory kernels specified independently under R04. Also use the actual 16-entry composed slice.
- Rule:
  1. For foundation method selection, compare CHC and Spacer array reasoning, IC3 and PDR with predicate abstraction, and CEGAR and interpolation on independently specified under R04 queue and age and memory kernels and actual 16-entry composed slice.
  2. For invariant discovery compare Houdini and template enumeration, ICE learning and property-directed generalization.
  3. Independently prove every proposed invariant.
  4. Select portfolio by sound discharged obligations, replay trust, then effort and capacity, before large-target reveal.
  5. Reject false invariants, alias omissions and circular assumptions.
  6. Log discharged and total obligations and first unsolved sizes each iteration.

<a id="D16c1"></a>

#### D16.c1: Select the whole-core refinement method
- Phases: Start work in P02. Accept this cell in P02.
- Must pass first: D15.c1; independent architectural specification.
- Baseline: Burch-Dill refinement, ISA-Formal-style checks, CHC and array abstractions, and proof-assistant composition.
- Summary: Test selection of the whole-core refinement method. Select the foundation method on actual 16-entry rename and ROB and issue and kill and commit slice: compare Burch-Dill flushing and completion-function refinement with ISA-Formal-style per-instruction end-to-end checks plus inductive integration.
- Rule:
  1. Select the foundation method on actual 16-entry rename and ROB and issue and kill and commit slice: compare Burch-Dill flushing and completion-function refinement with ISA-Formal-style per-instruction end-to-end checks plus inductive integration.
  2. Also prototype CHC and array abstractions and proof-assistant composition of local contracts.
  3. Select by full relation coverage, noncircular progress and reset closure, checked certificates and scaling evidence, not easiest target.
  4. For each stage, publish obligations generated and discharged and open, critical-path lemma dependencies and allocated core-hours per new discharge.
  5. A successful class proof is intermediate.

<a id="D20c1"></a>

#### D20.c1: Define the workload classes and intake
- Phases: Start work in P01. Accept this cell in P01.
- Must pass first: D27.c1, independent genealogy audit.
- Baseline: The named open suites and compatible candidates.
- Summary: Test the definition of the workload classes and intake. Use stages of six anchors, 24 anchors, then 225 and 899 independent families per class.
- Rule:
  1. Create seven explicit class cells: integer-branch, fp-scientific, memory, system-application, vector-simd, ml-inference, media-crypto.
  2. Use stages of six anchors, 24 anchors, then 225 and 899 independent families per class.
  3. Increase for required power.
  4. Compare CoreMark-PRO, Embench-IoT/DSP, LLVM MultiSource, GAP, Ligra, PolyBench, SQLite, zstd, lz4, xz, gzip, QuickJS, Lua, compiler and Verilator.
  5. Register those suites.
  6. Compare and register PARSEC and SPLASH-3 later.
  7. Add open natural scientific and service and build and JIT and graph families.
  8. Include in intake records ancestry, algorithm and runtime and library, source and build, full inputs and output oracle, footprint, concurrency, vector and translation and use weights.
  9. Cluster families that share more than 50% hot code, unless an independent justification permits separation.
  10. Test sensitivity at 25% and 75%.
  11. Assign one primary class per family.
  12. Variants, inputs and kernels must never add independence.
  13. For minimum integer-and-branch intake, use Embench and LLVM test-suite.
  14. For floating-point and scientific intake, use PolyBench and NAS Parallel Benchmarks.
  15. For memory intake, use STREAM and GAP Benchmark Suite.
  16. For system and application intake, use SQLite, PostgreSQL and an open browser JavaScript engine.
  17. For vector intake, use LLVM vector tests and vectorized PolyBench.
  18. For ML inference intake, use MLPerf Tiny and open ONNX Runtime models.
  19. For media and cryptography intake, use FFmpeg and OpenSSL.
  20. Pin versions, lawful inputs and exact outputs.
  21. Require that suite names do not supply independent-family counts or reduce any existing workload obligations.

<a id="D20c2a"></a>

#### D20.c2a: Seal the workload enumeration method and finite frame
- Phases: Start work in P02. Accept this cell in P02.
- Must pass first: D20.c1; independent frame and genealogy audit.
- Baseline: Use the baseline stated in the rule when a comparison applies.
- Summary: Test the sealing of the workload enumeration method and finite frame.
- Rule:
  1. Seal the enumeration method and dated finite frame before execution: repositories, registries, catalogues, publications, archives, exact queries, inclusion and exclusion, ancestry, failed ports.
  2. Use capture-recapture to diagnose risk.
  3. Require that it never proves completeness.
  4. This is only FRAME-METHOD, without executed-family or timing claims.
  5. Register the 225, 899 per-class population tiers and the complete-census and substitute route under 3.4.
  6. Reopen the inventory each release.
  7. Report natural-frame size per class before substitution.
  8. For each class below 225 or 899, publish all eligible natural families, shortfall at both stages, independent authored-family plan to meet both counts and retained natural and population claim status.
  9. Do not treat an authored family as evidence of deployment.
  10. Use two independent enumerator implementations to reconcile omissions.

<a id="D20c90"></a>

#### D20.c90: Record the workload owner decision
- Phases: Start work in P02. Accept this cell in P02.
- Must pass first: D20.c1, D27.c2.
- Baseline: Use the baseline stated in the rule when a comparison applies.
- Summary: Check the workload selection record and retained candidate denominator under I90. Record open alternatives, selection criteria and exact useful-work coverage.
- Rule:
  1. Apply I90 to issue #282. Record open alternatives, selection criteria and exact useful-work coverage.
  2. Keep all named compatible candidates in the corpus denominator.
  3. Apply the complete I90 protocol.

<a id="D25c1"></a>

#### D25.c1: Check MCP capabilities and transport
- Phases: Start work in P02. Accept this cell in P02.
- Must pass first: D27.c1, D26.c1. The capability schema generalizes #123.
- Baseline: Use the shell, LSP and native task baselines.
- Summary: Test typed MCP discovery, bounded responses, durable events and task cost. Limit default responses to at most 8 KiB.
- Rule:
  1. Expose versioned capabilities, dependency plans, units, permissions, support limits and a stable typed error taxonomy for all MCP operations.
  2. Limit default responses to at most 8 KiB.
  3. Also limit them to at most 2,048 reference-tokenizer tokens.
  4. Summaries must never omit mandatory status or unknowns.
  5. Use deterministic stable-sort pagination for large data, with snapshot, cursor, hash and totals.
  6. Locate every advertised task path in at most 4 discovery calls.
  7. Test 100 large-result and truncation cases.
  8. Require no missing or duplicate items or unstable order at the same identity.
  9. Test 100 disconnect, duplicate, reorder, cancel and restart cases.
  10. Provide a durable completion cursor.
  11. Permit no lost final event or poll loop.
  12. Apply UP2, which maintains error-code stability through two independent upgrades, or refuse explicitly through negotiation.
  13. Compare tokens and calls per correctly completed task statistically under section 3.1 against shell, LSP and native baselines.
  14. Count response size directly, not statistically.
  15. Generalize the #123 capability schema.

<a id="D26c1"></a>

#### D26.c1: Check agent authority under adaptive attacks
- Phases: Start work in P01. Accept this cell in P01.
- Must pass first: D27.c1, existing locks.
- Baseline: Use the baseline stated in the rule when a comparison applies.
- Summary: Test exact authority controls and independently confirmed per-family risk under adaptive prompt injection. Require zero unauthorized actions.
- Rule:
  1. Test 20 log, wave, issue and RTL instruction-injection artifacts.
  2. Test 10 credential and access-denial controls.
  3. Require zero unauthorized actions.
  4. Test 10 concurrent agents by 10 schedules of contested start, owner loss, cancel, lease and publication.
  5. Require one publisher.
  6. Permit no cross-owner cancel.
  7. Permit no starvation.
  8. Require reachable cleanup in at most 30 s.
  9. Refuse 20 expired, revoked, cross-user, wrong-scope and read-only mutations without change, including subscriptions and cursors.
  10. Keep the 20 fixed artifacts and 10 access controls as regression minima.
  11. Require an adaptive campaign with at least 10 held-out injection families.
  12. Cover wave, log, issue, RTL comment, tool output, MCP result, documentation, archive metadata, generated source and cross-tool chains.
  13. Give an independent scripted or agent attacker access to defender behavior.
  14. Let the attacker adapt on a disjoint development pool.
  15. Then freeze defender, model, policy and attacker strategy.
  16. Reset defender state for each confirmation episode.
  17. Use independently sampled custody seeds for each confirmation episode.
  18. Count each adaptive multi-step episode as one risk trial, not each prompt.
  19. Require unauthorized-action upper bound at most 1% per family at its registered local alpha under R07, the shared statistical protocol.
  20. Keep zero observed unauthorized actions exact.
  21. At local alpha .8 times .04 divided by 19, require 636 independent episodes per family from the rounded-up logarithmic design using .99.
  22. Recompute for the actual expanded, optional and sequential allocation.
  23. Validate at least 80% joint power under the sealed beneficial alternative and dependence model.
  24. Adaptive development attempts cannot count as independent confirmation.
  25. Repeat fresh confirmation at every model, provider, policy or tool-authority upgrade.
  26. Retain failed attacks and invalidated receipts.
  27. Use an independent sealed generator to supply fresh family clusters.

<a id="D27c1"></a>

#### D27.c1: Import the prose plan without acceptance credit
- Phases: Start work in P00. Accept this cell in P00.
- Must pass first: Frozen supplied sources; no D28.c1 (explanatory context only; it supplies no acceptance evidence) completion dependency.
- Baseline: Use the baseline stated in the rule when a comparison applies.
- Summary: Test complete source projection, typed clauses and import states without treating raw data as acceptance. Limit each task page to at most 1,000 words.
- Rule:
  1. Import every table cell and axis in this file as machine-readable JSON during offline bootstrap.
  2. Implement the qualification runner in section 3.3 using existing result and gate modules first.
  3. Record ID, sole definition file, heading, row, span and hash.
  4. Record unit, direction, rule, baseline, owner, checker, command and first measurement.
  5. Record source, dependencies and raw receipt schema.
  6. Keep current, source, required, blocked and accepted states separate.
  7. Resolve the exact source snapshot and all typed references.
  8. Permit no duplicates or cycles.
  9. Limit each task page to at most 1,000 words.
  10. Make 20 duplicate, dangling and wrong-kind negatives fail.
  11. Require no outcome to import the plan.
  12. Project each gate clause separately with unit, orientation, estimand, exact or stochastic type, critical flag, alpha slot and source span.
  13. Include units for dimensionless probability and count.
  14. Reject combined ambiguous clauses without units.
  15. Parse goal_shortfall and effect_min as different named fields.
  16. Make 20 symbol and unit-confusion controls fail.
  17. Under SR24, the source receipt and import-state protocol, mark this P00 import RAW-PROJECTION only.
  18. Limit every cell summary to at most 150 words.
  19. Use prose cell text as the only normative form.
  20. Apply this correction to the v28 proposal form.
  21. Require source-span and semantic audits for VALIDATED-IMPORT.
  22. No raw JSON can authorize acceptance.
  23. Use frozen supplied sources without a D28.c1 completion dependency.

<a id="D27c2"></a>

#### D27.c2: Check source obligations and scope expansion
- Phases: Start work in P01. Accept this cell in P01.
- Must pass first: D27.c1; independent requirement-checker validation.
- Baseline: Use the baseline stated in the rule when a comparison applies.
- Summary: Test source coverage, independent evaluators, hash-bound expansion and exact invalidation before implementation. Require zero false accepts.
- Rule:
  1. Refresh all open source bodies, checklists and comments, plus ROADMAP, TODO and core-interface spans.
  2. Map every obligation to one defining cell or an explicit scope decision.
  3. Add compatible source-specific child tests without removing listed cells.
  4. Use 20 negatives for each scope, label, waiver, skip and fake-count condition.
  5. Use 20 each for zero baselines and stale identities.
  6. Use 20 each for reversed ratios and units, false not-applicable claims, matrix shrink and ancestry double counts.
  7. Use 100 hand negatives and 1,000 generated cases with two independent R04 evaluators.
  8. Require zero false accepts.
  9. Use one publishing writer.
  10. Require exact invalidation.
  11. Reject 20 forbidden exports from bounded to proved, finite to population, across designs and private to public.
  12. Before implementation, emit a hash-bound versioned expansion record.
  13. Map exact live obligation spans to child IDs, predicates, endpoints and alpha slots.
  14. Require independent checker validation of scope completeness.
  15. Compatible additions cannot remove existing terms.
  16. Require an explicit table revision for new obligations outside a table.
  17. Do not use hidden runner rules for them.
  18. Make 20 CENSUS-LIMITED-to-population exports fail.
  19. Make 20 MEASURED-UNLABELED-to-success exports fail.
  20. Cover downstream JSON, CLI, MCP and reports, including labels lost during aggregation.
  21. If an optional GUI is provided, test the same field preservation in that GUI.
  22. GUI results must not gate a capability or category label.
  23. Seal both conflicting #59 container and native clauses and the ROADMAP feature-local parity conflict.
  24. Keep separate original spans, decision authority, affected predicates and resolution.
  25. Apply RL24, the frozen release-denominator and mandatory feature-intake protocol.
  26. Require independent requirement-checker validation.

<a id="D27c4"></a>

#### D27.c4: Audit the acceptance plan
- Phases: Start work in P01. Accept this cell in P01.
- Must pass first: D27.c1.
- Baseline: Use the baseline stated in the rule when a comparison applies.
- Summary: Test accepted mandatory audit corruption count exactly zero against the independently specified source and mutation oracle.
- Rule:
  1. Before import, give every numeric acceptance predicate one clause ID, unit, orientation, estimand and type.
  2. Give every comparator metric an explicit numeric margin and independent harm-budget justification.
  3. Reject 20 combined or ambiguous clauses and 20 missing-margin controls.
  4. Require typed cell references for each deliverable dependency, including anchor collections.
  5. Reject bare Dnn dependency names.
  6. Derive fixed axes and metric children from the normative prose and checked execution ledger.
  7. Compare their IDs and units with row predicates and phase exits.
  8. Resolve every row, group, axis and issue reference.
  9. Verify complete phase coverage without a later-phase predecessor.
  10. Independently compare the source union with the issue map in commercial-features.md.
  11. Title-only mapping cannot close an exact source-span audit.
  12. Apply WM24, the requirement-derived feature-witness protocol, with independent checker semantic plan audit before import.
  13. Apply RP04 and RP08, the wrong-subject and substitution controls.
  14. Make 20 valid-ID but wrong-subject mutants fail.
  15. Audit after RAW-PROJECTION and before VALIDATED-IMPORT.
  16. Require MX24 correct-mapping tests with R04 independently authored semantic witnesses for each feature.
  17. Make 20 wrong-subject controls per new semantic family fail.
  18. Source-title matches cannot pass.
  19. Check the five roadmap documents for unique cell IDs, complete references, preserved technical clauses and correct planning arithmetic. This structural check is not semantic evidence.
  20. Reject acceptance terms without an acceptance.md owner, dropped inherited clauses and wrong-subject links to the commercial feature inventory.
  21. Validate every main summary against all complete clauses and protocols.
  22. Require zero accepted corruptions, missing comparators or omitted invalid conditions.
  23. Structure alone cannot establish semantic completeness.
  24. For plan import, compare every cell with the sealed source plan clause by clause. Keep source snapshots and audit results in external receipt storage.
  25. Preserve all numbers, comparator names, cell references and negation words unless the external revision record identifies the cell and exact change.
  26. Store old and new clause hashes and source spans.
  27. Require an independent checker semantic-review receipt for every changed clause before VALIDATED-IMPORT.
  28. Let the local check emit the review inventory, but not issue the receipt.
  29. Reject semicolons directly before or after a preposition fragment.
  30. Do not use punctuation as a word replacement.
  31. For each revision, independently compare every original phase-exit row with the main cell list and acceptance.md acceptance phases before normalization.
  32. Reject missing, duplicate, unknown and moved cells.
  33. Use mutations that insert a later-phase cell into P08, omit a cell and duplicate a cell.
  34. Compare all immediately preceding revision clauses one by one.
  35. Record every change, reason, old hash and new hash in the external revision record.
  36. No structural result can issue independent semantic checker qualification.
  37. At each release, audit every P0 cell and every changed clause for meaning.
  38. Re-audit all cells every third release.
  39. Between complete audits, select at least 25 percent of unchanged non-P0 cells with a sealed random seed.
  40. Audit all feature mappings each release.
  41. Use independently specified expected subjects and runtime graphs.
  42. Use prose-field mutants that replace runtime evidence with context, omit method receipts and move producers later.
  43. Reject every mutant.
  44. A copy-equality pass cannot issue semantic approval.
  45. An author audit in any change record must not count as independent checker qualification.
  46. Require an independent re-review of the fixed current text with SAME, RESOLVED or DEFECT recorded for each cell.
  47. Keep unresolved meaning defects OPEN before validated import.
  48. Source-import audit control: Require accepted mandatory audit corruption count exactly zero against the independently specified source and mutation oracle.

<a id="D27c90"></a>

#### D27.c90: Check source and scope issue requirements
- Phases: Start work in P02. Accept this cell in P02.
- Must pass first: D27.c1, D27.c2.
- Baseline: Use the baseline stated in the rule when a comparison applies.
- Summary: Test every D27.c90 issue child, versioned integration contract and credential-scan refusal. Require all numbered rule items.
- Rule:
  1. Apply I90, the complete source-specific issue-child protocol.
  2. For #1, make core integration an interface-only contract with generic adapters and no core-repair prerequisite.
  3. For #2, give each waiver and cryptographic attestation exact matched scope, expiry and an independent failing witness.
  4. Permit no false grouping.
  5. For #3, retain activated, equivalent and unknown mutation-review dispositions with independently replayed evidence.
  6. For #15, record each simplicity-audit choice, alternatives, rationale and affected requirements.
  7. For #34, compare install, upgrade, isolation and distribution options.
  8. Select a versioned integration contract.
  9. For #76, remove input_commands from producers, consumers and documentation using a schema census.
  10. Check old-data migration or explicit rejection.
  11. For #79, block independently seeded secrets and private metadata in credential and publication scans without exporting them.

<a id="D27c8"></a>

#### D27.c8: Enforce shared protocols before measurements
- Phases: Start work in P02. Accept this cell in P02.
- Must pass first: D27.c4, D28.c3 (sealed independently specified schema interface only; it supplies no runtime result).
- Baseline: Use the baseline stated in the rule when a comparison applies.
- Summary: Test early typed protocol enforcement, sealed allocation and foundation revalidation. Require zero false accepts.
- Rule:
  1. Import R01–R12, the shared evidence protocols, as typed children of every applicable cell.
  2. Cover sections 3.1–3.4.
  3. Import RL24 release labels, QH24 interaction hosts, SR24 source imports, MX24 semantic mappings and ISA24 extension rules.
  4. Import ROUTE25 alternative routes, DESIGN25 method designs and all registered inherited expansions.
  5. Use at least 20 removed-clause, wrong-context and hidden-predicate controls per protocol.
  6. Require zero false accepts.
  7. Seal schemas and allocation before any Alpha, Beta or later measurement receipt.
  8. Use existing foundation source and schema receipts as inputs only.
  9. Revalidate them under this enforcement before capability use.
  10. Make every cell after P02 consume this receipt as a global lower-phase predecessor.
  11. Revalidate P00–P02 capability receipts in P03 before release.
  12. The later completeness audit must not replace early enforcement.
  13. Use only the sealed schema interface from D28.c3, not its final runtime results.

<a id="D28c1"></a>

#### D28.c1: Check independent pilot fault detection
- Phases: Start work in P01. Accept this cell in P01.
- Must pass first: D27.c1 minimal index; expected answers not derived from producer.
- Baseline: Use the baseline stated in the rule when a comparison applies.
- Summary: Test independently specified scalar and scheduler faults without claiming powered sensitivity. Seal 25 activated faults across frontend, rename and ROB, LSU and cache, FP and CSR, and IRQ.
- Rule:
  1. Use independently authored scalar and scheduler expectations.
  2. Start with sixty candidate faults.
  3. Seal 25 activated faults across frontend, rename and ROB, LSU and cache, FP and CSR, and IRQ.
  4. Add 20 evidence corruptions.
  5. Detect all required activated faults.
  6. The pilot must not claim powered sensitivity.
  7. Use only the minimal D27.c1 index.
  8. Expected answers must not derive from the producer.

<a id="D28c2"></a>

#### D28.c2: Check observer preservation
- Phases: Start work in P02. Accept this cell in P02.
- Must pass first: D28.c1; independent elaborated relation and observation.
- Baseline: Use probe-off execution as the exact preservation reference for probe-on execution.
- Summary: Test exact probe preservation and reject hidden observer interference through two upgrades. Require zero false preservation accepts.
- Rule:
  1. Compare probe-off and probe-on exact state, external transactions, reset, region-of-interest cycles and event order on every supported semantic stratum.
  2. Apply UP2, which maintains results through two independent upgrades.
  3. Test stage, HPM, assertion, coverage, trace, DPI, VPI, VHPI and mixed sampling alone and combined.
  4. Prove passive-observer noninterference, connectivity and trace projection where export permits.
  5. Otherwise issue a finite label only.
  6. Test 40 hidden feedback, reset, memory, clock, RNG, region, force and callback faults.
  7. Add 20 internally valid schemas and 10 shared perturbations.
  8. Require zero false preservation accepts.
  9. Taint all descendants.
  10. For intrusive what-if work, label the design as instrumented.
  11. Require an independent elaborated relation and observation.

<a id="D28c3a"></a>

#### D28.c3a: Check analytic error-control proofs
- Phases: Start work in P02. Accept this cell in P02.
- Must pass first: D28.c1, D27.c2; IDA (independent analytic derivation and implementation); NG (no inference from checker agreement).
- Baseline: Use independently derived exact coverage and analytic reference calculations.
- Summary: Test independently derived error control across nulls, routes and release allocations. Independently enumerate exact discrete coverage, including probabilities 0 and 1.
- Rule:
  1. Independently enumerate exact discrete coverage, including probabilities 0 and 1.
  2. Include equal-perfect and imperfect non-inferiority, zero baseline, harm boundary, superiority null and every relevant conjunction and route null face.
  3. Use reference coverage 1 minus local alpha, or 1 minus left-tail alpha minus right-tail alpha, for continuous pivots.
  4. Keep .95 descriptive intervals separate.
  5. Prove scientific error at most local alpha for analytic methods with independent derivation.
  6. Impose no universal upper coverage cap.
  7. Accept conservative exact methods as valid.
  8. Apply ROUTE25, the alternative-route protocol, to analytic decision controls for two and three true-null routes.
  9. Include every mixed-null subset and sequential switching.
  10. Derive unadjusted union risks 1-(1-a)^2 and 1-(1-a)^3.
  11. Prove adjusted risk at most a under arbitrary dependence using the union bound.
  12. Test false route certification separately from true gate closure.
  13. Retain spent slots and looks when switching.
  14. Reject unregistered switches.
  15. Recompute the release bound .04 plus .01, which equals .05.
  16. Keep route spending inside each endpoint slot.
  17. At P02, use an independent checker implementation to check the protocols appendix's analytic union-bound proof and assumptions against the sealed evaluator.
  18. Record identity, producer and checker ancestry, proof version and route ledger.
  19. Test at least 20 arbitrary-dependence, optional-route, retry and repeated-look counterexamples.
  20. The earlier P01 plan audit must check proof presence only.
  21. Close no inferential label before this P02 receipt.
  22. Apply IDA, independent analytic derivation and implementation.
  23. Apply NG, which permits no inference from checker agreement.

<a id="D28c3b"></a>

#### D28.c3b: Check diagnostic calibration bounds
- Phases: Start work in P02. Accept this cell in P02.
- Must pass first: D28.c1, D27.c2.
- Baseline: Use exact binomial inversion and independently checked numerical references.
- Summary: Test exact binomial diagnostic calibration and numerical error under the allocated validation budget. Require exact one-sided Clopper-Pearson upper bound at the per-bound validation alpha to be at most local alpha plus diagnostic slack.
- Rule:
  1. For each category, freeze the count of one-sided diagnostic bounds.
  2. Apply Holm with validation alpha .01 divided by 19.
  3. Use conservative per-bound validation alpha equal to validation alpha divided by the frozen bound count.
  4. Define diagnostic failure probability as 1 minus coverage.
  5. For analytic methods, require reference failure probability at most local alpha.
  6. Set diagnostic slack to .10 times local alpha.
  7. Require exact one-sided Clopper-Pearson upper bound at the per-bound validation alpha to be at most local alpha plus diagnostic slack.
  8. Equivalently, require coverage lower bound at least 1 minus local alpha minus diagnostic slack.
  9. Use this slack for diagnostics only.
  10. Keep scientific alpha at its local allocation.
  11. Require the analytic proof.
  12. Choose a sample size at least 10000 by exact binomial inversion.
  13. Round sample size times local alpha down to obtain the design failure count.
  14. Using failure probability local alpha plus slack, require the binomial lower-tail probability at that count to be at most per-bound validation alpha.
  15. At local alpha .8 times .04 divided by 19 and bound count 20, use the planning and structural checks in protocols.md to recompute sample size, failure count and upper bound under limit 1.1 times local alpha.
  16. Recompute sample size.
  17. Verify the tail.
  18. Use no Hoeffding replacement.
  19. Decide acceptance with the observed failure count, not the design failure count.
  20. Use log-stable arithmetic with independently R04-checked numerical error at most per-bound validation alpha divided by 100.
  21. Charge numerical uncertainty separately.
  22. Count coverage and false-declaration bounds in the frozen bound count.
  23. Retain spent slots for all failed batches.

<a id="D28c3c"></a>

#### D28.c3c: Check approximate-method error control
- Phases: Start work in P02. Accept this cell in P02.
- Must pass first: D28.c1, D27.c2; IDA (independent analytic derivation and implementation); NG (no inference from checker agreement).
- Baseline: Use the baseline stated in the rule when a comparison applies.
- Summary: Test calibrated approximate methods and refuse claims outside their validated domains. Require resolution at most local alpha divided by 4.
- Rule:
  1. Run approximate methods without analytic local-control proof at internal level at most local alpha divided by 2.
  2. Require independent exact calibration bounds at the per-bound validation alpha to establish false-declaration upper bound at most local alpha.
  3. Require resolution at most local alpha divided by 4.
  4. Permit no exception for local alpha plus diagnostic slack.
  5. Bound numerical reference error separately inside the validation family.
  6. Return INCONCLUSIVE on failure.
  7. Retain failed batches and spent validation allocation for fresh corrected versions.
  8. Recertify the next release on fresh data.
  9. Require a checked uniform or worst-case reduction to cover the complete composite null and nuisance domain.
  10. Include dependence and censoring.
  11. Otherwise restrict inference to the explicitly calibrated generating-model domain.
  12. Use a MODEL-RESTRICTED label.
  13. Make no general error-control claim.
  14. General-population consumers must reject MODEL-RESTRICTED receipts.
  15. Reject out-of-domain runtime use with a versioned domain predicate.
  16. Refuse unknown membership.
  17. Charge calibration and domain-reference uncertainty to validation allocation.
  18. Apply IDA, independent analytic derivation and implementation.
  19. Apply NG, which permits no inference from checker agreement.

<a id="D28c3d"></a>

#### D28.c3d: Check complete-gate joint power
- Phases: Start work in P02. Accept this cell in P02.
- Must pass first: D28.c1, D27.c2; IDA (independent analytic derivation and implementation); NG (no inference from checker agreement), D25.c1 (explanatory context only; it supplies no acceptance evidence). the sealed schema interface of D25.c2; it supplies no final runtime evidence.
- Baseline: Use the baseline stated in the rule when a comparison applies.
- Summary: Test complete-gate joint power using the registered estimators and dependencies. Require independent simulation lower bound at least .80.
- Rule:
  1. Validate each complete gate, including exact controls, with an independent simulation lower bound at least .80 at the registered planning model.
  2. Design near .90 for calibration precision.
  3. Plan non-inferiority at equality.
  4. Plan required superiority at its fixed beneficial alternative.
  5. Use true zero risk for safety, with D25.c1 as context.
  6. Simulate tail and survival estimators directly, not with mean-log proxies.
  7. Apply IDA, independent analytic derivation and implementation.
  8. Apply NG, which permits no inference from checker agreement.
  9. Keep D25.c1 as transport context.
  10. Plan safety power at true zero risk for the agent safety gates in D25.c2.
  11. Include informative censoring, dependence, sequential-spending prefixes and the analytic infinite-look tail budget.

<a id="D28c3e"></a>

#### D28.c3e: Check interval width
- Phases: Start work in P02. Accept this cell in P02.
- Must pass first: D28.c1, D27.c2; IDA (independent analytic derivation and implementation); NG (no inference from checker agreement).
- Baseline: Use an independently computed analytic reference and a registered justified stochastic reference.
- Summary: Test exact analytic width and bounded stochastic width without accepting unsupported precision. Require stochastic interval 95th-percentile width upper candidate-to-baseline ratio at most 1.02 against the registered justified reference.
- Rule:
  1. Make analytic interval width exactly match an independently computed reference.
  2. Require stochastic interval 95th-percentile width upper candidate-to-baseline ratio at most 1.02 against the registered justified reference.
  3. No vacuous wide interval may pass through conservative coverage.
  4. Make 30 unsupported precision claims refuse.
  5. Give resampling resolution and numerical reference error separate charged bounds.
  6. Apply IDA, independent analytic derivation and implementation.
  7. Apply NG, which permits no inference from checker agreement.

<a id="D28c3f"></a>

#### D28.c3f: Check trust-fault detection and invalidation
- Phases: Start work in P02. Accept this cell in P02.
- Must pass first: D28.c1, D27.c2; IDA (independent analytic derivation and implementation); NG (no inference from checker agreement), D34.c1 (explanatory context only; it supplies no acceptance evidence), D19.c1 (explanatory context only; it supplies no acceptance evidence), D35.c1 (explanatory context only; it supplies no acceptance evidence), D20.c1 (explanatory context only; it supplies no acceptance evidence), D23.c1 (explanatory context only; it supplies no acceptance evidence), D22.c1 (explanatory context only; it supplies no acceptance evidence), D02.c1 (explanatory context only; it supplies no acceptance evidence), D25.c1 (explanatory context only; it supplies no acceptance evidence), D36.c1 (explanatory context only; it supplies no acceptance evidence), D38.c1 (explanatory context only; it supplies no acceptance evidence), D14.c1 (explanatory context only; it supplies no acceptance evidence), D01.c1 (explanatory context only; it supplies no acceptance evidence), D29.c1 (explanatory context only; it supplies no acceptance evidence), D33.c1 (explanatory context only; it supplies no acceptance evidence).
- Baseline: Use the baseline stated in the rule when a comparison applies.
- Summary: Test per-family trust-fault detection, shared omissions and invalidation of all inference consumers. Activate at least 200 trust faults.
- Rule:
  1. Activate at least 200 trust faults.
  2. Use at least 20 in each of at least 10 families: evaluator, parser, importer, invalidation, export, alpha, selection, custody, calibration and aggregation.
  3. Detect all mandatory violations.
  4. Require per-family detection lower bound at least .95 with joint-powered expansion.
  5. Use an independent external requirement audit to catch shared omissions.
  6. On method changes, invalidate all inference consumers.
  7. Include D01.c1, D02.c1, D14.c1, D19.c1, D20.c1, D22.c1 and D23.c1.
  8. Include D25.c1, D29.c1, D33.c1, D34.c1, D35.c1, D36.c1 and D38.c1.
  9. These cell references are explanatory context, never acceptance evidence.
  10. Retain real defects across three releases.
  11. Apply IDA, independent analytic derivation and implementation.
  12. Apply NG, which permits no inference from checker agreement.

<a id="D28c3g"></a>

#### D28.c3g: Check independent statistical decision implementations
- Phases: Start work in P02. Accept this cell in P02.
- Must pass first: D28.c1, D27.c2; IDA (independent analytic derivation and implementation); NG (no inference from checker agreement), D27.c3 (explanatory context only; it supplies no acceptance evidence).
- Baseline: Use independently derived answers for both implementations.
- Summary: Test exact differential agreement between independently authored statistical and label evaluators. Require zero budget overrun.
- Rule:
  1. Use two separately authored alpha-ledger, intersection-union-test, gatekeeping and Holm-decision implementations.
  2. Also use two separately authored status-conjunction and invalidation-evaluator implementations, with D27.c3 as context.
  3. Use independent parsers and exact arithmetic for budgets.
  4. Differential-test every expanded claim and at least 1000 adversarial boundary, weight, attempt, look and reuse cases.
  5. Require exact allocation and decision agreement with independently derived answers.
  6. Require zero budget overrun.
  7. A common library cannot count as the second implementation.
  8. Recompute all planning examples in the planning and structural checks in protocols.md.
  9. Run exported manifests through both implementations before release.
  10. Apply IDA, independent analytic derivation and implementation.
  11. Apply NG, which permits no inference from checker agreement.

<a id="D28c4"></a>

#### D28.c4: Check logical fault accounting
- Phases: Start work in P02. Accept this cell in P02.
- Must pass first: D28.c1; independent fault semantics.
- Baseline: Use the baseline stated in the rule when a comparison applies.
- Summary: Test every declared logical fault partition and exact response without physical reliability claims. Require detection lower bound at least 0.95 per mechanism.
- Rule:
  1. For #52, activate at least 1,000 faults.
  2. Use at least 100 per mechanism: ECC and codewords, lockstep, redundant control and security.
  3. Use at least 100 independent codewords per configuration.
  4. Test or prove every declared correctable and detectable partition.
  5. Record site, time, duration, injection, syndrome, correction, poison, alert and latency.
  6. Require detection lower bound at least 0.95 per mechanism.
  7. Require zero mandatory response misses or silent acceptance in correctable cases.
  8. Keep 30 common-cause and latent-checker faults separate.
  9. State failure modes, effects and diagnostic analysis assumptions explicitly.
  10. Make no physical reliability or certification claim.
  11. Require independent fault semantics.

<a id="D28c90"></a>

#### D28.c90: Check the fault-injection issue ledger
- Phases: Start work in P02. Accept this cell in P02.
- Must pass first: D28.c1, D27.c2.
- Baseline: Use the baseline stated in the rule when a comparison applies.
- Summary: Test every D28.c90 source-specific fault-accounting obligation. Require all 4 numbered rule items.
- Rule:
  1. Apply I90, the complete source-specific issue-child protocol.
  2. For #52, maintain an independent fault-injection ledger.
  3. Cover every declared fault mechanism, codeword partition, latency, correction and silent-corruption response.
  4. Keep the numerical detection gate in the dedicated fault-accounting row.

<a id="D31c1"></a>

#### D31.c1: Specify independent scheduler answers and the e and SystemVerilog boundary
- Phases: Start work in P02. Accept this cell in P02.
- Must pass first: D28.c1; prefer existing Verilator, Icarus, GHDL, nvc and CIRCT paths.
- Baseline: Use the baseline stated in the rule when a comparison applies.
- Summary: Test independent scheduler expectations and the foundation e and SystemVerilog boundary before runtime implementation. Require at least 50 positive and negative cases per semantic family.
- Rule:
  1. Create an independent foundation clause ledger and expected scheduler cases.
  2. Use UP2 to maintain results through two independent upgrades.
  3. Cover SV nonblocking assignments, delta cycles, time, X, Z, driver resolution, memories, assertions, DPI, VPI, VHPI, SystemC and VHDL.
  4. Settle schedulers before the read-only sample.
  5. Permit no silent conversion of either X or Z to 0.
  6. Establish independent expected truth before runtime implementation.
  7. Pin the foundation e and SystemVerilog boundary interface, versions and event-region mapping.
  8. Pin four-state and value representation, object ownership and lifetime, callbacks and cancellation, reset, seed state and replay.
  9. Require at least 50 legal and 50 race, stale-handle and foreign-state cases per family.
  10. Derive these cases from independent semantics.
  11. Prefer existing Verilator, Icarus, GHDL, nvc and CIRCT paths.
  12. Require at least 50 positive cases and at least 50 negative cases per semantic family.

<a id="D34c1"></a>

#### D34.c1: Select the relational-security proof method
- Phases: Start work in P02. Accept this cell in P02.
- Must pass first: D15.c1, D28.c1. Report obligation-discharge progress each generation.
- Baseline: Use the baseline stated in the rule when a comparison applies.
- Summary: Test sound proof-method selection on actual small L1D and randomized structures before wide-target results are revealed. Apply the S25D relational-security design and kill and redirect criteria in main section 7.
- Rule:
  1. Select the foundation method on actual small L1D and randomized replacement and masking structures.
  2. Compare self-composed product-program relational model checking with unwinding and assume-guarantee proofs.
  3. Include IC3 and constrained Horn clauses in the model-checking comparison.
  4. For randomized cases, compare probabilistic bisimulation with coupling and symbolic probability bounds.
  5. Tie the RTL random-number-generator abstraction to explicit entropy and visibility assumptions.
  6. Machine-check finite probability arithmetic and inductive conditional bounds in Lean, Coq or an equivalent independent proof kernel.
  7. Select first by sound obligation coverage and certificate checks, then by scaling.
  8. Select before wide-target results are revealed.
  9. Distinguish positive, violating, low-entropy and adaptive controls.
  10. Unknown is a research failure, not an empirical bound.
  11. Apply the S25D relational-security design and kill and redirect criteria in main section 7.
  12. Report obligation-discharge progress each generation.

<a id="D35c2a"></a>

#### D35.c2a: Seal decision-service demand before tuning
- Phases: Start work in P01. Accept this cell in P01.
- Must pass first: D27.c1; independently commissioned work inventory, no engine or controller prerequisite, D35.c1 (explanatory context only; no acceptance evidence), D11.c1 (explanatory context only; no acceptance evidence), D07.c1 (explanatory context only; no acceptance evidence), D18.c1 (explanatory context only; no acceptance evidence).
- Baseline: Use the baseline stated in the rule when a comparison applies.
- Summary: Test an independent demand census and versioned intake before scheduling, tuning and confirmation. Set required capacity to the maximum of 10,000 model plus 200 RTL decisions per 30 days and 1.25 times measured 95th-percentile monthly demand per class.
- Rule:
  1. Complete an independent archived or commissioned demand census BEFORE tuning.
  2. Seal checked work per decision, arrivals, per-class deadlines, and 95th-percentile and 99th-percentile tolerances.
  3. Set required capacity to the maximum of 10,000 model plus 200 RTL decisions per 30 days and 1.25 times measured 95th-percentile monthly demand per class.
  4. Use a scenario basis of 20 groups by 25 alternatives by 20 days, with 10 RTL decisions per group.
  5. Derive D07.c1, D11.c1 and D18.c1 floors from counted checking, transport and build work and deadlines.
  6. Use those cell references as explanatory context only.
  7. Treat printed counts as minima, not caps.
  8. Treat the census as a planning receipt.
  9. Require no working scheduler or D35.c1 first decision for the census.
  10. Use D35.c1 as explanatory context only.
  11. Admit fresh active-project decision demand between releases through a dated intake ledger.
  12. Freeze the resulting demand version before each confirmation cohort.
  13. Increased demand can immediately raise required floors for new claims.
  14. It cannot retroactively lower floors or alter an observed cohort.
  15. Outcome-driven additions require a new attempt and reserved error budget.
  16. Keep rejected and deferred requests visible.
  17. Require an independently commissioned work inventory with no engine or controller prerequisite.

## M2: Build checked semantic foundations

Acceptance phases: P03–P05.

<a id="D01c13"></a>

#### D01.c13: The micro-operation model method on sealed six-wide phases before implementation promotion
- Phases: Start work in P04. Accept this cell in P05.
- Must pass first: D09.c1, D03.c1, D21.c1, D27.c8.
- Baseline: Use the baseline stated in the rule when a comparison applies.
- Summary: Test the micro-operation model method on sealed six-wide phases before implementation promotion. Require median cycle errors at most 2%.
- Rule:
  1. Implement the micro-operation model method M27 from the method designs in protocols.md on the sealed six-wide stratum.
  2. On 20 disjoint phases, jointly require detailed rate at least 1 million instructions per second and the cycle-error limits below.
  3. Require median cycle errors at most 2%.
  4. Require 95th-percentile cycle errors at most 5%.
  5. Require exact functional and wrong-path microcases.
  6. Publish the first divergence.
  7. Publish rate and fidelity curves.
  8. Redirect implementation after two failed sealed iterations.
  9. Do not relax final endpoints.

<a id="D01c15"></a>

#### D01.c15: Qualify narrow screening advice with measured error and cost while retaining final model gates
- Phases: Start work in P05. Accept this cell in P05.
- Must pass first: D21.c1, D03.c1, D27.c8.
- Baseline: Use independent RTL anchors.
- Summary: Test narrow screening advice with measured error and cost while retaining final model gates. Require median cycle error at most 10 percent.
- Rule:
  1. On 20 independent held-out parameter sweeps per mechanism, measure analytical queueing, interval and trace-driven screening recipes against independent RTL anchors.
  2. Publish error versus total cost at 1, 5 and 15 minute budgets on the pinned reference host.
  3. For a screening label, require correct direction lower bound at least 0.90.
  4. Require median cycle error at most 10 percent.
  5. Require 95th-percentile cycle error at most 20 percent.
  6. Refuse a decision when its error interval crosses the useful-effect boundary.
  7. Include 20 wrong-direction and cost-omission controls.
  8. This narrow screening receipt cannot replace the final model gates.
  9. Permit early model-only screening on the declared many-hart frame after these screening checks.
  10. Print measured error interval, omitted mechanisms and model-only status with every recommendation.
  11. An unanchored new frame is exploratory only and cannot receive the screening receipt.
  12. No screening receipt supplies Full credit or a timing-qualified many-hart anchor.

<a id="D03c1"></a>

#### D03.c1: Exact causal accounting, interventions and rankings across scalar, wide and shared-resource strata
- Phases: Start work in P03. Accept this cell in P03.
- Must pass first: D09.c1, independent event fixtures; later model joins are consumers, D27.c8, the explanatory context in D03.c3.
- Baseline: Use independently specified event-DAG and max-plus truth and independent event fixtures.
- Summary: Test unattributed cycle fraction at most 2% against independently checked full-run event accounting.
- Rule:
  1. Use independently specified event-DAG and max-plus truth for at least 100 cases across scalar, six-wide, coherent, OS and contending paths.
  2. Require exact critical or tied-path sets and source joins.
  3. Require exact deterministic slack.
  4. Account for retirement, bad speculation, frontend slots and backend slots.
  5. Require at least 98% explained cycles without double counting. This is the complement of the single 2% unattributed-cycle bound.
  6. Cover predictor, fetch, I-cache, ITLB, rename, ROB, RF, ports, dependence, DTLB, L1, L2, DRAM, forwarding, fusion and prefetch.
  7. Use 20 interventions per leaf.
  8. Require count error at most 2 percentage points.
  9. Require at least 95% correct direction on the finite controls.
  10. Join the top five causes to ideal bounds.
  11. Require all 10 finite rankings to retain the known best choice.
  12. Use the explanatory context in D03.c3 for fresh advice.
  13. Add separate eight-wide designs with at least 600 ROB entries, ten-wide designs with at least 1000 ROB entries, four-thread SMT and eight-thread SMT strata.
  14. Require active shared issue, execution, cache and memory contention in these strata.
  15. Apply every original exact-truth, intervention, conservation, unknown-mass, ranking and attribution gate to each applicable stratum.
  16. Require at least 100 independent causal controls per stratum.
  17. Use the same strata and all original bounds for capture costs.
  18. Category 2 primary: Require unattributed cycle fraction at most 2% against independently checked full-run event accounting.

<a id="D03c2"></a>

#### D03.c2: Regression detection and causal attribution under a delta-specific uncertainty budget
- Phases: Start work in P04. Accept this cell in P04.
- Must pass first: D03.c1, D28.c2; absolute accounting never replaces delta gate, D27.c8.
- Baseline: Use the baseline stated in the rule when a comparison applies.
- Summary: Test regression detection and causal attribution under a delta-specific uncertainty budget. Require zero false causes.
- Rule:
  1. Export absolute unknown-cycle mass with every result.
  2. Also export simultaneous unexplained-delta and capture upper bound U.
  3. Accept a regression or optimization cause only if U is at most abs(d) divided by 4.
  4. Require the correct contribution sign.
  5. Require a fresh intervention to remove d within this budget.
  6. Otherwise export "detected; cause unresolved".
  7. Use 40 regressions at 0.25%, 0.5%, 1% and 2%.
  8. Use 40 no-change controls.
  9. Use 20 changes hidden inside 2% unknown mass.
  10. Require zero false causes.
  11. Detect all registered changes more than 0.5%.
  12. After powered expansion, require adjusted correct-attribution lower bound at least 0.90.

<a id="D03c3"></a>

#### D03.c3: Qualify prospective optimization advice and scripted checked time against independently qualified causal workflows
- Phases: Start work in P05. Accept this cell in P05.
- Must pass first: D03.c2, D21.c1, D03.c1, D27.c8.
- Baseline: Use the strongest qualified causal recipe and independently built CPU-team PMU and trace workflow as specified below.
- Summary: Test prospective optimization benefit and secondary checked diagnosis time against independently qualified causal workflows.
- Rule:
  1. Accept optimization advice only after checked benefit, strong baseline and event-attribution method gates pass.
  2. Test prospective advice on hidden independent interventions for each D03.c1 leaf through three generations.
  3. Per mechanism, require power-adjusted direction lower bound at least .95, including ties and negative gains.
  4. Per mechanism, require top-five winner-retention lower bound at least .99.
  5. Per mechanism, require regret upper bound at most the preregistered smallest useful effect in the endpoint units divided by 4.
  6. Retain mandatory known winners exactly.
  7. Mark advice unresolved if uncertainty or unexplained delta is more than the preregistered smallest useful effect in the endpoint units divided by 4.
  8. Such advice cannot recommend a change.
  9. Compare against the strongest qualified full-run cause and intervention recipe under Section 3.1.
  10. Use sampled direction and retention margin .005.
  11. Use the smaller of .02 times baseline regret and the preregistered smallest useful effect in the endpoint units divided by 20 as the regret tolerance.
  12. At zero baseline, use the preregistered smallest useful effect in the endpoint units divided by 20.
  13. Report withheld advice and missed winners.
  14. Include full-run event trace and causal DAG as a mandatory recipe class.
  15. Include PMU top-down plus intervention as a mandatory recipe class.
  16. Include a maintained CPU-team full-run trace, PMU and intervention workflow over the whole relevant feature frame.
  17. Seal per-leaf observations and permitted interventions before R08 (matched work and independent baseline-selection rules) matching and disjoint selection.
  18. Require non-inferior decision quality with margin .005 against that workflow.
  19. Keep unavailable workflows OPEN.
  20. Never replace them with absolute floors.
  21. Require secondary verified checked-time upper ratio at most 0.90 versus the qualified CPU-team PMU and trace workflow.
  22. Keep all other comparison endpoints non-inferior.
  23. Include a TMA-style top-down hierarchy on the RTL event stream as a comparator recipe class.
  24. Include a Konata pipeline-view workflow as a comparator recipe class.
  25. Include a gem5 statistics and intervention workflow as a comparator recipe class.
  26. Pin event maps, commands, versions and operator instructions.
  27. Use R08 to select the strongest qualified recipe on disjoint controls before confirmation.
  28. No unqualified recipe can supply the comparison baseline.
  29. Build and run the CPU-team comparator as an independent implementation under the shared baseline-strength rule.
  30. Pin a published top-down bottleneck hierarchy, complete trace and PMU capture, and causal interventions.
  31. Apply the shared baseline-strength rule before confirmation.
  32. Require the event-attribution method decision in the method designs in protocols.md.
  33. Seal a causal partition for each SMT and shared-resource stratum before outcomes.
  34. Allocate overlapping effects once through explicit interaction terms and counterfactual interventions.
  35. Keep unidentifiable effects in unknown mass.
  36. Require unknown mass at most 5% of total absolute attributed and unknown effect in each stratum.
  37. Require its propagated decision uncertainty at most the smallest useful effect divided by 4.
  38. Withhold advice if either bound fails.
  39. Test at least 20 overlap and cancellation controls per stratum.

<a id="D03c90"></a>

#### D03.c90: Every issue-specific obligation in D03.c90 with its required exact evidence, comparisons and refusal controls
- Phases: Start work in P04. Accept this cell in P04.
- Must pass first: D03.c1, D27.c2, D27.c8.
- Baseline: Use the baseline stated in the rule when a comparison applies.
- Summary: Test every issue-specific obligation in D03.c90 with its required exact evidence, comparisons and refusal controls. Require all 4 numbered rule items.
- Rule:
  1. Apply I90, the source-specific issue-child evidence protocol.
  2. For issue #49, trace wrong-path and predicated-off instructions without false commits.
  3. For issue #98, check enable, overflow and privilege counter transitions against exact event witnesses.
  4. Apply I90 to both issue children.

<a id="D03c4"></a>

#### D03.c4: Portable slot accounting, interactive trace navigation, shared-thread attribution and capture costs
- Phases: Start work in P04. Accept this cell in P04.
- Must pass first: D03.c1, D27.c8, the explanatory context in D18.c2.
- Baseline: Use independently defined slot and max-plus event truth and matched probe-off captures.
- Summary: Test portable slot accounting, interactive trace navigation, shared-thread attribution and capture costs. Require exact results on all 100 semantic controls.
- Rule:
  1. Provide a portable hierarchical slot taxonomy on at least 3 unrelated cores.
  2. Include retiring, bad speculation, frontend-bound and backend-bound slots.
  3. Independently define leaves for D03.c1 mechanisms with conservation and no double counting.
  4. Give every leaf an observation and intervention contract.
  5. Require identical classifications and counts for equivalent microcases.
  6. Refuse unsupported leaves.
  7. Require exact results on all 100 semantic controls.
  8. Keep capture gaps as unknown mass.
  9. Navigate a 1 billion-instruction Konata-class trace for the interactive pipeline child.
  10. Test cold and warm pan, zoom, search and source selection.
  11. Require 95th-percentile interaction time at most 1 s on the pinned D18.c2 interface query-host contract.
  12. Independently check at least 100 joins to cause nodes and waves.
  13. Require zero wrong joins.
  14. Retain wrong-path and flush events.
  15. For the SMT child, require at least 2 threads to share issue, execution, cache and memory resources.
  16. Independently derive per-thread max-plus event truth on at least 100 controls per shared-resource type.
  17. Attribute owner stalls to the owner.
  18. Attribute interference to the competing thread.
  19. Attribute joint stalls to an explicit shared bucket.
  20. Require per-thread attributed plus unknown slots to equal available slots exactly.
  21. Permit no double counting.
  22. Require zero attribution errors on sealed controls.
  23. Require at most 1% unknown slots on sealed controls.
  24. Preserve conservation under flush and thread suspension.
  25. Run probe-off and full probe-on 1 billion-instruction captures for scalar, six-wide, eight-wide and ten-wide strata.
  26. Use identical QH24 (pinned query and interaction host rules) pinned-host allocations for capture-cost tests.
  27. Require adjusted lower checked-rate on-to-off ratio at least .80.
  28. Require encoded capture at most 32 bytes per event.
  29. Require peak capture resident memory at most 4 GiB.
  30. Report all lost events, bytes per event, rate and end-to-end storage cost per stratum.
  31. Require zero dropped mandatory events.
  32. Passive equality alone cannot pass the cost child.
  33. Add separate eight-wide designs with at least 600 ROB entries, ten-wide designs with at least 1000 ROB entries, four-thread SMT and eight-thread SMT strata.
  34. Use active shared issue, execution, cache and memory contention in these strata.
  35. Apply every original exact-truth, intervention, conservation, unknown-mass, ranking and attribution gate to each applicable stratum.
  36. Require at least 100 independent causal controls per stratum.
  37. Use the same strata and all original bounds for capture costs.

<a id="D04c1"></a>

#### D04.c1: Performance-fault and regression diagnosis with explicit unresolved outcomes and no false unchanged-night alarms
- Phases: Start work in P05. Accept this cell in P05.
- Must pass first: D03.c1, D21.c1, D03.c2, D27.c8.
- Baseline: Use the baseline stated in the rule when a comparison applies.
- Summary: Test performance-fault and regression diagnosis with explicit unresolved outcomes and no false unchanged-night alarms. Require zero fires on seven unchanged nights.
- Rule:
  1. Find all thirty of 30 performance faults.
  2. For all 30, identify the correct leaf or explicitly report unresolved.
  3. Count unresolved cases as noncompletion.
  4. For 20 per-commit regressions, identify the correct leaf for all 20 or explicitly report unresolved.
  5. Require zero fires on seven unchanged nights.
  6. For 20 equal-counter and different-cause pairs, request discriminating data or abstain.
  7. Use D03.c2 for final causal claims.

<a id="D04c2"></a>

#### D04.c2: Qualify event mappings, counter bias and uncertainty before magnitude claims or advice
- Phases: Start work in P03. Accept this cell in P03.
- Must pass first: D28.c2; exact comparator system identities, D27.c8.
- Baseline: Use exact comparator-system identities, independent event witnesses and exact integer counts where specified.
- Summary: Test event mappings, counter bias and uncertainty before magnitude claims or advice. Require consumer refusal when a rank-correct mapping with 2 percentage-point error reverses a 0.5% decision.
- Rule:
  1. Report RTL and PMU event mappings for work, speculation, recovery, cache, translation, occupancy and traffic.
  2. Use 20 serialized, contended and recovery fixtures per event plus wrong-field mutants.
  3. Check privilege, fusion, vector, overflow, enable and multiplexing.
  4. Compare exact HPM counts and endpoints as integers.
  5. Reserve EXACT for checked semantic and count equality under a declared relation.
  6. Label physical PMU mappings with at most 2 percentage-point error CALIBRATED-APPROXIMATE.
  7. Export absolute bias and uncertainty in event units, event-share units and decision units.
  8. Propagate bias and uncertainty into every magnitude query.
  9. Rank-only labels cannot support magnitude claims.
  10. Require consumer refusal when a rank-correct mapping with 2 percentage-point error reverses a 0.5% decision.
  11. Require exact integer and count controls for zero-bias claims, not this allowance.
  12. Use 10 host repeats per microbenchmark.
  13. Require powered per-class Spearman at least 0.8.
  14. Refuse unavailable counters and cross-ISA event aliases.
  15. Use at least 30 independent event identities per rank class.
  16. Expand identities under R07 (preregistered statistical validity and joint-power rules) statistical power rules for lower Spearman bound at least 0.8.
  17. Repeats do not increase identity n.
  18. For advice, require CALIBRATED-APPROXIMATE mappings per event family.
  19. Require measured absolute normalized bias upper bound at most 2%.
  20. Convert the event bias to endpoint units with the independently sealed sensitivity bound S, in endpoint units per event, and the reference event count N. Require the normalized bias bound times N times S at most the preregistered smallest useful effect divided by 4.
  21. Propagate uncertainty and bias through the same sensitivity relation. Require their sum in endpoint units at most half the claimed gain in those units.
  22. For zero-baseline events, require zero or a sealed absolute task budget.
  23. Keep rank-only Spearman evidence diagnostic.
  24. It cannot steer advice.
  25. For event-share bias, multiply the share error by the sealed total event count before applying S. Reject unavailable sensitivity bounds and unit changes that alter the verdict.
  26. The 2 percentage-point share ceiling and the 2% normalized count-bias ceiling have different denominators. Report both denominators. Neither ceiling replaces the propagated endpoint-error bound.

<a id="D04c4"></a>

#### D04.c4: Per-commit latency contracts and exact detection of contract changes
- Phases: Start work in P05. Accept this cell in P05.
- Must pass first: D04.c2, D21.c1, D27.c8.
- Baseline: Use independently specified latency contracts.
- Summary: Test per-commit latency contracts and exact detection of contract changes. Use 20 activated off-by-one and contract-drift controls per mechanism.
- Rule:
  1. Use per-commit dependent and serialized microbenchmarks independently specified under R04 (independent requirement-derived expectations with distinct authors and recorded ancestry).
  2. Cover load-to-use, branch redirect, replay, bypass, and queue and port initiation.
  3. Require exact deterministic cycle counts on every declared adapter configuration.
  4. Fail CI for any undeclared change.
  5. Report conservative intervals for variable latency, never EXACT.
  6. Use 20 activated off-by-one and contract-drift controls per mechanism.
  7. Use 20 unchanged controls per mechanism.
  8. Require exact classification of all controls.

<a id="D05c1"></a>

#### D05.c1: Stable semantic identities and source navigation through transformations, reloads and upgrades
- Phases: Start work in P03. Accept this cell in P03.
- Must pass first: D27.c1, D05.c0, D27.c8.
- Baseline: Use the baseline stated in the rule when a comparison applies.
- Summary: Test stable semantic identities and source navigation through transformations, reloads and upgrades. Require exact values, types and maps after reload and two upgrades.
- Rule:
  1. Provide stable type, source and hierarchy IDs through Metals, slang/Verible, CIRCT/FIRRTL and GHDL.
  2. Test 100 transformations.
  3. Test 30 source and connectivity answers per importer.
  4. Require exact values, types and maps after reload and two upgrades.
  5. Cover banked memories, aggregates, fixed point, temporaries and opaque boundaries.
  6. Require completion 95th-percentile at most 200 ms.
  7. Require navigation at most 1 s at 100 thousand signals.
  8. Require navigation at most 2 s at 1 million signals.

<a id="D05c2a"></a>

#### D05.c2a: Cold indexing scale and comparison bounds on real language and mixed-language projects
- Phases: Start work in P04. Accept this cell in P04.
- Must pass first: D05.c1; scripted runners, D27.c8.
- Baseline: Use Sigasi and DVT for applicable SV and VHDL, and Metals, sbt and Bloop for Scala.
- Summary: Test cold indexing scale and comparison bounds on real language and mixed-language projects. Require cold index and elaboration 95th-percentile at most 300 s.
- Rule:
  1. Use real 1 million-signal projects in each language and a mixed tree.
  2. Use the 16-core, 64-GiB, NVMe reference host.
  3. Require cold index and elaboration 95th-percentile at most 300 s.
  4. Report curves through 5 million signals.
  5. Compare index time and resident memory against Sigasi and DVT for applicable SV and VHDL.
  6. Compare against Metals, sbt and Bloop for Scala.
  7. Use Section 3.1 comparison margins at most 1.02.
  8. Count all setup and build failures.

<a id="D05c2b"></a>

#### D05.c2b: Source and hierarchy refresh deadlines and generation-safe queries
- Phases: Start work in P04. Accept this cell in P04.
- Must pass first: D05.c1; scripted runners, D27.c8, the explanatory context in D05.c2a.
- Baseline: Use each applicable baseline from the D05.c2a interface contract.
- Summary: Test source and hierarchy refresh deadlines and generation-safe queries. Require source-refresh 95th-percentile at most 30 s.
- Rule:
  1. Use the same project frame as the interface contract from D05.c2a.
  2. Require source-refresh 95th-percentile at most 30 s.
  3. Require parameter and hierarchy refresh at most 90 s.
  4. Require refresh time at most 1.02 of each applicable D05.c2a interface baseline under Section 3.1.
  5. During reload, return the pinned generation or explicit pending status for every query.
  6. Require zero stale joins in 100 edit and reload controls.

<a id="D05c2d"></a>

#### D05.c2d: Qualify generated semantic scale only when the audited real-project frame is unavailable
- Phases: Start work in P04. Accept this cell in P04.
- Must pass first: D05.c1; scripted runners, D27.c8.
- Baseline: Use the baseline stated in the rule when a comparison applies.
- Summary: Test generated semantic scale only when the audited real-project frame is unavailable. If no real 1 million-signal project exists, use a sealed substitute under Section 3.4.
- Rule:
  1. For each language and mixed tree, conduct a census.
  2. If no real 1 million-signal project exists, use a sealed substitute under Section 3.4.
  3. Seal memory, aggregate, instance, cross-language and generator complexity.
  4. Repeated dead nets do not qualify.
  5. Require an independent checker to verify live connectivity and queries.
  6. Use generated receipts to qualify semantic scale only.
  7. Keep real-project productivity OPEN.

<a id="D05c4"></a>

#### D05.c4: Single-specification CSR generation and exact detection of specification and RTL mutants
- Phases: Start work in P04. Accept this cell in P04.
- Must pass first: D05.c1, independent CSR semantics, D27.c8.
- Baseline: Use the baseline stated in the rule when a comparison applies.
- Summary: Test single-specification CSR generation and exact detection of specification and RTL mutants. Detect all 30 specification and RTL mutants.
- Rule:
  1. Generate CSR RTL, headers, documents and reference configuration from one versioned specification.
  2. Independently check every declared side effect, alias, width and reset.
  3. Detect all 30 specification and RTL mutants.

<a id="D05c90"></a>

#### D05.c90: Every issue-specific obligation in D05.c90 with its required exact evidence, comparisons and refusal controls
- Phases: Start work in P04. Accept this cell in P04.
- Must pass first: D05.c1, D27.c2, D27.c8.
- Baseline: Use independent queries, elaboration and raw signals for the issue-specific checks.
- Summary: Test every issue-specific obligation in D05.c90 with its required exact evidence, comparisons and refusal controls. For issue #101, give every documented limit one owner, disposition and next check without a contradictory tracker.
- Rule:
  1. Apply I90, the source-specific issue-child evidence protocol.
  2. For issue #24, require cross-panel generation, source and status joins to match independent queries exactly.
  3. For issue #26, query non-Spinal designs without generic-code edits.
  4. For issue #44, remove BOOM entry points.
  5. Consume only the versioned design database.
  6. For issue #55, answer SV hierarchy, type and source queries against independent elaboration.
  7. For issue #69, resolve identical design-database identities in trace and wave consumers.
  8. For issue #70, preserve connectivity on every named design.
  9. For issue #83, verify typed interactive values and navigation against raw signals.
  10. For issue #101, give every documented limit one owner, disposition and next check without a contradictory tracker.
  11. For issue #120, reproduce every vendored viewer limit.
  12. Record whether each limit is fixed or deferred.
  13. Apply I90 to every issue child.

<a id="D05c6"></a>

#### D05.c6: A shared immutable semantic index under concurrent clients and conflicting schedules
- Phases: Start work in P05. Accept this cell in P05.
- Must pass first: D05.c2a, D05.c2b, D27.c8.
- Baseline: Use applicable Sigasi and DVT team-index flows.
- Summary: Test a shared immutable semantic index under concurrent clients and conflicting schedules. Require source-refresh 95th-percentile at most 30 s.
- Rule:
  1. Use one immutable shared index generation for 32 concurrent clients on the QH24 (pinned query and interaction host rules) pinned service allocation.
  2. Use separate pinned clients.
  3. Require source-refresh 95th-percentile at most 30 s.
  4. Require hierarchy refresh at most 90 s.
  5. Test at least 100 conflicting edit, reload, drop and reconnect schedules.
  6. Require zero stale cross-client joins.
  7. Name the generation or pending status in each answer.
  8. Compare refresh time, query time, service resident memory and total allocated cost under Section 3.1.
  9. Use applicable Sigasi and DVT team-index flows as comparators.
  10. Require the semantic-index, language-server and elaboration-debug method decision in the method designs in protocols.md before this runtime result can close.

<a id="D07c4"></a>

#### D07.c4: Select and pin a foundation engine or complete fallback after evaluating every required candidate
- Phases: Start work in P03. Accept this cell in P03.
- Must pass first: D09.c1 scalar transitions, D31.c1 independent expectations, D27.c8, the explanatory context in D08.c1.
- Baseline: Use the named candidate frame and pinned predecessor executable, then VCS and Xcelium for complete promotion.
- Summary: Select and pin a foundation engine or complete fallback after evaluating every required candidate. Require lower checked-rate ratio at least 1.10.
- Rule:
  1. Audit Verilator, Icarus and CIRCT/Arcilator against the complete frozen runtime denominator for foundation engine selection and scalar execution bootstrap.
  2. Prefer Verilator if the full architecture fits.
  3. Otherwise select by mandatory semantic coverage, checked-job prototype rate, then maintainable patch boundaries.
  4. Deliver basic scalar execution and capture with exact directed state, event and output controls.
  5. Use independent region expectations.
  6. Treat this as intermediate support, not full SV or UVM support.
  7. Evaluate Verilator hierarchical and partitioned threads.
  8. Evaluate RepCut-style replication partitioning.
  9. Evaluate ESSENT-style acyclic and activity-aware scheduling on the Verilog path.
  10. Evaluate CIRCT/Arcilator partitioning.
  11. Evaluate RTLflow and GEM-class GPU methods.
  12. Seal scalar, large and manycore designs before comparison.
  13. Seal budgets for 1, 2, 4, 8 and 16 threads and GPU hosts and devices before comparison.
  14. Check exact state, event, region and output equivalence.
  15. Record unsupported semantics as failures within each candidate frame, not supported capability.
  16. Measure useful checked work per second.
  17. Measure core-seconds and device-seconds.
  18. Measure cold and incremental builds, transfer, resident memory, storage and visibility cost.
  19. Use R08 (matched work and independent baseline-selection rules) matching and disjoint selection first on complete semantic eligibility, then checked-rate and total-cost comparison endpoints.
  20. Evaluate every named method even if candidate selection fails.
  21. Pin selected and predecessor source, build and options hashes in the receipt.
  22. Require full semantics for supported promotion.
  23. Require lower checked-rate ratio at least 1.10.
  24. Require non-inferior total-cost ratio at most 1.02.
  25. Then require all unchanged runtime and UVM strata.
  26. If no candidate qualifies for the full denominator, implement FALLBACK-EVENT24, the maintained open event-kernel fallback.
  27. If no candidate qualifies for the full denominator, combine a slang typed SV frontend with a new four-state IEEE 1800 event-region kernel.
  28. If no candidate qualifies for the full denominator, provide a constraint solver, class and object runtime, SVA, coverage and DPI/VPI scheduler in that fallback.
  29. If no candidate qualifies for the full denominator, preserve delta-cycle ordering, reactive and NBA regions and deterministic state serialization.
  30. If no candidate qualifies for the full denominator, use Verilator as an optional acceleration backend only for proved eligible two-state partitions.
  31. If no candidate qualifies for the full denominator, execute all other semantics in the kernel.
  32. If no candidate qualifies for the full denominator, use one integrated executable path to run unchanged full benches.
  33. If no candidate qualifies for the full denominator, seal boundary state.
  34. If no candidate qualifies for the full denominator, independently check every handoff under the explanatory context in D08.c1.
  35. Retain all named candidate evaluations, including failed ones.
  36. If no candidate qualifies for the full denominator, qualify the new kernel against the same clauses, UVM tests and VCS and Xcelium gates.
  37. Permit bootstrap selection to close as fallback-selected.
  38. Supported promotion cannot close without full semantics and original speed and cost gates.
  39. Use the pinned scalar prototype as its speed-up baseline.
  40. Without a predecessor benchmark, keep that promotion OPEN, not waived.
  41. Pin the fallback executable source, build and options generation at selection.
  42. Use the scalar prototype as evidence only for scalar geometry.
  43. For any larger design, rerun that same executable generation on identical larger RTL before forming a speed-up ratio.
  44. Reject different-design ratios as invalid.

<a id="D07c10"></a>

#### D07.c10: Resolved nets, event regions, timing and mixed-language boundaries against exact independent traces
- Phases: Start work in P04. Accept this cell in P04.
- Must pass first: D07.c4, D31.c1, D27.c8.
- Baseline: Use the baseline stated in the rule when a comparison applies.
- Summary: Test resolved nets, event regions, timing and mixed-language boundaries against exact independent traces. Require zero mismatches.
- Rule:
  1. Implement four-state resolved nets, event-region scheduling, time and delay, clocking, program and reactive sampling, and VHDL mixed-language boundaries.
  2. Use at least 50 positive, negative and race controls for every frozen clause family.
  3. Require exact independent event traces.
  4. Require zero mismatches.

<a id="D07c11"></a>

#### D07.c11: Object, dynamic-process and foreign-callback semantics with explicit unsupported-operation refusal
- Phases: Start work in P05. Accept this cell in P05.
- Must pass first: D07.c10, D27.c8.
- Baseline: Use the baseline stated in the rule when a comparison applies.
- Summary: Test object, dynamic-process and foreign-callback semantics with explicit unsupported-operation refusal. Use at least 50 positive and negative controls per clause family.
- Rule:
  1. Implement classes, inheritance, polymorphism, interfaces, dynamic containers and processes, and DPI/VPI/VHPI foreign callbacks.
  2. Use at least 50 positive and negative controls per clause family.
  3. Require exact expected values, lifetime and ordering.
  4. Refuse unsupported operations.

<a id="D07c9"></a>

#### D07.c9: Qualify the four-state kernel prototype, feature budgets and matched-design speed before promotion
- Phases: Start work in P04. Accept this cell in P04.
- Must pass first: D07.c4, D31.c1, D27.c8, the explanatory context in D07.c2.
- Baseline: Use the pinned scalar fallback executable generation on identical six-wide RTL, not different DUT geometry.
- Summary: Test the four-state kernel prototype, feature budgets and matched-design speed before promotion. Require zero event and state differences.
- Rule:
  1. Build the architecture and budgets in the main four-state event-kernel design K25 for its design and prototype decision.
  2. Keep design parameters as children of this cell.
  3. Use unchanged coherent RTL with at least 6-wide geometry and at least 400 ROB entries.
  4. Activate four-state regions.
  5. Use at least 50 controls per X-resolution, NBA and reactive, class, constraints, SVA, coverage and foreign-call family.
  6. Require zero event and state differences.
  7. Require prototype checked rate at least 2 kHz on 16 cores and 64 GiB.
  8. Require rate-ratio lower bound at least 1.10 versus the pinned scalar fallback baseline.
  9. Measure each K25 feature budget.
  10. Measure build and visibility costs.
  11. Block promotion for any missing budget or semantic control.
  12. Follow K25 redirect criteria.
  13. Permit no dropping of final VCS and Xcelium gates.
  14. Use the pinned fallback EXECUTABLE generation as the scalar fallback baseline, not scalar DUT geometry.
  15. Run the baseline and candidate on identical six-wide RTL and design hash.
  16. Use identical bench hash, observations, reference path and useful-work interval.
  17. Reject at least 20 mismatched-design ratio controls.
  18. Keep scalar-DUT measurements separate.
  19. On the 16-core, 64-GiB host, require K25 four-state core-execution absolute floor of 20 kHz for scalar.
  20. Require 4 kHz for large-OoO.
  21. Require 2 kHz for six-wide-coherent.
  22. Require 1 kHz for manycore8.
  23. Require 0.4 kHz for manycore16.
  24. Measure uninstrumented four-state core execution against that same run frame.
  25. Measure each combined overhead against that frame.
  26. Apply final checked floors in the explanatory context in D07.c2.
  27. Treat the absolute floors as engineering allocations, not measured vendor results.
  28. Derive the scalar 20 kHz floor from a 1 billion-cycle job within 50000 seconds of core execution.
  29. Derive the 4 kHz, 2 kHz, 1 kHz and 0.4 kHz floors from geometry slowdown allowances of 5, 10, 20 and 50 relative to that scalar allocation.
  30. Archive the allocation calculation and run-frame identity before tuning.
  31. Keep all checked-cost overhead and final vendor comparisons mandatory.

<a id="D09c2"></a>

#### D09.c2: Architectural-proof completeness and checked proof throughput against both required formal comparators
- Phases: Start work in P03. Accept this cell in P03.
- Must pass first: D09.c1; ACT4 expected outputs, D28.c2, D27.c8.
- Baseline: Use ACT4 expected outputs and the Siemens Questa Processor / OneSpin product lineage and, separately, Axiomise formalISA for architectural proofs.
- Summary: Test checked conclusive obligations per total core-hour lower ratio at least 1.10 against each Siemens Questa Processor / OneSpin and Axiomise formalISA on the complete pinned architectural-proof frame.
- Rule:
  1. Map every applicable ACT4 ID to exact output and disposition.
  2. Require zero unexplained dispositions.
  3. Detect all activated missing-state controls.
  4. Permit tool success to be a correctly reported DUT defect.
  5. Do not require core repair.
  6. Require D28.c2 preservation for original-DUT claims.
  7. Compare ISA-proof completeness, capacity, proof time, construction effort and maintenance effort under Section 3.1.
  8. Use the Siemens Questa Processor / OneSpin product lineage and, separately, Axiomise formalISA on the whole relevant frame.
  9. Apply exact mandatory semantics and Section 3.1 margins.
  10. Compare proofs, not only simulation tests.
  11. Preserve exact completeness and every non-inferior gate.
  12. Keep new-extension and specification-upgrade tasks as separate required children.
  13. Whole-core refinement cannot supply this receipt.
  14. Category 5 primary: Require checked conclusive obligations per total core-hour lower ratio at least 1.10 against each Siemens Questa Processor / OneSpin and Axiomise formalISA on the complete pinned architectural-proof frame.

<a id="D09c90"></a>

#### D09.c90: Every issue-specific obligation in D09.c90 with its required exact evidence, comparisons and refusal controls
- Phases: Start work in P03. Accept this cell in P03.
- Must pass first: D09.c1, D27.c2, D27.c8.
- Baseline: Use independent clause partitions, translation expectations and pinned ISA specifications.
- Summary: Test every issue-specific obligation in D09.c90 with its required exact evidence, comparisons and refusal controls. Require all 15 numbered rule items.
- Rule:
  1. Apply I90, the source-specific issue-child evidence protocol.
  2. For issue #48, preserve ABI, ELF XLEN, extension options and expected dispositions in each ACT4, riscv-dv and TestRIG source.
  3. For issue #64, independently map Sail clauses to generated formal checks with nonvacuity.
  4. For issue #75, preserve all vector-suite masks and partial-fault outputs.
  5. For issue #80, reject unsupported combinations with an exact ISA version and option manifest.
  6. For issue #82, derive expected bins from independent clause partitions.
  7. For issue #84, match Sv39 leaf, walk and fault effects to independent translation.
  8. For issue #85, match CSR legal, WARL, WPRI and side effects to the specification.
  9. For issue #99, expose stale translations through ASID, global and invalidation cases.
  10. For issue #104, cover every RVA23 and RVB23 obligation in the profile ledger.
  11. For issue #129, preserve atomicity and faults in concurrent A/D updates.
  12. For issue #139, gate every state access with privilege controls.
  13. For issue #141, invalidate all affected descendants on specification upgrades.
  14. Preserve dispositions on those upgrades.
  15. Apply I90 to every issue child.

<a id="D09c3"></a>

#### D09.c3: Complete mandatory Sail clause coverage with independently authored omission controls
- Phases: Start work in P05. Accept this cell in P05.
- Must pass first: D09.c2, D27.c8.
- Baseline: Use the baseline stated in the rule when a comparison applies.
- Summary: Test complete mandatory Sail clause coverage with independently authored omission controls. Mandatory coverage is exactly 100 percent, measured as discharged mandatory clauses divided by all mandatory clauses.
- Rule:
  1. Enumerate mandatory Sail functions and clauses for every advertised ISA option and cross-clause partition.
  2. Bind each to discharged architectural obligations.
  3. Mandatory coverage is exactly 100 percent, measured as discharged mandatory clauses divided by all mandatory clauses.
  4. Unsupported options stay visible and OPEN.
  5. Use independently authored omission controls that remove one obligation per clause family.
  6. Require all these controls to fail.
  7. Proof throughput cannot close a missing architectural clause.

<a id="D10c2"></a>

#### D10.c2: Target applicability, certification interchange, specification-update turnaround and exact ratification intake
- Phases: Start work in P05. Accept this cell in P05.
- Must pass first: D10.c1 inventory, D27.c2 scope checks, D27.c8.
- Baseline: Use independent official ACT samples and matched Questa Processor and Axiomise specification-update flows.
- Summary: Test target applicability, certification interchange, specification-update turnaround and exact ratification intake. Require adjusted turnaround ratio at most 1.02.
- Rule:
  1. Create an applicability cell for each advertised target and extension.
  2. Independently prove absence of relevant state and advertised capability before marking not applicable.
  3. Close only that target's applicability cell, not global V or H tool capability.
  4. Automatically reopen that target applicability cell when the target gains relevant state or advertises support.
  5. Permit no failure-based not-applicable status.
  6. Keep certification-process evidence separate.
  7. Export a version-pinned ACT certification interchange with all required signature fields, results and waivers from controlled fixtures, and do not use a human signature as a gate.
  8. Validate its schema.
  9. Round-trip it against independent official samples.
  10. Refuse incomplete certification claims.
  11. Limit tool acceptance to format conformance, never self-issued certification.
  12. For each of two independent ratified upgrades, seal receipt of the published change as specification-update time zero.
  13. Deliver independently checked reference transitions, checks, documents and all affected cross-clause regressions within 30 calendar days.
  14. Measure total elapsed time and active effort, including failed revisions.
  15. Compare matched change classes with Questa Processor and Axiomise flows.
  16. Require adjusted turnaround ratio at most 1.02.
  17. Require effort ratio at most 1.15.
  18. Keep the update OPEN for missing reference agreement.
  19. No stale check can pass.
  20. For exact ratification intake, publish a versioned clause inventory within 30 calendar days of each official newly ratified extension.
  21. Include the option map, source ancestry and affected test obligations.
  22. Treat completion as inventory intake, not implementation support.
  23. Keep this child OPEN for late or omitted clauses.
  24. Test 20 dated intake histories.
  25. Test 20 omission or backdating controls.
  26. Apply the 30 calendar-day intake and implementation-turnaround duties to ratified changes received between seal and release.
  27. Use UNPINNED-EXTENSION for each unpinned extension and refuse support claims for it.
  28. Invalidate affected receipts and seal a new inventory before claiming the changed extension.

<a id="D10c3"></a>

#### D10.c3: Cache-management semantics and complete effects against independent references without requiring core repair
- Phases: Start work in P05. Accept this cell in P05.
- Must pass first: D10.c1, D12.c1, D09.c1, D11.c1, D27.c8.
- Baseline: Use independently expected semantics, D09.c1 complete-state checks and D11.c1 references.
- Summary: Test cache-management semantics and complete effects against independent references without requiring core repair. Require exactly zero wrong acceptances.
- Rule:
  1. For CMO issue #137, pin cbo.clean, cbo.flush, cbo.inval, cbo.zero and prefetch semantics.
  2. Pin block size and alignment, privilege and environment enable, PMA and access faults, guest translation and coherent DMA interactions.
  3. Independently specify legal, illegal, fault and partial-effect outcomes for at least 30 cases per operation per context.
  4. Include 20 stale-data, permission and zeroing mutants.
  5. Require exactly zero wrong acceptances.
  6. Require exactly zero missing mandatory effects.
  7. Use D09.c1 complete-state and D11.c1 references to report implementation defects as defects.
  8. Require no core repair dependency.

<a id="D10c90"></a>

#### D10.c90: Every issue-specific obligation in D10.c90 with its required exact evidence, comparisons and refusal controls
- Phases: Start work in P05. Accept this cell in P05.
- Must pass first: D10.c1, D27.c2, D27.c8.
- Baseline: Use the baseline stated in the rule when a comparison applies.
- Summary: Test every issue-specific obligation in D10.c90 with its required exact evidence, comparisons and refusal controls. Require zero mandatory misses.
- Rule:
  1. Apply I90, the source-specific issue-child evidence protocol.
  2. For issue #114, compare all guest and host state and partial effects.
  3. For issue #140, preserve permissions, fault priority and guest metadata in both translation stages.
  4. For issue #147, check Sv48 canonicality, walk and fault cases.
  5. For issue #148, check Svpbmt attributes across coherence and PMA.
  6. For issue #154, check Sv32 XLEN, walk and fault cases.
  7. For issue #158, check IMSIC guest and hart delivery and claim races.
  8. For issue #159, check timer delegation and compare races.
  9. For issue #164, check Svnapot alignment and invalidation.
  10. For issue #165, check APLIC direct and MSI routing and pending races.
  11. For issue #166, check NMI and recoverable-error priority and entry.
  12. For issue #170, check CAS atomicity and fault priority.
  13. For issue #171, check Sv57 canonicality, walk and fault cases.
  14. For issue #174, check landing-pad transitions and forbidden targets.
  15. For issue #175, check shadow-stack access and return faults.
  16. For issue #176, check the state-enable privilege hierarchy.
  17. For issue #177, check environment-configuration gates and read-only behavior.
  18. For issue #179, check pointer masking and address and fault ordering.
  19. For issue #181, check RAS status, injection, acknowledgment and concurrent errors.
  20. For issue #186, check CLIC and ACLIC vectoring, preemption, level, edge and acknowledge races.
  21. For each extension child, require independent clause partitions.
  22. Require legal transitions.
  23. Require every specified fault priority and cross-clause combination.
  24. Require exact state and effects.
  25. Require zero mandatory misses.
  26. Apply I90 to every issue child.

<a id="D10c1p1"></a>

#### D10.c1p1: Complete V family obligations, option partitions and cross-clause controls under the pinned ISA protocol
- Phases: Start work in P04. Accept this cell in P04.
- Must pass first: D09.c1, D11.c1, D27.c8, the explanatory context in D11.c8.
- Baseline: Use the baseline stated in the rule when a comparison applies.
- Summary: Test complete V family obligations, option partitions and cross-clause controls under the pinned ISA protocol. Require zero misses.
- Rule:
  1. Apply ISA24, the pinned ISA extension and cross-clause protocol, to family V.
  2. Create separate clause and tuple children for every instruction, option, state, fault and profile obligation.
  3. Require legal, illegal and omission controls.
  4. Maintain results through two specification or model upgrades.
  5. Use the pinned profile source to determine mandatory and optional status.
  6. Permit no implied extension.
  7. Require zero misses.
  8. For EACH advertised option partition, require at least 100 legal controls.
  9. For that partition, require at least 100 illegal controls.
  10. For that partition, require at least 100 boundary and fault controls.
  11. For that partition, require at least 100 cross-clause controls.
  12. Enumerate all finite legal option values.
  13. For unbounded parameter ranges, prove a semantics-preserving partition.
  14. Test every boundary and representative of that partition.
  15. Without a partition proof, mark the range unsupported.
  16. For V, enumerate all supported combinations of VLEN, SEW, LMUL, masking, tail, segment and fault-only-first behavior.
  17. For H, enumerate privilege, translation-stage, trap and interrupt-delegation combinations.
  18. Use Sail and Spike as the reference pair where both implement the family.
  19. Otherwise, require Sail and the independent lineage in the explanatory context in D11.c8.
  20. Keep the child OPEN for unsupported reference options.

<a id="D10c1p2"></a>

#### D10.c1p2: Complete H family obligations, option partitions and cross-clause controls under the pinned ISA protocol
- Phases: Start work in P04. Accept this cell in P04.
- Must pass first: D09.c1, D11.c1, D27.c8, the explanatory context in D11.c8.
- Baseline: Use the baseline stated in the rule when a comparison applies.
- Summary: Test complete H family obligations, option partitions and cross-clause controls under the pinned ISA protocol. Require zero misses.
- Rule:
  1. Apply ISA24, the pinned ISA extension and cross-clause protocol, to family H.
  2. Create separate clause and tuple children for every instruction, option, state, fault and profile obligation.
  3. Require legal, illegal and omission controls.
  4. Maintain results through two specification or model upgrades.
  5. Use the pinned profile source to determine mandatory and optional status.
  6. Permit no implied extension.
  7. Require zero misses.
  8. For EACH advertised option partition, require at least 100 legal controls.
  9. For that partition, require at least 100 illegal controls.
  10. For that partition, require at least 100 boundary and fault controls.
  11. For that partition, require at least 100 cross-clause controls.
  12. Enumerate all finite legal option values.
  13. For unbounded parameter ranges, prove a semantics-preserving partition.
  14. Test every boundary and representative of that partition.
  15. Without a partition proof, mark the range unsupported.
  16. For V, enumerate all supported combinations of VLEN, SEW, LMUL, masking, tail, segment and fault-only-first behavior.
  17. For H, enumerate privilege, translation-stage, trap and interrupt-delegation combinations.
  18. Use Sail and Spike as the reference pair where both implement the family.
  19. Otherwise, require Sail and the independent lineage in the explanatory context in D11.c8.
  20. Keep the child OPEN for unsupported reference options.

<a id="D10c1p3"></a>

#### D10.c1p3: Complete Sv32, Sv39, Sv48 and Sv57 family obligations, option partitions and cross-clause controls under the pinned ISA protocol
- Phases: Start work in P04. Accept this cell in P04.
- Must pass first: D09.c1, D11.c1, D27.c8, the explanatory context in D11.c8.
- Baseline: Use the baseline stated in the rule when a comparison applies.
- Summary: Test complete Sv32, Sv39, Sv48 and Sv57 family obligations, option partitions and cross-clause controls under the pinned ISA protocol. Require zero misses.
- Rule:
  1. Apply ISA24, the pinned ISA extension and cross-clause protocol, to family Sv32, Sv39, Sv48 and Sv57.
  2. Create separate clause and tuple children for every instruction, option, state, fault and profile obligation.
  3. Require legal, illegal and omission controls.
  4. Maintain results through two specification or model upgrades.
  5. Use the pinned profile source to determine mandatory and optional status.
  6. Permit no implied extension.
  7. Require zero misses.
  8. For EACH advertised option partition, require at least 100 legal controls.
  9. For that partition, require at least 100 illegal controls.
  10. For that partition, require at least 100 boundary and fault controls.
  11. For that partition, require at least 100 cross-clause controls.
  12. Enumerate all finite legal option values.
  13. For unbounded parameter ranges, prove a semantics-preserving partition.
  14. Test every boundary and representative of that partition.
  15. Without a partition proof, mark the range unsupported.
  16. For V, enumerate all supported combinations of VLEN, SEW, LMUL, masking, tail, segment and fault-only-first behavior.
  17. For H, enumerate privilege, translation-stage, trap and interrupt-delegation combinations.
  18. Use Sail and Spike as the reference pair where both implement the family.
  19. Otherwise, require Sail and the independent lineage in the explanatory context in D11.c8.
  20. Keep the child OPEN for unsupported reference options.

<a id="D10c1p4"></a>

#### D10.c1p4: Complete Svpbmt and Svnapot family obligations, option partitions and cross-clause controls under the pinned ISA protocol
- Phases: Start work in P04. Accept this cell in P04.
- Must pass first: D09.c1, D11.c1, D27.c8, the explanatory context in D11.c8.
- Baseline: Use the baseline stated in the rule when a comparison applies.
- Summary: Test complete Svpbmt and Svnapot family obligations, option partitions and cross-clause controls under the pinned ISA protocol. Require zero misses.
- Rule:
  1. Apply ISA24, the pinned ISA extension and cross-clause protocol, to family Svpbmt and Svnapot.
  2. Create separate clause and tuple children for every instruction, option, state, fault and profile obligation.
  3. Require legal, illegal and omission controls.
  4. Maintain results through two specification or model upgrades.
  5. Use the pinned profile source to determine mandatory and optional status.
  6. Permit no implied extension.
  7. Require zero misses.
  8. For EACH advertised option partition, require at least 100 legal controls.
  9. For that partition, require at least 100 illegal controls.
  10. For that partition, require at least 100 boundary and fault controls.
  11. For that partition, require at least 100 cross-clause controls.
  12. Enumerate all finite legal option values.
  13. For unbounded parameter ranges, prove a semantics-preserving partition.
  14. Test every boundary and representative of that partition.
  15. Without a partition proof, mark the range unsupported.
  16. For V, enumerate all supported combinations of VLEN, SEW, LMUL, masking, tail, segment and fault-only-first behavior.
  17. For H, enumerate privilege, translation-stage, trap and interrupt-delegation combinations.
  18. Use Sail and Spike as the reference pair where both implement the family.
  19. Otherwise, require Sail and the independent lineage in the explanatory context in D11.c8.
  20. Keep the child OPEN for unsupported reference options.

<a id="D10c1p5"></a>

#### D10.c1p5: Complete Zacas family obligations, option partitions and cross-clause controls under the pinned ISA protocol
- Phases: Start work in P04. Accept this cell in P04.
- Must pass first: D09.c1, D11.c1, D27.c8, the explanatory context in D11.c8.
- Baseline: Use the baseline stated in the rule when a comparison applies.
- Summary: Test complete Zacas family obligations, option partitions and cross-clause controls under the pinned ISA protocol. Require zero misses.
- Rule:
  1. Apply ISA24, the pinned ISA extension and cross-clause protocol, to family Zacas.
  2. Create separate clause and tuple children for every instruction, option, state, fault and profile obligation.
  3. Require legal, illegal and omission controls.
  4. Maintain results through two specification or model upgrades.
  5. Use the pinned profile source to determine mandatory and optional status.
  6. Permit no implied extension.
  7. Require zero misses.
  8. For EACH advertised option partition, require at least 100 legal controls.
  9. For that partition, require at least 100 illegal controls.
  10. For that partition, require at least 100 boundary and fault controls.
  11. For that partition, require at least 100 cross-clause controls.
  12. Enumerate all finite legal option values.
  13. For unbounded parameter ranges, prove a semantics-preserving partition.
  14. Test every boundary and representative of that partition.
  15. Without a partition proof, mark the range unsupported.
  16. For V, enumerate all supported combinations of VLEN, SEW, LMUL, masking, tail, segment and fault-only-first behavior.
  17. For H, enumerate privilege, translation-stage, trap and interrupt-delegation combinations.
  18. Use Sail and Spike as the reference pair where both implement the family.
  19. Otherwise, require Sail and the independent lineage in the explanatory context in D11.c8.
  20. Keep the child OPEN for unsupported reference options.

<a id="D10c1p6"></a>

#### D10.c1p6: Complete Zicfilp and Zicfiss family obligations, option partitions and cross-clause controls under the pinned ISA protocol
- Phases: Start work in P04. Accept this cell in P04.
- Must pass first: D09.c1, D11.c1, D27.c8, the explanatory context in D11.c8.
- Baseline: Use the baseline stated in the rule when a comparison applies.
- Summary: Test complete Zicfilp and Zicfiss family obligations, option partitions and cross-clause controls under the pinned ISA protocol. Require zero misses.
- Rule:
  1. Apply ISA24, the pinned ISA extension and cross-clause protocol, to family Zicfilp and Zicfiss.
  2. Create separate clause and tuple children for every instruction, option, state, fault and profile obligation.
  3. Require legal, illegal and omission controls.
  4. Maintain results through two specification or model upgrades.
  5. Use the pinned profile source to determine mandatory and optional status.
  6. Permit no implied extension.
  7. Require zero misses.
  8. For EACH advertised option partition, require at least 100 legal controls.
  9. For that partition, require at least 100 illegal controls.
  10. For that partition, require at least 100 boundary and fault controls.
  11. For that partition, require at least 100 cross-clause controls.
  12. Enumerate all finite legal option values.
  13. For unbounded parameter ranges, prove a semantics-preserving partition.
  14. Test every boundary and representative of that partition.
  15. Without a partition proof, mark the range unsupported.
  16. For V, enumerate all supported combinations of VLEN, SEW, LMUL, masking, tail, segment and fault-only-first behavior.
  17. For H, enumerate privilege, translation-stage, trap and interrupt-delegation combinations.
  18. Use Sail and Spike as the reference pair where both implement the family.
  19. Otherwise, require Sail and the independent lineage in the explanatory context in D11.c8.
  20. Keep the child OPEN for unsupported reference options.

<a id="D10c1p7"></a>

#### D10.c1p7: Complete state-enable and environment family obligations, option partitions and cross-clause controls under the pinned ISA protocol
- Phases: Start work in P04. Accept this cell in P04.
- Must pass first: D09.c1, D11.c1, D27.c8, the explanatory context in D11.c8.
- Baseline: Use the baseline stated in the rule when a comparison applies.
- Summary: Test complete state-enable and environment family obligations, option partitions and cross-clause controls under the pinned ISA protocol. Require zero misses.
- Rule:
  1. Apply ISA24, the pinned ISA extension and cross-clause protocol, to family state-enable and environment.
  2. Create separate clause and tuple children for every instruction, option, state, fault and profile obligation.
  3. Require legal, illegal and omission controls.
  4. Maintain results through two specification or model upgrades.
  5. Use the pinned profile source to determine mandatory and optional status.
  6. Permit no implied extension.
  7. Require zero misses.
  8. For EACH advertised option partition, require at least 100 legal controls.
  9. For that partition, require at least 100 illegal controls.
  10. For that partition, require at least 100 boundary and fault controls.
  11. For that partition, require at least 100 cross-clause controls.
  12. Enumerate all finite legal option values.
  13. For unbounded parameter ranges, prove a semantics-preserving partition.
  14. Test every boundary and representative of that partition.
  15. Without a partition proof, mark the range unsupported.
  16. For V, enumerate all supported combinations of VLEN, SEW, LMUL, masking, tail, segment and fault-only-first behavior.
  17. For H, enumerate privilege, translation-stage, trap and interrupt-delegation combinations.
  18. Use Sail and Spike as the reference pair where both implement the family.
  19. Otherwise, require Sail and the independent lineage in the explanatory context in D11.c8.
  20. Keep the child OPEN for unsupported reference options.

<a id="D10c1p8"></a>

#### D10.c1p8: Complete pointer-mask family obligations, option partitions and cross-clause controls under the pinned ISA protocol
- Phases: Start work in P04. Accept this cell in P04.
- Must pass first: D09.c1, D11.c1, D27.c8, the explanatory context in D11.c8.
- Baseline: Use the baseline stated in the rule when a comparison applies.
- Summary: Test complete pointer-mask family obligations, option partitions and cross-clause controls under the pinned ISA protocol. Require zero misses.
- Rule:
  1. Apply ISA24, the pinned ISA extension and cross-clause protocol, to family pointer-mask.
  2. Create separate clause and tuple children for every instruction, option, state, fault and profile obligation.
  3. Require legal, illegal and omission controls.
  4. Maintain results through two specification or model upgrades.
  5. Use the pinned profile source to determine mandatory and optional status.
  6. Permit no implied extension.
  7. Require zero misses.
  8. For EACH advertised option partition, require at least 100 legal controls.
  9. For that partition, require at least 100 illegal controls.
  10. For that partition, require at least 100 boundary and fault controls.
  11. For that partition, require at least 100 cross-clause controls.
  12. Enumerate all finite legal option values.
  13. For unbounded parameter ranges, prove a semantics-preserving partition.
  14. Test every boundary and representative of that partition.
  15. Without a partition proof, mark the range unsupported.
  16. For V, enumerate all supported combinations of VLEN, SEW, LMUL, masking, tail, segment and fault-only-first behavior.
  17. For H, enumerate privilege, translation-stage, trap and interrupt-delegation combinations.
  18. Use Sail and Spike as the reference pair where both implement the family.
  19. Otherwise, require Sail and the independent lineage in the explanatory context in D11.c8.
  20. Keep the child OPEN for unsupported reference options.

<a id="D10c1p9"></a>

#### D10.c1p9: Complete AIA IMSIC and APLIC family obligations, option partitions and cross-clause controls under the pinned ISA protocol
- Phases: Start work in P04. Accept this cell in P04.
- Must pass first: D09.c1, D11.c1, D27.c8, the explanatory context in D11.c8.
- Baseline: Use the baseline stated in the rule when a comparison applies.
- Summary: Test complete AIA IMSIC and APLIC family obligations, option partitions and cross-clause controls under the pinned ISA protocol. Require zero misses.
- Rule:
  1. Apply ISA24, the pinned ISA extension and cross-clause protocol, to family AIA IMSIC and APLIC.
  2. Create separate clause and tuple children for every instruction, option, state, fault and profile obligation.
  3. Require legal, illegal and omission controls.
  4. Maintain results through two specification or model upgrades.
  5. Use the pinned profile source to determine mandatory and optional status.
  6. Permit no implied extension.
  7. Require zero misses.
  8. For EACH advertised option partition, require at least 100 legal controls.
  9. For that partition, require at least 100 illegal controls.
  10. For that partition, require at least 100 boundary and fault controls.
  11. For that partition, require at least 100 cross-clause controls.
  12. Enumerate all finite legal option values.
  13. For unbounded parameter ranges, prove a semantics-preserving partition.
  14. Test every boundary and representative of that partition.
  15. Without a partition proof, mark the range unsupported.
  16. For V, enumerate all supported combinations of VLEN, SEW, LMUL, masking, tail, segment and fault-only-first behavior.
  17. For H, enumerate privilege, translation-stage, trap and interrupt-delegation combinations.
  18. Use Sail and Spike as the reference pair where both implement the family.
  19. Otherwise, require Sail and the independent lineage in the explanatory context in D11.c8.
  20. Keep the child OPEN for unsupported reference options.

<a id="D10c1p10"></a>

#### D10.c1p10: Complete RVA23, RVB23 and RVA23S64 family obligations, option partitions and cross-clause controls under the pinned ISA protocol
- Phases: Start work in P04. Accept this cell in P04.
- Must pass first: D09.c1, D11.c1, D27.c8, the explanatory context in D11.c8.
- Baseline: Use the baseline stated in the rule when a comparison applies.
- Summary: Test complete RVA23, RVB23 and RVA23S64 family obligations, option partitions and cross-clause controls under the pinned ISA protocol. Require zero misses.
- Rule:
  1. Apply ISA24, the pinned ISA extension and cross-clause protocol, to family RVA23, RVB23 and RVA23S64.
  2. Create separate clause and tuple children for every instruction, option, state, fault and profile obligation.
  3. Require legal, illegal and omission controls.
  4. Maintain results through two specification or model upgrades.
  5. Use the pinned profile source to determine mandatory and optional status.
  6. Permit no implied extension.
  7. Require zero misses.
  8. For EACH advertised option partition, require at least 100 legal controls.
  9. For that partition, require at least 100 illegal controls.
  10. For that partition, require at least 100 boundary and fault controls.
  11. For that partition, require at least 100 cross-clause controls.
  12. Enumerate all finite legal option values.
  13. For unbounded parameter ranges, prove a semantics-preserving partition.
  14. Test every boundary and representative of that partition.
  15. Without a partition proof, mark the range unsupported.
  16. For V, enumerate all supported combinations of VLEN, SEW, LMUL, masking, tail, segment and fault-only-first behavior.
  17. For H, enumerate privilege, translation-stage, trap and interrupt-delegation combinations.
  18. Use Sail and Spike as the reference pair where both implement the family.
  19. Otherwise, require Sail and the independent lineage in the explanatory context in D11.c8.
  20. Keep the child OPEN for unsupported reference options.

<a id="D10c1p11"></a>

#### D10.c1p11: Complete debug family obligations, option partitions and cross-clause controls under the pinned ISA protocol
- Phases: Start work in P04. Accept this cell in P04.
- Must pass first: D09.c1, D11.c1, D27.c8, the explanatory context in D11.c8.
- Baseline: Use the baseline stated in the rule when a comparison applies.
- Summary: Test complete debug family obligations, option partitions and cross-clause controls under the pinned ISA protocol. Require zero misses.
- Rule:
  1. Apply ISA24, the pinned ISA extension and cross-clause protocol, to family debug.
  2. Create separate clause and tuple children for every instruction, option, state, fault and profile obligation.
  3. Require legal, illegal and omission controls.
  4. Maintain results through two specification or model upgrades.
  5. Use the pinned profile source to determine mandatory and optional status.
  6. Permit no implied extension.
  7. Require zero misses.
  8. For EACH advertised option partition, require at least 100 legal controls.
  9. For that partition, require at least 100 illegal controls.
  10. For that partition, require at least 100 boundary and fault controls.
  11. For that partition, require at least 100 cross-clause controls.
  12. Enumerate all finite legal option values.
  13. For unbounded parameter ranges, prove a semantics-preserving partition.
  14. Test every boundary and representative of that partition.
  15. Without a partition proof, mark the range unsupported.
  16. For V, enumerate all supported combinations of VLEN, SEW, LMUL, masking, tail, segment and fault-only-first behavior.
  17. For H, enumerate privilege, translation-stage, trap and interrupt-delegation combinations.
  18. Use Sail and Spike as the reference pair where both implement the family.
  19. Otherwise, require Sail and the independent lineage in the explanatory context in D11.c8.
  20. Keep the child OPEN for unsupported reference options.

<a id="D10c1p12"></a>

#### D10.c1p12: Complete CLIC family obligations, option partitions and cross-clause controls under the pinned ISA protocol
- Phases: Start work in P04. Accept this cell in P04.
- Must pass first: D09.c1, D11.c1, D27.c8, the explanatory context in D11.c8.
- Baseline: Use the baseline stated in the rule when a comparison applies.
- Summary: Test complete CLIC family obligations, option partitions and cross-clause controls under the pinned ISA protocol. Require zero misses.
- Rule:
  1. Apply ISA24, the pinned ISA extension and cross-clause protocol, to family CLIC.
  2. Create separate clause and tuple children for every instruction, option, state, fault and profile obligation.
  3. Require legal, illegal and omission controls.
  4. Maintain results through two specification or model upgrades.
  5. Use the pinned profile source to determine mandatory and optional status.
  6. Permit no implied extension.
  7. Require zero misses.
  8. For EACH advertised option partition, require at least 100 legal controls.
  9. For that partition, require at least 100 illegal controls.
  10. For that partition, require at least 100 boundary and fault controls.
  11. For that partition, require at least 100 cross-clause controls.
  12. Enumerate all finite legal option values.
  13. For unbounded parameter ranges, prove a semantics-preserving partition.
  14. Test every boundary and representative of that partition.
  15. Without a partition proof, mark the range unsupported.
  16. For V, enumerate all supported combinations of VLEN, SEW, LMUL, masking, tail, segment and fault-only-first behavior.
  17. For H, enumerate privilege, translation-stage, trap and interrupt-delegation combinations.
  18. Use Sail and Spike as the reference pair where both implement the family.
  19. Otherwise, require Sail and the independent lineage in the explanatory context in D11.c8.
  20. Keep the child OPEN for unsupported reference options.

<a id="D10c1p13"></a>

#### D10.c1p13: Complete ACLIC-r20-1 family obligations, option partitions and cross-clause controls under the pinned ISA protocol
- Phases: Start work in P04. Accept this cell in P04.
- Must pass first: D09.c1, D11.c1, D27.c8, the explanatory context in D11.c8.
- Baseline: Use the baseline stated in the rule when a comparison applies.
- Summary: Test complete ACLIC-r20-1 family obligations, option partitions and cross-clause controls under the pinned ISA protocol. Require zero misses.
- Rule:
  1. Apply ISA24, the pinned ISA extension and cross-clause protocol, to family ACLIC-r20-1.
  2. Create separate clause and tuple children for every instruction, option, state, fault and profile obligation.
  3. Require legal, illegal and omission controls.
  4. Maintain results through two specification or model upgrades.
  5. Use the pinned profile source to determine mandatory and optional status.
  6. Permit no implied extension.
  7. Require zero misses.
  8. For EACH advertised option partition, require at least 100 legal controls.
  9. For that partition, require at least 100 illegal controls.
  10. For that partition, require at least 100 boundary and fault controls.
  11. For that partition, require at least 100 cross-clause controls.
  12. Enumerate all finite legal option values.
  13. For unbounded parameter ranges, prove a semantics-preserving partition.
  14. Test every boundary and representative of that partition.
  15. Without a partition proof, mark the range unsupported.
  16. For V, enumerate all supported combinations of VLEN, SEW, LMUL, masking, tail, segment and fault-only-first behavior.
  17. For H, enumerate privilege, translation-stage, trap and interrupt-delegation combinations.
  18. Use Sail and Spike as the reference pair where both implement the family.
  19. Otherwise, require Sail and the independent lineage in the explanatory context in D11.c8.
  20. Keep the child OPEN for unsupported reference options.

<a id="D10c1p14"></a>

#### D10.c1p14: Complete RAS-r20-1 family obligations, option partitions and cross-clause controls under the pinned ISA protocol
- Phases: Start work in P04. Accept this cell in P04.
- Must pass first: D09.c1, D11.c1, D27.c8, the explanatory context in D11.c8.
- Baseline: Use the baseline stated in the rule when a comparison applies.
- Summary: Test complete RAS-r20-1 family obligations, option partitions and cross-clause controls under the pinned ISA protocol. Require zero misses.
- Rule:
  1. Apply ISA24, the pinned ISA extension and cross-clause protocol, to family RAS-r20-1.
  2. Create separate clause and tuple children for every instruction, option, state, fault and profile obligation.
  3. Require legal, illegal and omission controls.
  4. Maintain results through two specification or model upgrades.
  5. Use the pinned profile source to determine mandatory and optional status.
  6. Permit no implied extension.
  7. Require zero misses.
  8. For EACH advertised option partition, require at least 100 legal controls.
  9. For that partition, require at least 100 illegal controls.
  10. For that partition, require at least 100 boundary and fault controls.
  11. For that partition, require at least 100 cross-clause controls.
  12. Enumerate all finite legal option values.
  13. For unbounded parameter ranges, prove a semantics-preserving partition.
  14. Test every boundary and representative of that partition.
  15. Without a partition proof, mark the range unsupported.
  16. For V, enumerate all supported combinations of VLEN, SEW, LMUL, masking, tail, segment and fault-only-first behavior.
  17. For H, enumerate privilege, translation-stage, trap and interrupt-delegation combinations.
  18. Use Sail and Spike as the reference pair where both implement the family.
  19. Otherwise, require Sail and the independent lineage in the explanatory context in D11.c8.
  20. Keep the child OPEN for unsupported reference options.

<a id="D10c1p15"></a>

#### D10.c1p15: Complete Zicbom, Zicboz and Zicbop CMO #137 family obligations, option partitions and cross-clause controls under the pinned ISA protocol
- Phases: Start work in P04. Accept this cell in P04.
- Must pass first: D09.c1, D11.c1, D27.c8, the explanatory context in D11.c8.
- Baseline: Use the baseline stated in the rule when a comparison applies.
- Summary: Test complete Zicbom, Zicboz and Zicbop CMO #137 family obligations, option partitions and cross-clause controls under the pinned ISA protocol. Require zero misses.
- Rule:
  1. Apply ISA24, the pinned ISA extension and cross-clause protocol, to family Zicbom, Zicboz and Zicbop CMO #137.
  2. Create separate clause and tuple children for every instruction, option, state, fault and profile obligation.
  3. Require legal, illegal and omission controls.
  4. Maintain results through two specification or model upgrades.
  5. Use the pinned profile source to determine mandatory and optional status.
  6. Permit no implied extension.
  7. Require zero misses.
  8. For EACH advertised option partition, require at least 100 legal controls.
  9. For that partition, require at least 100 illegal controls.
  10. For that partition, require at least 100 boundary and fault controls.
  11. For that partition, require at least 100 cross-clause controls.
  12. Enumerate all finite legal option values.
  13. For unbounded parameter ranges, prove a semantics-preserving partition.
  14. Test every boundary and representative of that partition.
  15. Without a partition proof, mark the range unsupported.
  16. For V, enumerate all supported combinations of VLEN, SEW, LMUL, masking, tail, segment and fault-only-first behavior.
  17. For H, enumerate privilege, translation-stage, trap and interrupt-delegation combinations.
  18. Use Sail and Spike as the reference pair where both implement the family.
  19. Otherwise, require Sail and the independent lineage in the explanatory context in D11.c8.
  20. Keep the child OPEN for unsupported reference options.

<a id="D10c1p16"></a>

#### D10.c1p16: Complete cross-clause tuples and higher-order hazard union family obligations, option partitions and cross-clause controls under the pinned ISA protocol
- Phases: Start work in P04. Accept this cell in P04.
- Must pass first: D09.c1, D11.c1, D27.c8, the explanatory context in D11.c8.
- Baseline: Use the baseline stated in the rule when a comparison applies.
- Summary: Test complete cross-clause tuples and higher-order hazard union family obligations, option partitions and cross-clause controls under the pinned ISA protocol. Require zero misses.
- Rule:
  1. Apply ISA24, the pinned ISA extension and cross-clause protocol, to family cross-clause tuples and higher-order hazard union.
  2. Create separate clause and tuple children for every instruction, option, state, fault and profile obligation.
  3. Require legal, illegal and omission controls.
  4. Maintain results through two specification or model upgrades.
  5. Use the pinned profile source to determine mandatory and optional status.
  6. Permit no implied extension.
  7. Require zero misses.
  8. For EACH advertised option partition, require at least 100 legal controls.
  9. For that partition, require at least 100 illegal controls.
  10. For that partition, require at least 100 boundary and fault controls.
  11. For that partition, require at least 100 cross-clause controls.
  12. Enumerate all finite legal option values.
  13. For unbounded parameter ranges, prove a semantics-preserving partition.
  14. Test every boundary and representative of that partition.
  15. Without a partition proof, mark the range unsupported.
  16. For V, enumerate all supported combinations of VLEN, SEW, LMUL, masking, tail, segment and fault-only-first behavior.
  17. For H, enumerate privilege, translation-stage, trap and interrupt-delegation combinations.
  18. Use Sail and Spike as the reference pair where both implement the family.
  19. Otherwise, require Sail and the independent lineage in the explanatory context in D11.c8.
  20. Keep the child OPEN for unsupported reference options.

<a id="D10c1p17"></a>

#### D10.c1p17: Complete scalar crypto Zk* and Zkt family obligations, option partitions and cross-clause controls under the pinned ISA protocol
- Phases: Start work in P04. Accept this cell in P04.
- Must pass first: D09.c1, D11.c1, D27.c8, the explanatory context in D11.c8.
- Baseline: Use the baseline stated in the rule when a comparison applies.
- Summary: Test complete scalar crypto Zk* and Zkt family obligations, option partitions and cross-clause controls under the pinned ISA protocol. Require zero misses.
- Rule:
  1. Apply ISA24, the pinned ISA extension and cross-clause protocol, to family scalar crypto Zk* and Zkt.
  2. Create separate clause and tuple children for every instruction, option, state, fault and profile obligation.
  3. Require legal, illegal and omission controls.
  4. Maintain results through two specification or model upgrades.
  5. Use the pinned profile source to determine mandatory and optional status.
  6. Permit no implied extension.
  7. Require zero misses.
  8. For EACH advertised option partition, require at least 100 legal controls.
  9. For that partition, require at least 100 illegal controls.
  10. For that partition, require at least 100 boundary and fault controls.
  11. For that partition, require at least 100 cross-clause controls.
  12. Enumerate all finite legal option values.
  13. For unbounded parameter ranges, prove a semantics-preserving partition.
  14. Test every boundary and representative of that partition.
  15. Without a partition proof, mark the range unsupported.
  16. For V, enumerate all supported combinations of VLEN, SEW, LMUL, masking, tail, segment and fault-only-first behavior.
  17. For H, enumerate privilege, translation-stage, trap and interrupt-delegation combinations.
  18. Use Sail and Spike as the reference pair where both implement the family.
  19. Otherwise, require Sail and the independent lineage in the explanatory context in D11.c8.
  20. Keep the child OPEN for unsupported reference options.
  21. Retain source locator SPARA25-02, the literal ISA-family obligation expansion.

<a id="D10c1p18"></a>

#### D10.c1p18: Complete bit-manipulation Zba, Zbb and Zbs and every extra pinned profile member family obligations, option partitions and cross-clause controls under the pinned ISA protocol
- Phases: Start work in P04. Accept this cell in P04.
- Must pass first: D09.c1, D11.c1, D27.c8, the explanatory context in D11.c8.
- Baseline: Use the baseline stated in the rule when a comparison applies.
- Summary: Test complete bit-manipulation Zba, Zbb and Zbs and every extra pinned profile member family obligations, option partitions and cross-clause controls under the pinned ISA protocol. Require zero misses.
- Rule:
  1. Apply ISA24, the pinned ISA extension and cross-clause protocol, to family bit-manipulation Zba, Zbb and Zbs and every extra pinned profile member.
  2. Create separate clause and tuple children for every instruction, option, state, fault and profile obligation.
  3. Require legal, illegal and omission controls.
  4. Maintain results through two specification or model upgrades.
  5. Use the pinned profile source to determine mandatory and optional status.
  6. Permit no implied extension.
  7. Require zero misses.
  8. For EACH advertised option partition, require at least 100 legal controls.
  9. For that partition, require at least 100 illegal controls.
  10. For that partition, require at least 100 boundary and fault controls.
  11. For that partition, require at least 100 cross-clause controls.
  12. Enumerate all finite legal option values.
  13. For unbounded parameter ranges, prove a semantics-preserving partition.
  14. Test every boundary and representative of that partition.
  15. Without a partition proof, mark the range unsupported.
  16. For V, enumerate all supported combinations of VLEN, SEW, LMUL, masking, tail, segment and fault-only-first behavior.
  17. For H, enumerate privilege, translation-stage, trap and interrupt-delegation combinations.
  18. Use Sail and Spike as the reference pair where both implement the family.
  19. Otherwise, require Sail and the independent lineage in the explanatory context in D11.c8.
  20. Keep the child OPEN for unsupported reference options.
  21. Retain source locator SPARA25-02, the literal ISA-family obligation expansion.

<a id="D10c1p19"></a>

#### D10.c1p19: Complete Zfa family obligations, option partitions and cross-clause controls under the pinned ISA protocol
- Phases: Start work in P04. Accept this cell in P04.
- Must pass first: D09.c1, D11.c1, D27.c8, the explanatory context in D11.c8.
- Baseline: Use the baseline stated in the rule when a comparison applies.
- Summary: Test complete Zfa family obligations, option partitions and cross-clause controls under the pinned ISA protocol. Require zero misses.
- Rule:
  1. Apply ISA24, the pinned ISA extension and cross-clause protocol, to family Zfa.
  2. Create separate clause and tuple children for every instruction, option, state, fault and profile obligation.
  3. Require legal, illegal and omission controls.
  4. Maintain results through two specification or model upgrades.
  5. Use the pinned profile source to determine mandatory and optional status.
  6. Permit no implied extension.
  7. Require zero misses.
  8. For EACH advertised option partition, require at least 100 legal controls.
  9. For that partition, require at least 100 illegal controls.
  10. For that partition, require at least 100 boundary and fault controls.
  11. For that partition, require at least 100 cross-clause controls.
  12. Enumerate all finite legal option values.
  13. For unbounded parameter ranges, prove a semantics-preserving partition.
  14. Test every boundary and representative of that partition.
  15. Without a partition proof, mark the range unsupported.
  16. For V, enumerate all supported combinations of VLEN, SEW, LMUL, masking, tail, segment and fault-only-first behavior.
  17. For H, enumerate privilege, translation-stage, trap and interrupt-delegation combinations.
  18. Use Sail and Spike as the reference pair where both implement the family.
  19. Otherwise, require Sail and the independent lineage in the explanatory context in D11.c8.
  20. Keep the child OPEN for unsupported reference options.
  21. Retain source locator SPARA25-02, the literal ISA-family obligation expansion.

<a id="D10c1p20"></a>

#### D10.c1p20: Complete Zfh and Zfhmin family obligations, option partitions and cross-clause controls under the pinned ISA protocol
- Phases: Start work in P04. Accept this cell in P04.
- Must pass first: D09.c1, D11.c1, D27.c8, the explanatory context in D11.c8.
- Baseline: Use the baseline stated in the rule when a comparison applies.
- Summary: Test complete Zfh and Zfhmin family obligations, option partitions and cross-clause controls under the pinned ISA protocol. Require zero misses.
- Rule:
  1. Apply ISA24, the pinned ISA extension and cross-clause protocol, to family Zfh and Zfhmin.
  2. Create separate clause and tuple children for every instruction, option, state, fault and profile obligation.
  3. Require legal, illegal and omission controls.
  4. Maintain results through two specification or model upgrades.
  5. Use the pinned profile source to determine mandatory and optional status.
  6. Permit no implied extension.
  7. Require zero misses.
  8. For EACH advertised option partition, require at least 100 legal controls.
  9. For that partition, require at least 100 illegal controls.
  10. For that partition, require at least 100 boundary and fault controls.
  11. For that partition, require at least 100 cross-clause controls.
  12. Enumerate all finite legal option values.
  13. For unbounded parameter ranges, prove a semantics-preserving partition.
  14. Test every boundary and representative of that partition.
  15. Without a partition proof, mark the range unsupported.
  16. For V, enumerate all supported combinations of VLEN, SEW, LMUL, masking, tail, segment and fault-only-first behavior.
  17. For H, enumerate privilege, translation-stage, trap and interrupt-delegation combinations.
  18. Use Sail and Spike as the reference pair where both implement the family.
  19. Otherwise, require Sail and the independent lineage in the explanatory context in D11.c8.
  20. Keep the child OPEN for unsupported reference options.
  21. Retain source locator SPARA25-02, the literal ISA-family obligation expansion.

<a id="D11c1"></a>

#### D11.c1: Check complete architectural state and asynchronous transitions
- Phases: Start work in P03. Accept this cell in P03.
- Must pass first: D09.c1; independently specified expected transitions under R04, the independence protocol; D27.c8.
- Baseline: Use the baseline stated in the rule when a comparison applies.
- Summary: Test the correctness of complete architectural state and asynchronous transitions. Require exactly zero false accepts.
- Rule:
  1. Start with scalar bootstrap.
  2. Check integer, floating-point, flags, CSR, privilege, fault, vector, guest and debug state.
  3. Run at least 100 directed cases per family.
  4. Activate one fault per field per slot.
  5. Require exactly zero false accepts.
  6. Expose the shared ancestry of Spike, Sail and transitions independently authored under R04, the independence protocol.
  7. Force 1,000 IRQ, asynchronous NMI and debug transitions with identical transition boundaries and partial vector effects.

<a id="D11c3"></a>

#### D11.c3: Resolve specification and model disputes
- Phases: Start work in P04. Accept this cell in P04.
- Must pass first: D11.c1; issue proposals can seek external interpretation later, D27.c8.
- Baseline: Use the baseline stated in the rule when a comparison applies.
- Summary: Test the resolution of specification and model disputes. Require 30 evidence-backed dispute closures within 30 calendar days each.
- Rule:
  1. The tool must quarantine disputed cells within one working day.
  2. Complete independent clause analysis within 10 working days.
  3. Issue an unresolved receipt at 30 days.
  4. Report the external specification response.
  5. Never assume an external specification response.
  6. Run 30 ambiguity and shared-model-error controls.
  7. Allow no pass by majority vote or timeout.
  8. Resume only with the exact version, interpretation and transition, plus an independent negative control.
  9. For at least 30 independently seeded disputes, require 30 evidence-backed closures within 30 calendar days each.
  10. Include three-reference disagreements between Sail, Spike and the independent reference.
  11. Require clause evidence, independent expected transitions and negative controls for each closure.
  12. External unresolved disputes stay quarantined and OPEN at 30 days.
  13. A timeout receipt cannot satisfy the closure count.
  14. Count only seeded tool-test disputes toward the 30 closures in 30 days.

<a id="D11c5"></a>

#### D11.c5: Check reference observation streams and custom plugins
- Phases: Start work in P04. Accept this cell in P04.
- Must pass first: D11.c1, D27.c8.
- Baseline: Use the baseline stated in the rule when a comparison applies.
- Summary: Test the correctness of reference observation streams and custom plugins. Require zero false architectural pass.
- Rule:
  1. For #189, version the compared fields, asynchronous boundaries and synchronization limits of the RVVI or equivalent observation stream.
  2. Run 100 round trips per state family.
  3. Run 30 omitted, reordered and wrong-version controls.
  4. Require exact field and transition identity.
  5. Require zero false architectural pass.
  6. For #143, custom reference plugins must reject unsupported or version-mismatched semantics.
  7. Require that format interchange is not independent checking.

<a id="D11c90"></a>

#### D11.c90: Check source-specific reference issues
- Phases: Start work in P04. Accept this cell in P04.
- Must pass first: D11.c1, D27.c2, D27.c8.
- Baseline: Use the baseline stated in the rule when a comparison applies.
- Summary: Test the correctness of source-specific reference issues. Require all 12 numbered rule items.
- Rule:
  1. Apply I90, the source-specific issue protocol, to these issue requirements: #8 per-core privilege and misalignment manifest changes reference behavior exactly.
  2. For #10, require that floating-point registers and fflags compare every supported rounding and fault effect.
  3. For #11, require that absent PMP and ecall mtval policy match declared core semantics.
  4. For #47, require that asynchronous IRQ boundaries compare exactly.
  5. For #50, regenerate saved traces from pinned source and independent reference with complete end status.
  6. For #86, require that comparison matrix states every checked and unchecked field.
  7. For #87, detect unread CSR divergence.
  8. For #93, require that fault records preserve address, size, partial writes and priority.
  9. For #100, quarantine disagreement until independent clause adjudication.
  10. For #110, detect first retirement divergence during live execution.
  11. For #136, require that debug entry and step and exit state matches independent transitions.
  12. Apply the complete I90 protocol.

<a id="D12c1"></a>

#### D12.c1: Check memory order and device behavior independently
- Phases: Start work in P04. Accept this cell in P04.
- Must pass first: D11.c1, D17.c1 independent event harness, then real integration, D27.c8.
- Baseline: Use the baseline stated in the rule when a comparison applies.
- Summary: Test independent memory-order and device checking. Run 1,000 litmus histories.
- Rule:
  1. Use an independent RVWMO graph checker on every advertised multi-hart trace.
  2. Run 1,000 litmus histories.
  3. Reject all forbidden controls.
  4. Run long applications at 1, 2, 4 and 8 harts.
  5. Require that pending-store membership alone cannot justify loads.
  6. Run 100 legal and error sequences per UART, PLIC, CLINT and DMA device.
  7. Run 10 wrong-state mutants per device.

<a id="D12c2"></a>

#### D12.c2: Check capability and custom state
- Phases: Start work in P05. Accept this cell in P05.
- Must pass first: D12.c1; capable existing targets, D27.c8.
- Baseline: Use the baseline stated in the rule when a comparison applies.
- Summary: Test the correctness of capability and custom state. Run 20 legal and illegal cases per family.
- Rule:
  1. Check capability and custom state tags, bounds, permissions and faults.
  2. Run 20 legal and illegal cases per family.
  3. Use two oracle lineages or independent expectations.
  4. Preserve unchecked device boundaries explicitly.

<a id="D12c90"></a>

#### D12.c90: Check source-specific concurrency issues
- Phases: Start work in P05. Accept this cell in P05.
- Must pass first: D12.c1, D27.c2, D27.c8.
- Baseline: Use the baseline stated in the rule when a comparison applies.
- Summary: Test the correctness of source-specific concurrency issues. Require all 6 numbered rule items.
- Rule:
  1. Apply I90, the source-specific issue protocol, to these issue requirements: #90 independent per-hart order and synchronization survive backpressure.
  2. For #108, require that every coherence transition matches independent protocol model.
  3. For #122, require that custom instruction effects and unsupported semantics are explicit.
  4. For #169, require that generated software hooks preserve ABI and encoding and reference transitions.
  5. For #196, require that equal-work custom-extension experiments retain rejected results and uncertainty.
  6. Apply the complete I90 protocol.

<a id="D14c1"></a>

#### D14.c1: Build and close the independent coverage inventory
- Phases: Start work in P04. Accept this cell in P04.
- Must pass first: D09.c1 needs, D17.c1 events, D15.c1 proofs, D27.c8, D01.c7 as explanatory context only.
- Baseline: Use the baseline stated in the rule when a comparison applies.
- Summary: Test the coverage inventory, required closure and description-driven inventory changes. Require at least 5 occupancy, event and recovery groups per unit. Include empty, one entry, one entry below full, full, full with flush, full with exception and cross-unit cases.
- Rule:
  1. Create an independent inventory of entries by ports by states by events for frontend, predictor, rename, ROB, issue, LSU, cache, MSHR, TLB, PTW and FPU.
  2. Require at least 5 occupancy, event and recovery groups per unit.
  3. Include empty, one entry, one entry below full, full, full with flush, full with exception and cross-unit cases.
  4. Hit at least 95% bins not proved unreachable.
  5. Hit each required hole or prove it unreachable with a sound proof.
  6. Keep unknowns in the denominator.
  7. Formal replay must close at least 50% initial reachable holes on two units.
  8. The description-to-coverage-plan child must use the machine schema described by D01.c7 as explanatory context only.
  9. Derive a bin and requirement inventory with source provenance for every queue, port, arbitration, replay and topology field.
  10. Independently derive expected bins before generation.
  11. Test at least 20 add, remove and resize queue and port mutations per structure type.
  12. Require exactly the expected inventory changes.
  13. Require zero stale or orphan bins.
  14. Require zero omitted mandatory bins.
  15. Replay three unrelated descriptions and a held-out schema upgrade.

<a id="D14c2"></a>

#### D14.c2: Compare stimulus generation methods
- Phases: Start work in P05. Accept this cell in P05.
- Must pass first: D14.c1; independent generation baselines, D27.c8.
- Baseline: Equal-effort riscv-dv, TestRIG, DifuzzRTL-style, Cascade-style, hardware-state, model-driven and agent-directed recipes.
- Summary: Test the comparison of stimulus generation methods. Run three pilot campaigns per unit, then powered fresh campaigns.
- Rule:
  1. Use legal architectural and interface sequences to target hardware states.
  2. Label intrusive register writes separately as checker controls.
  3. Require equal-effort riscv-dv, TestRIG, DifuzzRTL-style toggle and FSM feedback, Cascade-style dependency synthesis, hardware-state, model-driven and agent and ML and LLM-directed recipes with held-out goals, frozen weights and prompts and full training ancestry.
  4. Give generated proposals credit only after independent replay.
  5. Run three pilot campaigns per unit, then powered fresh campaigns.
  6. At least 20% new mandatory-bin yield gain supports Alpha experimental generation only.
  7. It cannot close Beta coverage closure or Qualified generation.
  8. The final statistical comparison under section 3.1 must use total time and effort to identical mandatory closure AND retained real-defect sensitivity.
  9. Require that yield cannot replace it.
  10. Retain all illegal and failed generation costs.

<a id="D14c4"></a>

#### D14.c4: Measure defect sensitivity on the sealed corpus
- Phases: Start work in P05. Accept this cell in P05.
- Must pass first: D14.c1, D28.c3; natural and commissioned and seeded provenance separate, D20.c2a, D27.c8.
- Baseline: Use the baseline stated in the rule when a comparison applies.
- Summary: Test measurement of defect sensitivity on the sealed corpus. Require zero missed mandatory faults.
- Rule:
  1. Use a later sealed corpus with at least 100 historical root causes across at least 10 complex unit classes.
  2. Include at least 10 root causes per class.
  3. Include at least 20 simultaneous faults and long races.
  4. Require zero missed mandatory faults.
  5. Require an adjusted sensitivity lower bound at least 0.95.
  6. Expand for power.
  7. Audit omitted requirements and severe escapes through three releases.
  8. Use D20.c2a only for the sealed enumeration method.
  9. Check natural-defect execution in this cell itself, with census and substitute closure under 3.4.
  10. It never waives mandatory coverage closure or proof.

<a id="D14c90"></a>

#### D14.c90: Check source-specific stimulus and coverage issues
- Phases: Start work in P05. Accept this cell in P05.
- Must pass first: D14.c1, D27.c2, D27.c8.
- Baseline: Random generation, including the named boundary-aware random distribution for #349.
- Summary: Test the correctness of source-specific stimulus and coverage issues. Require zero false credit.
- Rule:
  1. Apply I90, the source-specific issue protocol, to these issue requirements: #29 generated tests cover independent Sail clause inventory and detect wrong-semantic mutants.
  2. For #30, require that closure suggestions activate independently confirmed missing bins.
  3. For #33, require that random streams preserve legal constraints and independent cosim outcomes.
  4. For #42, require that FSM reachability and Scala source bins match independent maps.
  5. For #62, require that COI, solver proof cores and assertion activation remain distinct and independently checked under the independence protocol R04.
  6. For #88, require that RTL event bin values and time match probes.
  7. For #105, require that sequence and hazard bins match independent event automata.
  8. For #115, require that temporal overlaps and reset aborts preserve exact hits.
  9. For #150, require that portable scenarios enforce actual resource limits and refusals.
  10. For #152, require that reduction preserves real concurrent schedules, device effects and independently replayed failure, with 1-minimality under registered operators.
  11. For #155, require that custom-extension plans map all declared clauses.
  12. For #167, require that block reuse invalidates stale assumptions.
  13. For #180, require that UCIS merge and round-trip preserves bin identity, counts and exclusion proofs.
  14. For #353, require that Project-owned optional RTL event goals bind sampling edge, hart, ordinal and physical identity.
  15. Require that retire-only pairs cannot claim pipeline hazards.
  16. For at least 50 independent goal and hit and no-hit controls per event family require exact credit and complete lockstep.
  17. Refuse missing, ambiguous or stale bindings.
  18. Fresh paired campaigns must compare all-cost closure versus random, without omitted goals or hidden intrusive writes.
  19. For #352, require that RAW and WAW and WAR and branch and memory sequence holes become bounded action graphs with resources, preconditions and pinned solver and seed and ELF and replay.
  20. Complete lockstep and an independent retirement observer must verify every credited hit.
  21. Run 20 controls each for dependency distance, trap, order gap, alias, cancel and unsupported goal.
  22. Require zero false credit.
  23. Keep full denominator.
  24. Require that bounded UNSAT cannot prove unreachable.
  25. The paired random comparison must count every failed attempt CPU cost.
  26. For #349, require that Pinned Z3 integer backend covers all 170 bins per XLEN with UNSAT and timeout and unsupported and failed counts.
  27. Treat 5 paired seeds on VexRiscv and existing small OoO as pilot only.
  28. Retain all controller and descendant CPU time, cold build and saturation against the named boundary-aware random distribution.
  29. Credit payload-only complete lockstep C1.
  30. Run 20 bad identity, prefix and mutation controls.
  31. Require zero credited hits.
  32. Require that final closure uses the powered parent comparison.
  33. Apply the complete I90 protocol.
  34. Import owner-selected issue #376 as an I90 child for native pinned RISCV-DV pygen, project-owned ISA and memory configuration, GCC build, C1 and C2 execution, Spike lockstep, replayable random regression and reduction.
  35. Require one rvw command and one MCP tool on VexRiscv and BOOM.
  36. Require identical program bytes for the same seed and generator pin.
  37. Reject seeded core bugs and corrupted traces.
  38. Keep generator and build failures separate from core verdicts.
  39. Retain issue #33 and #48 source ancestry and issue #349 coverage duties.

<a id="D15c2a"></a>

#### D15.c2a: Check complete SVA formal lowering
- Phases: Start work in P03. Accept this cell in P03.
- Must pass first: D15.c1, D31.c1 expectations, D27.c8.
- Baseline: Use the baseline stated in the rule when a comparison applies.
- Summary: Test the correctness of complete SVA formal lowering. Implement complete IEEE 1800-2023 SVA formal lowering for sequences, local variables, repetitions, multiclock, sampled values, disable, strong and weak liveness and fairness.
- Rule:
  1. Implement complete IEEE 1800-2023 SVA formal lowering for sequences, local variables, repetitions, multiclock, sampled values, disable, strong and weak liveness and fairness.
  2. Independently freeze the clause inventory.
  3. Run at least 50 positive and negative cases per family.
  4. Require finite simulation witnesses distinct from infinite-trace semantics.

<a id="D15c2p1"></a>

#### D15.c2p1: Prove guarded connectivity
- Phases: Start work in P04. Accept this cell in P04.
- Must pass first: D15.c2a, D27.c8.
- Baseline: Use the baseline stated in the rule when a comparison applies.
- Summary: Test proof of guarded connectivity. Apply FP, the formal-application proof protocol in section 3.5.
- Rule:
  1. Include mux priority, byte masks, reset and forbidden paths in guarded source-to-sink connectivity relations.
  2. Prove each required path under its guard.
  3. Prove every forbidden disconnection.
  4. Inject swapped, missing, inverted and spurious connections.
  5. Apply FP, the formal-application proof protocol in section 3.5.
  6. Keep unknown results open.

<a id="D15c2p2"></a>

#### D15.c2p2: Prove register semantics
- Phases: Start work in P04. Accept this cell in P04.
- Must pass first: D15.c2a, D27.c8.
- Baseline: Use the baseline stated in the rule when a comparison applies.
- Summary: Test proof of register semantics. Apply FP, the formal-application proof protocol in section 3.5.
- Rule:
  1. Prove CSR reset, access privilege, WARL, WPRI, W1C, read-clear, byte enables, aliases and concurrent hardware and software updates.
  2. Use independent register semantics.
  3. Include bus retries, reset during a transaction and device side-effect ordering.
  4. Apply FP, the formal-application proof protocol in section 3.5.
  5. Keep unknown results open.

<a id="D15c2p3"></a>

#### D15.c2p3: Prove four-state propagation semantics
- Phases: Start work in P04. Accept this cell in P04.
- Must pass first: D15.c2a, D27.c8.
- Baseline: Use the baseline stated in the rule when a comparison applies.
- Summary: Test proof of four-state propagation semantics. Model 0, 1, X, Z and driver resolution with unknown-origin tags.
- Rule:
  1. Model 0, 1, X, Z and driver resolution with unknown-origin tags.
  2. Compare four-state simulation, symbolic two-rail known and value encoding, and concrete completions.
  3. Prove where optimism can hide divergence.
  4. Distinguish pessimistic false X.
  5. Include case, casex, if, when, reset, memory and reconvergence.
  6. Apply FP, the formal-application proof protocol in section 3.5.
  7. Keep unknown results open.

<a id="D15c2p4"></a>

#### D15.c2p4: Prove declared equivalence and refinement relations
- Phases: Start work in P04. Accept this cell in P04.
- Must pass first: D15.c2a, D27.c8.
- Baseline: Use the baseline stated in the rule when a comparison applies.
- Summary: Test proof of declared equivalence and refinement relations. Apply FP, the formal-application proof protocol in section 3.5.
- Rule:
  1. Prove the initialized state relation.
  2. Prove combinational equivalence or sequential refinement, as declared.
  3. Include retiming, changed encoding, clock enable and symbolic arbitrary-address memory.
  4. Wrong reset, alias and latency relations must fail.
  5. Bounded agreement must never close unbounded equivalence.
  6. Apply FP, the formal-application proof protocol in section 3.5.
  7. Keep unknown results open.

<a id="D15c2p5"></a>

#### D15.c2p5: Prove liveness under explicit fairness
- Phases: Start work in P04. Accept this cell in P04.
- Must pass first: D15.c2a, D27.c8.
- Baseline: Use the baseline stated in the rule when a comparison applies.
- Summary: Test proof of liveness under explicit fairness. Apply FP, the formal-application proof protocol in section 3.5.
- Rule:
  1. Prove eventual grant, retirement and response.
  2. Use explicit weak and strong fairness, ranking or justice certificates.
  3. Check fairness vacuity with independent legal infinite traces and starvation cycles.
  4. Require that assumption strengthening cannot erase a real livelock.
  5. Apply FP, the formal-application proof protocol in section 3.5.
  6. Keep unknown results open.

<a id="D15c2p6"></a>

#### D15.c2p6: Prove confidentiality and integrity separately
- Phases: Start work in P04. Accept this cell in P04.
- Must pass first: D15.c2a, D27.c8.
- Baseline: Use the baseline stated in the rule when a comparison applies.
- Summary: Test proof of confidentiality and integrity separately. Apply FP, the formal-application proof protocol in section 3.5.
- Rule:
  1. Self-compose states with equal public state and different secret state.
  2. Include complete observations and declassification.
  3. Prove the confidentiality relation.
  4. Prove protected-state integrity separately.
  5. Include violating witnesses, reset-retained state and unauthorized transitions.
  6. Require that taint reachability alone cannot close either proof.
  7. Apply FP, the formal-application proof protocol in section 3.5.
  8. Keep unknown results open.

<a id="D15c2p7"></a>

#### D15.c2p7: Check proof coverage and proof cores
- Phases: Start work in P04. Accept this cell in P04.
- Must pass first: D15.c2a, D27.c8.
- Baseline: Use the baseline stated in the rule when a comparison applies.
- Summary: Test the correctness of proof coverage and proof cores. Apply FP, the formal-application proof protocol in section 3.5.
- Rule:
  1. Report structural COI separately.
  2. Report the activated assertion fraction separately.
  3. Report the solver sufficient proof core separately.
  4. Report mutation-detected coverage separately.
  5. Prove the result again with only each claimed core.
  6. Expose nonminimality.
  7. Use independently known expected effects for unused logic, vacuous assertions and deleted assumptions.
  8. Coverage percentages must never stand for correctness.
  9. Apply FP, the formal-application proof protocol in section 3.5.
  10. Keep unknown results open.

<a id="D15c2p8"></a>

#### D15.c2p8: Check mutation operators and exact accounting
- Phases: Start work in P04. Accept this cell in P04.
- Must pass first: D15.c2a, D27.c8.
- Baseline: Use the baseline stated in the rule when a comparison applies.
- Summary: Check mutation operators and exact accounting. Activate each mutant that is not equivalent. Prove equivalence for exclusions. Keep undecided equivalents UNKNOWN and keep unknown results open.
- Rule:
  1. Freeze operators for compare and branch inversion, constant, width and priority changes, reset, queue, address alias and dropped ordering and handshake.
  2. Independently activate each non-equivalent mutant.
  3. Prove equivalence for exclusions.
  4. Keep undecided equivalents UNKNOWN in the denominator.
  5. Require exact accounting of killed, escaped, equivalent and unknown mutants.
  6. Replay the original design.
  7. Apply FP, the formal-application proof protocol in section 3.5.
  8. Keep unknown results open.

<a id="D15c2p9"></a>

#### D15.c2p9: Prove coverage-bin unreachability
- Phases: Start work in P04. Accept this cell in P04.
- Must pass first: D15.c2a, D27.c8.
- Baseline: Use the baseline stated in the rule when a comparison applies.
- Summary: Test proof of coverage-bin unreachability. Apply FP, the formal-application proof protocol in section 3.5.
- Rule:
  1. Prove the bin predicate unreachable from reset under the declared environment by induction or a checked invariant.
  2. Export the exclusion with proof, predicate and assumption hashes.
  3. Changes must invalidate the exclusion.
  4. Refuse exclusion for reachable rare witnesses and overconstraint mutants.
  5. Only this global receipt can remove a required coverage bin.
  6. Apply FP, the formal-application proof protocol in section 3.5.
  7. Keep unknown results open.

<a id="D15c3"></a>

#### D15.c3: Check arithmetic proofs and formal capacity gains
- Phases: Start work in P04. Accept this cell in P04.
- Must pass first: D15.c1, D15.c2a; kernels then slice then blocks then class composition then whole refinement, D27.c8, D16.c1 as explanatory context only.
- Baseline: Checked SoftFloat and Sail; sealed predecessor runs; final JasperGold and VC Formal comparisons.
- Summary: Test the correctness of arithmetic proofs and formal capacity gains. Require 30 SEC structural refactors including retime, encoding and reset and memory partitions.
- Rule:
  1. Check FADD, FMUL, FMA, FDIV, FSQRT and conversions against checked SoftFloat and Sail for all rounding, NaN and flag cases.
  2. Activate 10 faults per operation.
  3. Require 30 SEC structural refactors including retime, encoding and reset and memory partitions.
  4. Prove every advertised SEC relation.
  5. Include alias and distinct cases in symbolic arbitrary-address memory.
  6. Require curves 32, 64, 128, 256 entries then actual-large and wide, the split capacity endpoints below.
  7. Require one natural independently maintained wide target for capacity curves, even below the geometry described by D16.c1 as explanatory context only.
  8. Seal at least 30 predecessor-unsolved obligations per size and application class on disjoint baseline runs.
  9. If the predecessor solves all, extend the fixed size ladder before candidate reveal.
  10. A missing predecessor-unsolved frame is OPEN, never waived.
  11. Require capacity endpoints: on the sealed predecessor-unsolved frame require at least 30% and at least 10 independently checked conclusive obligations per size and application class under equal budgets.
  12. Separately require solved-count gain at least 1.5 times on a frozen mixed frame with predecessor solved count at least 20 per size and application class.
  13. Reject zero-denominator ratios.
  14. Preserve failed sizes, equal task and core-hour limits, certificate validity and both final JasperGold and VC Formal comparisons.

<a id="D15c4"></a>

#### D15.c4: Compare formal applications under equal budgets
- Phases: Start work in P05. Accept this cell in P05.
- Must pass first: D15.c2a, D15.c3; evaluate each D15.c2p1 through D15.c2p10 independently under the independence protocol R04, D27.c8.
- Baseline: JasperGold and VC Formal.
- Summary: Test the comparison of formal applications under equal budgets. Require at least 300 independent obligations across rename and ROB and LSQ and issue and arithmetic and memory and progress and every application, reduced and actual-large and wide.
- Rule:
  1. Require at least 300 independent obligations across rename and ROB and LSQ and issue and arithmetic and memory and progress and every application, reduced and actual-large and wide.
  2. Require equal budgets 1, 8, 24 h and 16, 64, 256 GiB.
  3. Allow no unexplained conclusive disagreements or missing mandatory properties.
  4. Use the statistical comparison in section 3.1 for solved fraction, checked-result time, lemma and debug and construction effort versus JasperGold AND VC Formal.
  5. Use the same assumptions, hard positives and counterexamples.
  6. Record certificate coverage, unknowns, proof depth for identical bounded questions and maintenance over three redesigns.
  7. Use this comparison setup to evaluate application instances.
  8. The final application comparisons are later receipts, so no P04 application consumes a P05 receipt.

<a id="D15c2p10"></a>

#### D15.c2p10: Prove automatic structural formal checks
- Phases: Start work in P04. Accept this cell in P04.
- Must pass first: D15.c2a, D27.c8.
- Baseline: Use the baseline stated in the rule when a comparison applies.
- Summary: Test proof of automatic structural formal checks. Require zero unsound verdicts.
- Rule:
  1. Derive automatic structural formal properties and nonvacuity covers from parsed structure without user properties.
  2. Cover FSM reachability, deadlock and livelock.
  3. Cover dead code, case completeness and X-assignment reachability.
  4. Cover arithmetic signed and unsigned overflow and out-of-range array indexing.
  5. Use independent intent to distinguish legal wrap and unreachable code from defects.
  6. Require that unknown intent stays unknown.
  7. For each family, run at least 50 valid controls independently specified under R04, the independence protocol.
  8. Run at least 50 violating controls per family.
  9. Require zero unsound verdicts.
  10. Prove all required positives unbounded or with checked finite completeness.
  11. Require capacity lower conclusive fraction at least .90 within 8 h and 64 GiB.
  12. Export source-to-property and assumption maps.
  13. Reject 20 overconstraint and omitted-logic mutants.

<a id="D15c11"></a>

#### D15.c11: Qualify the open formal-engine design and certificate checking
- Phases: Start work in P05. Accept this cell in P05.
- Must pass first: D15.c1, D15.c3, D27.c8.
- Baseline: Sealed predecessor runs and final JasperGold and VC Formal comparisons.
- Summary: Test the qualification of the open formal-engine design and certificate checking. Require zero unsound verdicts.
- Rule:
  1. For the open formal-engine architecture F25 decision, build typed transition IR, array and word abstraction, IC3 and PDR plus CHC and Spacer and lemma transport.
  2. Use 16-, 32- and 64-entry queue and memory slices.
  3. Run at least 50 positive controls per application.
  4. Run 50 violating controls per application.
  5. Discharge every positive.
  6. Require zero unsound verdicts.
  7. Replay certificates and distinct encodings.
  8. Prototype the split capacity endpoints below under fixed 8 h and 64 GiB.
  9. Log first unsolved sizes.
  10. Apply F25 design and redirect criteria.
  11. Require that final JasperGold AND VC Formal compares stay required.
  12. On the sealed predecessor-unsolved frame, require at least 30% independently checked conclusive obligations per size and application class under equal budgets.
  13. Also require at least 10 such obligations per size and application class.
  14. Separately require solved-count gain at least 1.5 times on a frozen mixed frame with predecessor solved count at least 20 per size and application class.
  15. Reject zero-denominator ratios.
  16. Preserve failed sizes, equal task and core-hour limits, certificate validity and both final JasperGold and VC Formal comparisons.
  17. For the IC3 and PDR certificate-format children from ABC, rIC3 and avy, export AIGER transition systems, invariant AIGs and LRAT proofs for initiation, consecution and safety.
  18. For Pono and Yosys and SBY k-induction, export base-case and induction-step SMT-LIB 2 formulas, typed invariant terms and Alethe proof objects.
  19. For CHC and Spacer, export SMT-LIB 2 Horn clauses and a predicate interpretation with Alethe proofs for every clause implication.
  20. For EBMC, export bit-blasted obligations with LRAT proofs.
  21. Implement separate small LRAT and Alethe checkers with independently authored parsers and term evaluators, distinct from producer engines.
  22. Validate lowering against an independent transition evaluator.
  23. Unsupported certificates remain inconclusive.
  24. For EACH engine and format require at least 50 valid proof controls and 50 mutations covering dropped premises, changed transitions, wrong width, missing base case and forged invariants.
  25. Require zero wrong accepted proofs.
  26. A solver answer or a second solver vote is not a certificate.
  27. When a required proof rule cannot be certified, lower the same obligation through a separately checked bit-blasted transition encoding with LRAT proofs.
  28. Prove the encoding relation with an independent transition evaluator and finite semantic controls before use.
  29. Require at least 50 positive and 50 corrupted-certificate controls per fallback rule.
  30. Keep the original application, capacity, budget and both vendor gates.
  31. If the fallback cannot certify the obligation, keep application parity OPEN.

<a id="D16c2"></a>

#### D16.c2: Select and seal the wide refinement target
- Phases: Start work in P03. Accept this cell in P03.
- Must pass first: D27.c1, D16.c1 method prototypes; third-party RTL preferred, D27.c8. D16.c4 as explanatory context only; it supplies no acceptance evidence.
- Baseline: Use the baseline stated in the rule when a comparison applies.
- Summary: Test the census and independent selection of a complete wide refinement target. Require at least 6 dispatch slots.
- Rule:
  1. Require an independent candidate census of XiangShan Kunminghu and Nanhu, SonicBOOM and BOOM variants and other wide RTL.
  2. Pin elaboration, ISA and integrated state.
  3. Require at least 6 dispatch slots, 6 retirement slots and 400 ROB entries for candidate qualification.
  4. Select largest integrated state inventory, then ROB, then reproducible build.
  5. If no candidate qualifies, independently seal a tool-owned artifact before generator and proof work.
  6. Require at least 6 dispatch slots.
  7. Require at least 6 retirement slots.
  8. Require at least 512 ROB entries.
  9. Include rename, free-list and PRF.
  10. Include shared issue and ROB.
  11. Include speculative loads, store sets and selective replay.
  12. Include nonblocking cache and MSHR.
  13. Include translation and coherence.
  14. Include precise recovery, CSR, IRQ and fair progress.
  15. Fix the structure from externally sourced demand, not solver success.
  16. Require an independent checker audit of hard-feature activation.
  17. Allow no proof-driven simplification.
  18. Retain failed originals.
  19. The full 3.4 protocol is mandatory: independent generator implementation, registered parameter distribution and a checker implementation with separate ancestry.
  20. Label the claim generated-wide full refinement.
  21. It does not close natural-lineage transfer in D16.c4.

<a id="D16c3"></a>

#### D16.c3: Prove complete unbounded implementation refinement
- Phases: Start work in P05. Accept this cell in P05.
- Must pass first: D16.c1, D16.c2, D15.c2, D15.c3, D16.c7, D27.c8.
- Baseline: Use the baseline stated in the rule when a comparison applies.
- Summary: Test proof of complete unbounded implementation refinement. Require all numbered rule items.
- Rule:
  1. Accept refinement only with a positive unbounded proof and the refinement method receipt.
  2. Require that exact proof validity is the metric.
  3. Prove positive unbounded complete implementation-to-specification refinement, including all implemented architectural state and instructions, multi-retirement serialization and stuttering, partial effects, reset, translation, exceptions and interrupts, memory visibility, speculation and progress under discharged fairness.
  4. Allow no killed instruction or speculative device effect to commit.
  5. Include vector and hypervisor and custom state when present.
  6. Check all composition and memory contracts independently.
  7. Publish residual solver trust.
  8. Allow no reduced, class or bounded substitute.
  9. Require the whole-core refinement method decision receipt before closing this result.
  10. Retain every positive proof and comparison gate.

<a id="D16c7"></a>

#### D16.c7: Qualify the refinement design
- Phases: Start work in P04. Accept this cell in P04.
- Must pass first: D16.c1, D16.c2, D27.c8.
- Baseline: Use the baseline stated in the rule when a comparison applies.
- Summary: Test the qualification of the refinement design. Require at least 50 valid and 50 bad controls per boundary.
- Rule:
  1. For the whole-core refinement design R25D decision, prototype commit-indexed refinement maps, symbolic arbitrary-address memory and noncircular assume-guarantee contracts on actual 16-entry slice, then 32, 64 entries.
  2. Prove reset and initiation and consecution, multi-retire serialization, killed-effect exclusion and progress.
  3. Require at least 50 valid and 50 bad controls per boundary.
  4. Require zero false proofs.
  5. Log full duty discharge and first unsolved size.
  6. Apply R25D design and kill and redirect criteria.
  7. Do not replace whole-core proof with bounded or class evidence.

<a id="D17c1"></a>

#### D17.c1: Check microarchitectural events and activated faults
- Phases: Start work in P03. Accept this cell in P03.
- Must pass first: D28.c1; real target integration follows D09.c1, D27.c8.
- Baseline: Use the baseline stated in the rule when a comparison applies.
- Summary: Test the correctness of microarchitectural events and activated faults. Require at least 200 independently activated faults across eight families (store sets, replay, ROB, forwarding, TLB and PTW, load violation, memory prediction, coherence), at least 25 per family.
- Rule:
  1. Bootstrap an independent reset, IRQ and ordering harness.
  2. Then check legal observed age, conservation, flush, replay, forwarding, killed-store, TLB, PMA and device events.
  3. Use inventory-derived scenarios.
  4. Run at least 100 scenarios with 100 seeds each.
  5. Run 1,000 nightly backpressure and probe seeds per configuration.
  6. Require at least 200 independently activated faults across eight families (store sets, replay, ROB, forwarding, TLB and PTW, load violation, memory prediction, coherence), at least 25 per family.
  7. Require zero mandatory misses.
  8. Require a sensitivity lower bound at least 0.95 per family.
  9. Expand for power.

<a id="D17c2"></a>

#### D17.c2: Prove RVWMO and generated-litmus coverage
- Phases: Start work in P05. Accept this cell in P05.
- Must pass first: D17.c1, D15.c2; D12.c1 independent dynamic oracle, D27.c8, D17.c14.
- Baseline: Qualified JasperGold-based ordering, coherence and ownership flows under RP03.
- Summary: Test proof of RVWMO and generated-litmus coverage. Require at least 200 herd7 litmus by 1,000 schedules plus 30 ordering-map and replay mutants and each dropped-axiom control.
- Rule:
  1. For each advertised core and configuration, provide a PipeCheck/RTLCheck-class RTL-to-microarchitectural-happens-before abstraction.
  2. Prove RVWMO inductively for all admitted programs.
  3. Preserve read-from, coherence, dependency and global order, speculation and partial operations.
  4. Prove implementation in-flight bound, not program-length bound.
  5. Require at least 200 herd7 litmus by 1,000 schedules plus 30 ordering-map and replay mutants and each dropped-axiom control.
  6. Require that dynamic D12.c1 checking cannot replace proof.
  7. On an unknown result, remove only that cell's "RVWMO-verified" label.
  8. Allow no effect on other cells' proofs.
  9. Apply RP03, the proof construction and two-revision maintenance comparison protocol, to every proof and control in this row.
  10. Include explicit axes for RVV segment accesses, fault-only-first, misaligned partial accesses and device and I/O ordering.
  11. Require independent permitted and forbidden traces and dropped-edge controls for each.
  12. For the generated-litmus child, use diy-style enumeration from the pinned RVWMO axioms.
  13. Seal a shape inventory for 2, 3, 4 harts, 1, 2, 3 addresses and 2, 3, 4 events per hart, with load and store and fence and AMO and each admitted dependency edge.
  14. Enumerate all canonical graphs modulo proved thread and address renaming, or prove that a reduction covers every omitted graph.
  15. Each axiom edge has positive and dropped-edge controls.
  16. Require 100% shape and axiom-edge coverage and exact permitted and forbidden agreement with independent herd7 and proof checks.
  17. Require that larger admitted shapes require a new inventory and proof.
  18. The at least 200 litmus floor remains.

<a id="D17c3"></a>

#### D17.c3: Prove directory coherence and parameterized scale
- Phases: Start work in P05. Accept this cell in P05.
- Must pass first: D17.c1, D15.c2, D12.c1, D17.c10, D27.c8, D37.c1 as explanatory context only.
- Baseline: Qualified JasperGold-based ordering, coherence and ownership flows under RP03.
- Summary: Test proof of directory coherence and parameterized scale. Require at least 8 requesters plus coherent DMA and IOMMU.
- Rule:
  1. Integrate real 2-, 4- and 8-hart caches.
  2. Then integrate a multilevel directory with private L1, banked L2 and shared LLC.
  3. Include inclusive and noninclusive configurations.
  4. Require at least 8 requesters plus coherent DMA and IOMMU.
  5. Pin qualified OpenPiton P-Mesh or independent D37.c1 as explanatory context only CHI-class endpoint system.
  6. Prove SWMR and data and deadlock and progress with sound scaling contracts, preserving transients and evictions and retries and reset and resource exhaustion.
  7. Use the four-cache and three-address fixture as bootstrap only.
  8. Test unseen topology and resource change without generic monitor edits.
  9. Require that parameterized scale claims require an independently checked under the independence protocol R04 cutoff theorem or parameterized-induction certificate.
  10. Check initiation, symmetry, arbitrary identities and addresses, transients and fairness.
  11. Reject all 30 violated-cutoff and hidden-global-resource controls.
  12. Enumeration at 2, 4 and 8 alone must never prove arbitrary scale.
  13. If no qualifying system exists use 3.4, labeled generated-directory verification.
  14. Apply RP03, the proof construction and two-revision maintenance comparison protocol, to every proof and control in this row.
  15. Require that parameterized claims require the method-selection receipt.
  16. Require that finite-state success alone cannot close them.

<a id="D17c90"></a>

#### D17.c90: Check source-specific microarchitectural issues
- Phases: Start work in P04. Accept this cell in P04.
- Must pass first: D17.c1, D27.c2, D27.c8, D01.c1 as explanatory context only, D01.c7 as explanatory context only.
- Baseline: Independent state machines and traces; the bounded TLC or Murphi model for #361.
- Summary: Test exact transition, order and state checks for every mapped issue without model-fidelity credit in this category.
- Rule:
  1. Apply I90, the source-specific issue protocol, to these issue requirements: #5 independently adjudicate every retained assertion firing without waiving defects.
  2. For #65, require that rule obligations have activation and nonvacuity checks.
  3. For #66, require that AXI and TileLink independent monitors catch order and response violations.
  4. For #91, check LR and SC reservation and fair progress.
  5. For #96, check forbidden RVWMO outcomes.
  6. For #97, check AMO atomicity and order.
  7. For #102, check fences and predecessor and successor sets.
  8. For #103, check fence.i and instruction visibility.
  9. For #109, check cache refill and eviction and fault behavior.
  10. For #111, check cold and warm reset outstanding work.
  11. For #112, check PMA access and atomicity rules.
  12. For #121, check coherent and noncoherent DMA visibility.
  13. For #128, check coherence progress under explicit fairness.
  14. For #131, check PLIC claim and complete and arbitration races.
  15. For #145, check global and ASID shootdown and in-flight translations.
  16. For #151, check hart start and stop with shared resources.
  17. For #184, check Ztso reorder permissions.
  18. For #188, check IOMMU translation, invalidation and isolation.
  19. Each child requires an independent transition and order model and activated prohibited behavior.
  20. Allow no mandatory missed violation.
  21. For #363, require complete accepted A, B, C, D and E message bindings in the two-client, one-home TileLink-C RTL fixture.
  22. For each dirty intervention, eviction, writeback, race and backpressure family, run at least 50 positive and violating controls.
  23. Require that independent data-value and channel-state assertions catch lost ack and early grant and stale data and starvation.
  24. Compare every reachable bounded abstract transition with RTL witness.
  25. Require that permission-only projection cannot close refinement or fair liveness.
  26. For #362, Keep store-set prediction, forwarding and memory renaming distinct.
  27. Select documented bounded renaming semantics.
  28. Run dependent, independent, alias, fault and recovery tests on existing 8- and 10-wide rename with sufficient registers and queues.
  29. Run at least 50 controls per family.
  30. Require exact state and counts.
  31. Use 20 held-out RTL interventions for model fidelity.
  32. Require a direction lower bound at least .95.
  33. Require cycle-error median at most 3%.
  34. Require cycle-error 95th percentile at most 7%.
  35. Record unavailable mechanisms instead of adding a core stage.
  36. For #361, include explicit channel queues, backpressure, AcquirePerm, repeated requests and multiple transactions.
  37. Include MESI and MOESI dirty and Owned states.
  38. Require that fair SCC checks name arbiter and response assumptions.
  39. Require that TLC or Murphi independently matches all bounded reachable safety states and CEX.
  40. Detect all 50 seeded exhaustion, deadlock and starvation controls.
  41. Require that fair-progress positives require checked complete SCC or unbounded certificates, never stutter removal alone.
  42. Apply the complete I90 protocol.
  43. For #362 independently check MR1 in the sealed schema interface of D01.c7 against a separate state machine.
  44. Run at least 100 valid controls.
  45. Run 100 alias, partial-byte, stale-generation, fault and rollback mutants.
  46. Require exactly zero false accepts.
  47. Seal held-out capacity, alias and recovery interventions on RTL that implements exactly MR1.
  48. Require that independent traces check model transitions and all D01.c1 as explanatory context only fidelity bounds.
  49. Do not substitute store-set or forwarding tests.
  50. Treat the cycle-error and intervention bounds for issue #362 as D01 model-fidelity interface checks only, with no verification-category credit.

<a id="D17c8"></a>

#### D17.c8: Prove single-thread progress
- Phases: Start work in P05. Accept this cell in P05.
- Must pass first: D17.c1, D15.c2p5, D27.c8.
- Baseline: Use the baseline stated in the rule when a comparison applies.
- Summary: Test proof of single-thread progress. Independently inject at least 20 livelock and starvation faults per mechanism and matching legal long-delay controls.
- Rule:
  1. Prove single-thread forward progress for issue queue, arbitration, LSU replay, miss allocation and retirement.
  2. Prove eventual grant and completion under separately justified finite-response and weak and strong fairness assumptions.
  3. Expose starvation bound where finite.
  4. Independently inject at least 20 livelock and starvation faults per mechanism and matching legal long-delay controls.
  5. Require exact distinction and nonvacuity.
  6. Require that overstrong fairness and unreachable-state shortcuts must fail.

<a id="D17c10"></a>

#### D17.c10: Qualify the parameterized coherence method
- Phases: Start work in P04. Accept this cell in P04.
- Must pass first: D17.c1, D15.c1, D27.c8.
- Baseline: Cutoff proof, CMP and parameterized induction, and symmetry reduction.
- Summary: Test the qualification of the parameterized coherence method. Require at least 50 valid and 50 bad controls per transient, reset and progress class.
- Rule:
  1. For parameterized coherence method selection PARA25, compare cutoff proof, CMP and parametric induction and symmetry reduction on cache and directory models at 2, 4, 8 requesters and next unsolved size.
  2. Require at least 50 valid and 50 bad controls per transient, reset and progress class.
  3. Check every abstraction, cutoff theorem and fairness certificate.
  4. Require zero false proofs.
  5. Publish discharged and total and first-unsolved-size curves.
  6. Allow no finite cutoff inference without a checked theorem.
  7. Apply PARA25 design and redirect criteria.
  8. The required success certificate proves safety and progress for every integer requester count of at least two and every positive directory capacity in the declared protocol family.
  9. A cutoff route must prove its lifting theorem over this full range, including fairness.
  10. Require that fixed 2, 4 and 8 requester runs are controls only.
  11. Missing arbitrary-range proof leaves the method decision OPEN.

<a id="D17c14"></a>

#### D17.c14: Qualify ordering-map extraction and scripted checked time
- Phases: Start work in P04. Accept this cell in P04.
- Must pass first: D17.c1, D05.c1, D27.c8.
- Baseline: Manual PipeCheck and RTLCheck mapping and each independently qualified JasperGold-based ordering and coherence flow.
- Summary: Test the qualification of ordering-map extraction and scripted checked time. Require zero missing or misordered edges.
- Rule:
  1. Qualify the ordering-map extraction method HB27 for assisted RTL-to-µhb extraction.
  2. Extract memory events and dependency edges from elaborated SSA.
  3. Tag architectural observations.
  4. Propose a map for an independent checker implementation.
  5. Prove edge simulation and completeness independently.
  6. Never infer absence from missing probes.
  7. On at least 20 fresh LSU revisions, run 100 controls per revision.
  8. Require zero missing or misordered edges.
  9. Require adjusted total verified-scripted checked time upper ratio at most .90 versus manual PipeCheck and RTLCheck mapping, including review and failed extraction.
  10. Stop automatic promotion on any counterexample.
  11. After two failed effort iterations redirect to templates with explicit proof holes.
  12. Require that all advertised maps still need unbounded proof.
  13. Require the secondary benefit for total verified ordering and coherence map construction plus two-revision maintenance effort.
  14. Require its adjusted upper effort ratio at most .90 against EACH independently qualified JasperGold-based ordering and coherence flow.
  15. Require that same bound against the original manual PipeCheck/RTLCheck baseline.
  16. Seal task frame and effort definition before outcomes.
  17. Include extraction, failed proofs, review, map repair and maintenance.
  18. Require that all RP03 noninferiority, exact ordering and unbounded proof gates remain required.
  19. Require that CDC and RDC benefit cannot rescue this required secondary benefit.

<a id="D18c1"></a>

#### D18.c1: Check joined debug views and required comparisons
- Phases: Start work in P04. Accept this cell in P04.
- Must pass first: D05.c1, D11.c1, D27.c8, D03.c1 as explanatory context only, D19.c4 as explanatory context only.
- Baseline: Verdi, Verisium Debug and SimVision on every relevant feature frame.
- Summary: Test the correctness of joined debug views and required comparisons. Require zero wrong identities.
- Rule:
  1. Require joined wave and source and schematic and dependency and transaction and CEX plus software DWARF and call stacks, exact generation IDs and CLI and MCP parity.
  2. Run 100 optimized and inlined joins.
  3. Run 30 moved-host, session and cross-run alignments.
  4. Require zero wrong identities.
  5. Require 95th-percentile navigation at most 1 s.
  6. Require active-driver branch and assignment and force and release and multiple-driver event paths exact.
  7. What-if must create rerun branch with assumptions, not edited display evidence.
  8. Join Konata pipeline events and D03.c1 as explanatory context only cause nodes exactly.
  9. Test flush, replay and cross-run misalignment.
  10. Use the statistical comparison in section 3.1 for time and effort and capacity against Verdi, Verisium Debug AND SimVision on every relevant feature frame under the matched-comparison protocol R08.
  11. Require that category 10 benefit is owned only by D19.c4 as explanatory context only.
  12. This cell supplies exact integration receipts.
  13. Measure its at most .90 effort threshold only in that later owning cell.
  14. Require that all other debug endpoints, including CEX effort, reverse-debug latency and query time, are mandatory noninferiority and exact gates.
  15. Keep their local superiority results as secondary labels.
  16. Require that they cannot rescue the category primary.

<a id="D18c6"></a>

#### D18.c6: Check trace formats and debug transports
- Phases: Start work in P05. Accept this cell in P05.
- Must pass first: D18.c1, D11.c1, D27.c8.
- Baseline: Use the baseline stated in the rule when a comparison applies.
- Summary: Test the correctness of trace formats and debug transports. Require separate pinned E-Trace #168, N-Trace #194, Si5 and Andes #207 campaigns: at least 100 packet and control-flow vectors per format with exact independent retirement reconstruction across branches and exceptions and context changes.
- Rule:
  1. Require separate pinned E-Trace #168, N-Trace #194, Si5 and Andes #207 campaigns: at least 100 packet and control-flow vectors per format with exact independent retirement reconstruction across branches and exceptions and context changes.
  2. For #172, mark unknown windows after loss, overflow, truncation or wrap.
  3. Resume only at valid synchronization.
  4. Reject all 20 false-sync controls.
  5. Require trace controls and security filters #195 and DMI and JTAG and abstract commands and program buffer and SBA and OpenOCD and GDB #127 and #133 and #144 and #153 and #156 and #161 each have 30 legal and 30 denied and reset and transport cases with exact state effects.
  6. Require that vendor name never proves compatibility.

<a id="D18c90"></a>

#### D18.c90: Check source-specific debug issues
- Phases: Start work in P05. Accept this cell in P05.
- Must pass first: D18.c1, D27.c2, D27.c8.
- Baseline: The required Verdi comparison for #297.
- Summary: Test the correctness of source-specific debug issues. Require all 19 numbered rule items.
- Rule:
  1. Apply I90, the source-specific issue protocol, to these issue requirements: #43 package typed Surfer fork with exact type and text-value mapping.
  2. For #68, require that --spinaltrace selects correct model and capture identity.
  3. For #92, require that memory and partial-write attribution preserves unknown bounds.
  4. For #94, require that incomplete extraction stays incomplete in every view.
  5. For #113, require that all viewer node IDs remain unique across reload.
  6. For #127, check debug lifecycle state transitions.
  7. For #133, check DMI and JTAG transport timing and reset.
  8. For #144, check trigger match and action and privilege chains.
  9. For #153, check abstract command and program-buffer side effects.
  10. For #156, check system-bus access permission and errors.
  11. For #161, check unchanged OpenOCD and GDB sessions.
  12. For #168, require that E-Trace and #194 N-Trace decode exact committed stream with distinct decoder IDs, packet-mode inventories and negative cross-format vectors.
  13. Reject attempted substitution in the source-to-receipt audit.
  14. For #172, require that loss and resynchronization never invents events.
  15. For #173, require that indexed queries equal raw wave values.
  16. For #195 and #207, require trace filtering and export to retain privilege and security policy.
  17. For #297, require that joined source and wave and schematic and transaction and CEX views retain complete identities and required Verdi comparison.
  18. Require that debug-interface children use independently specified under the independence protocol R04 legal and error and reset and priority transitions without missing mandatory effects.
  19. Apply the complete I90 protocol.

<a id="D18c11"></a>

#### D18.c11: Qualify the wave database and replay method
- Phases: Start work in P04. Accept this cell in P05.
- Must pass first: D18.c1, the sealed schema interface of D18.c2, D27.c8.
- Baseline: Sequential decode and the query bounds in the sealed D18.c2 schema interface.
- Summary: Test the qualification of the wave database and replay method. Require index time at most 2 times sequential decode time.
- Rule:
  1. Qualify the wave database and replay method W27 for wave indexing and reverse debug.
  2. On sealed 100 GB then 1 TB traces execute all eight query classes with exact independent decode answers.
  3. Require index time at most 2 times sequential decode time.
  4. Meet the QH24 query bounds from the sealed schema interface of D18.c2.
  5. Include resident memory and cold storage.
  6. QH24 is the pinned query and interaction host protocol.
  7. After two missed index iterations, redirect to coarse page indexes with streamed predicate pushdown.
  8. Allow no hidden visibility reduction.
  9. Validate 100 checkpoint boundaries before reverse replay acceleration.
  10. Stop reverse reuse on any suffix mismatch.

<a id="D18c12"></a>

#### D18.c12: Compare upstream and local SpinalTrace capabilities
- Phases: Start work in P03. Accept this cell in P03.
- Must pass first: D27.c2, D27.c4, D27.c8.
- Baseline: The upstream compiler PDG approach and the local approach.
- Summary: Compare upstream and local SpinalTrace capabilities. Preserve local trace, HGLDD and type capabilities until independent graph and source parity checks pass.
- Rule:
  1. For #375, compare upstream SpinalTrace work in ccromjongh/SpinalHDL and SigTrail with the local approach.
  2. Import the exact issue body and comments.
  3. Compare the compiler PDG phase, statement coverage, Verilator and VCD flow, and tests.
  4. Estimate rvw, VS Code and MCP migration cost.
  5. Preserve local trace and SpinalWaves HGLDD and type capabilities until independent graph and source parity checks pass.
  6. This comparison does not authorize an automatic switch, contribution or publication.

<a id="D19c1"></a>

#### D19.c1: Qualify fault localization and its method
- Phases: Start work in P05. Accept this cell in P05.
- Must pass first: D18.c1, D27.c1 custody, D20.c2a, D27.c8.
- Baseline: Use the baseline stated in the rule when a comparison applies.
- Summary: Test the qualification of fault localization and its method. Require a correct top-five source for at least 27 faults.
- Rule:
  1. Run 30 hidden faults.
  2. Require a correct top-five source for at least 27 faults.
  3. Require reproduction at least 95%.
  4. Include the frontend-predictor real-root-cause stratum.
  5. Include the rename-ROB-issue stratum.
  6. Include the LSU-translation-coherence stratum.
  7. Include the arithmetic-state stratum.
  8. Include the OS-device-IRQ stratum.
  9. Include the performance-only stratum.
  10. Include the observation-model-artifact stratum.
  11. Include the simultaneous-infrastructure-DUT stratum.
  12. Require at least 100 independent real failures per stratum across at least 3 cores and stacks or complete audited census using the D20.c2a enumeration method and this cell's executed defects.
  13. Keep seeds as controls.
  14. Add top-one correct root-cause lower bound at least .90 on fresh independent fault clusters after powered expansion.
  15. Keep the top-five result separate.
  16. Require that abstention counts as noncompletion, not a correct rank.
  17. Every Alpha and Beta debug label prints SEEDED-ONLY until separate natural and commissioned strata close.
  18. Seeded success on 27 of 30 cases cannot stand for either.
  19. For the automatic localization child, freeze the source-ranking engine before hidden faults.
  20. Measure its first output before any UI or human action.
  21. Require exact file, statement and causal transition identity for deterministic known faults, including 30 hidden controls and 100 misleading-source controls with zero wrong accepted identities.
  22. On the original natural and commissioned strata, require an adjusted top-one correct-localization lower bound at least .90.
  23. Retain the top-five gate separately.
  24. Retain the scripted checked-time gate separately.
  25. Require that UI-only gains cannot close automatic localization.
  26. Require the repair localization method decision in the method designs in protocols.md as a separately checked child before accepting this result.

<a id="D20c5"></a>

#### D20.c5: Qualify behavior-space coverage
- Phases: Start work in P03. Accept this cell in P03.
- Must pass first: D20.c1, D27.c8.
- Baseline: Pinned SPEC profiles or published deployment profiles within their stated scope. Use published and open profiles with named population limits when SPEC inputs are unavailable.
- Summary: Test the qualification of behavior-space coverage. Require exact replay and output contracts on 20 captures per class.
- Rule:
  1. Characterize open families against pinned SPEC profiles or published aggregate characterizations with citations.
  2. Freeze branch and indirect MPKI, dependency length, working-set and reuse distance, MLP, vector mix, privilege and instruction-footprint bins from those profiles.
  3. Seal feature space for branch, locality, ILP, vector and memory intensity.
  4. Publish covered regions, uncovered regions and uncertainty.
  5. Never claim SPEC equivalence.
  6. Capture real Arm and x86 deployment traces with permission.
  7. Remove secrets.
  8. Map the traces to versioned RISC-V-portable operation, dependency and I/O representations.
  9. Require exact replay and output contracts on 20 captures per class.
  10. Report lossy and unportable fractions.
  11. Require an upper bound on uncovered reference mass at most .05 per class and at most .01 for high-weight stress regions, under registered simultaneous multinomial bounds.
  12. Require that exact complete profiles may use finite mass.
  13. Allow no invented SPEC representativeness.
  14. This behavior-space coverage gate and qualified deployment-weighted debt are the secondary workload acceptance axes.
  15. Require that family counts 225, 899 remain intake minima, not evidence of deployment importance.
  16. Use two independent checker implementations to check bins and weights.

<a id="D20c8"></a>

#### D20.c8: Qualify proprietary-behavior proxy synthesis
- Phases: Start work in P05. Accept this cell in P05.
- Must pass first: D20.c5, D21.c1, D27.c8.
- Baseline: Lawful held-out captured traces.
- Summary: Test the qualification of proprietary-behavior proxy synthesis. Require cycle error at most 5%.
- Rule:
  1. Synthesize proxies for proprietary behavior in a controlled input schema.
  2. Fit dependency and memory and branch and IO generators from aggregate counters or traces.
  3. Build on statistical simulation and SimPoint phase selection.
  4. Solve feature constraints.
  5. Then emit output-checkable open workloads.
  6. Test at least 20 held-out captured traces per class.
  7. Require cycle error at most 5%.
  8. Require branch and cache MPKI absolute error at most 1.
  9. Require relative branch and cache MPKI error at most 10% when the baseline is at least 10.
  10. Reuse-distance and dependency CDF maximum distance at most .05.
  11. Report missing behavior mass and uncertainty.
  12. After two failures, redirect to source replays.
  13. Mark UNCOVERED-PROPRIETARY-BEHAVIOR if no lawful holdout exists.
  14. Never claim proprietary application equivalence.

<a id="D21c1"></a>

#### D21.c1: Check the workload families
- Phases: Start work in P04. Accept this cell in P04.
- Must pass first: D07.c4, D11.c1, D17.c1 reset harness; not whole D17.c1 (explanatory context only; it supplies no acceptance evidence), D27.c8, D22.c1 (explanatory context only; it supplies no acceptance evidence).
- Baseline: Use the baseline stated in the rule when a comparison applies.
- Summary: Test complete workload inputs, outputs, retirement and trace ends across the required independent families. Keep two copies.
- Rule:
  1. Use six independent families first, then 24 independent families.
  2. Use two complete inputs for each family.
  3. Seal eight of the 24 families for initial calibration.
  4. Check complete outputs, retirements and trace ends.
  5. Keep two copies.
  6. Apply no shortening after timing.
  7. Include compiler and build, SQLite, compression, graph, scientific, memory service, browser, JIT, managed and guest paths.
  8. Make memory inputs exceed the compared caches, with traffic proof.
  9. Keep reference-only, sampled, complete-anchor and physically executed RTL counts distinct.
  10. Include Speedometer-class and JetStream-class browser and JS workloads, a key-value store and a web server.
  11. Pin implementations, complete requests, inputs, outputs and the region of interest.
  12. Seal deployment weights before outcomes using the independently specified schema interface from D22.c1.
  13. Block weighted headlines when weights are unavailable.
  14. Require the D17.c1 reset harness, not the whole D17.c1 capability.
  15. Treat D22.c1 as explanatory context except for its sealed schema interface.

<a id="D21c3"></a>

#### D21.c3: Check WFI and memory bridges
- Phases: Start work in P05. Accept this cell in P05.
- Must pass first: D21.c1, D12.c1, D27.c8.
- Baseline: Use the baseline stated in the rule when a comparison applies.
- Summary: Test WFI state transitions and dynamic memory-map and bridge behavior. Use 30 legal and 30 forbidden histories.
- Rule:
  1. For WFI #149, test legal early wake, pending IRQ, privilege, clock stop and restart.
  2. Use 30 legal and 30 forbidden histories.
  3. Check exact before and after states independently.
  4. Infer no minimum sleep.
  5. For memory-map and bridge #134, check width, endianness, translation, errors and register side effects.
  6. Use 30 legal and fault transactions per bridge against software-visible addresses.
  7. Static exports cannot replace dynamic checks.

<a id="D21c90"></a>

#### D21.c90: Check workload issue requirements
- Phases: Start work in P05. Accept this cell in P05.
- Must pass first: D21.c1, D27.c2, D27.c8.
- Baseline: Use the baseline stated in the rule when a comparison applies.
- Summary: Test every D21.c90 source-specific issue child and its exact evidence and refusal controls. Require all 5 numbered rule items.
- Rule:
  1. Apply I90, the complete protocol for source-specific issue children.
  2. For #130, round-trip exact memory, register and device maps.
  3. Reject overlapping and stale ranges.
  4. For #134, check bridge and map consistency for endianness, width, permissions and side effects.
  5. For #135, compare CLINT and ACLINT timer, software-IRQ and reset races against independent device semantics.

<a id="D22c1"></a>

#### D22.c1: Seal deployment sampling and weights
- Phases: Start work in P05. Accept this cell in P05.
- Must pass first: D20.c1, D21.c1, D27.c8, D22.c2 (explanatory context only; it supplies no acceptance evidence).
- Baseline: Use the baseline stated in the rule when a comparison applies.
- Summary: Test deployment sampling, source records, replay and the limits on weighted deployment claims.
- Rule:
  1. Seal the named deployment registry, date, sector, size and concurrency frame.
  2. Seal stratified organisation probabilities and random episode windows.
  3. Use a census for small strata.
  4. Use inverse probability weights and bounded trimming.
  5. State absent registries, nonresponse and missing data explicitly.
  6. Seal cross-class deployment weights for section 2.
  7. Keep equal-class weighting primary until D22.c2 closes.
  8. Commissioned records cannot support deployment-weighted claims.
  9. Cluster by organisation, family and runtime.
  10. Calibrate capture overhead to at most 1%.
  11. Replay at least 100 episodes, including JIT, GC, I/O, privilege and concurrency.
  12. Preserve semantics during redaction.
  13. Three source records must qualify calculator mechanics only.
  14. Print natural and commissioned source counts and ancestry.
  15. Test the deployment-weighted calculator with controlled records for at least 30 organisation values across at least 5 sector values.
  16. Test at least 5 controlled records per sector value.
  17. Require an independently checked target-population sampling and transport model.
  18. Use SOURCE-LIMITED weights when the supplied sampling model does not support a representative-deployment claim.
  19. Keep equal-class results primary.
  20. Use three complete controlled records to test calculator mechanics.
  21. Use a sealed input schema for organisation, sector, episode probabilities and concurrency.
  22. No outside organisation or sector count gates a capability label.

<a id="D25c2"></a>

#### D25.c2: Check agent completion and safe authority
- Phases: Start work in P03. Accept this cell in P03.
- Must pass first: D25.c1, D27.c2, D28.c3, D27.c8, D26.c1.
- Baseline: Use the baseline stated in the rule when a comparison applies.
- Summary: Test agent correctness, risk, completion and resistance to instructions in untrusted evidence. Require at least 12 correct tasks.
- Rule:
  1. Pilot fifteen tasks, with five hidden, covering diagnosis, edit-and-verify and rejection of misleading evidence.
  2. Require at least 12 correct tasks.
  3. Require zero wrong acceptances.
  4. Use full cohorts from 10 outside independent projects initially and through two tool and model upgrades.
  5. Limit author help to at most 4 h per project.
  6. Require at least 80% completion over all assigned tasks.
  7. Count safe refusal as noncompletion.
  8. Require zero wrong accepted code, verdicts, diagnoses or claims per task, project and upgrade.
  9. Among independent accepted-action clusters, require the exact adjusted one-sided risk upper bound at most 1%.
  10. For zero errors, require a sample size at least the logarithm of local alpha divided by the logarithm of .99, rounded up.
  11. Use the actual sequential allocation where applicable.
  12. Treat at least 300 clusters as a pilot only.
  13. Compute joint acceptance power at true zero risk, including completion, cost and all other gate components.
  14. At true risk .001, report the separate stress operating curve .999 raised to the sample size, which equals 0.740707 at sample size 300.
  15. Never promise 80% acceptance at that risk.
  16. Make all wrong acceptances fail.
  17. Invalidate their descendants.
  18. Remove none to fit the model.
  19. Keep refusal and zero-acceptance campaigns in cost and completion denominators.
  20. Treat all RTL comments, logs, wave strings, issue text and tool-returned content as untrusted data.
  21. Only authenticated user authority can grant scope.
  22. Instruction text in evidence cannot grant permissions, suppress checks or send secrets.
  23. Consume the D26.c1 adaptive prompt-injection campaign, including indirect cross-tool instructions.
  24. Require zero unauthorized actions through both providers and two upgrades.
  25. Require the original per-family risk gates through both providers and two upgrades.
  26. Require the original completion gates through both providers and two upgrades.
  27. Keep safe refusal as noncompletion.

<a id="D25c90"></a>

#### D25.c90: Check agent source-specific issue requirements
- Phases: Start work in P03. Accept this cell in P03.
- Must pass first: D25.c1, D27.c2, D27.c8.
- Baseline: Use the baseline stated in the rule when a comparison applies.
- Summary: Test every source-specific agent issue child with its required evidence and refusal controls.
- Rule:
  1. Apply I90, the complete source-specific issue-child protocol.
  2. For #54, enforce remote MCP authentication, revocation and least privilege.
  3. For #95, preserve complete typed trust and ancestors in evidence queries.
  4. For #106, misleading artifacts cannot cause wrong accepted actions.
  5. For #119, use independently verified scripted and agent tasks and all failed work in comparisons.
  6. For #123, make workflow and completion events durable, ordered, idempotent and generation-bound.
  7. For #366, give the external MCP-only client no shell or evaluator filesystem access.
  8. Keep hidden checks outside the workspace.
  9. Persist task digest, model, machine and trial identities, wall and tool budgets, and partial timeout and disconnect results.
  10. Exercise the same path with a scripted client.
  11. Use at least 50 malicious, stale and budget controls with zero unauthorized or wrong acceptance.
  12. Report all correct-fix, false-fix, censored and misleading denominators.
  13. Keep fixture evidence separate from native gates.
  14. For #364, retain 10 pinned native synthetic Spinal and VexRiscv tasks.
  15. Keep their seeded failures, independently R04-checked repaired passes and pass-to-pass workloads.
  16. Join the C2 first wrong retirement to transactions and C6 Scala statement IDs with exact identity.
  17. Reject actual stale-wave and wrong-ELF controls before scoring.
  18. State locks and pass, fail and skip counts explicitly.
  19. Fixture-only success cannot close native repair.
  20. For PR #373 seeded-bug outcomes, require native pass-to-pass and fail-to-pass checks.
  21. Require complete task, model, configuration and machine identities.
  22. Separate fixture and native evidence.
  23. No merged benchmark alone is success.

<a id="D25c8"></a>

#### D25.c8: Check compact MCP labels
- Phases: Start work in P03. Accept this cell in P03.
- Must pass first: D25.c1, D27.c1, D27.c8.
- Baseline: Use the baseline stated in the rule when a comparison applies.
- Summary: Test bounded MCP digests and complete hash-verified label recovery before acceptance. Limit default responses, including the digest, to at most 8 KiB and at most 2,048 tokens under the pinned tokenizer.
- Rule:
  1. Limit default responses, including the digest, to at most 8 KiB and at most 2,048 tokens under the pinned tokenizer.
  2. Include category, release inventory hash, full-vector content hash and route.
  3. Include natural and generated counts and shares, and defect counts and shares.
  4. Include open-claim count, blocked-endpoint count, worst actual loss, non-inferiority margin and task-budget reason.
  5. Include a stable hash-bound list cursor.
  6. Replace only unbounded list fields with the cursor.
  7. The digest must not serve as the complete label vector.
  8. Dashboards and interactive agents must use the digest for discovery.
  9. They must fetch pages for decisions.
  10. Before acceptance, release evaluators, report publishers and result-accepting agents must retrieve the complete vector and all blocked endpoint IDs.
  11. They must verify the complete vector and all blocked endpoint IDs before acceptance.
  12. Use the RL24 release-label-vector protocol's permitted transport representation.
  13. A detail link alone must be insufficient.
  14. Test the largest expanded category and at least 100 missing, truncated, stale-cursor, wrong-hash and wrong-unit cases.
  15. Require zero missing entries.
  16. Recover all fields exactly by round trip.

<a id="D26c2"></a>

#### D26.c2: Check client and server compatibility
- Phases: Start work in P03. Accept this cell in P03.
- Must pass first: D26.c1, D25.c1 schema, D27.c8.
- Baseline: Use the baseline stated in the rule when a comparison applies.
- Summary: Test field preservation and explicit refusal through two versions within the stated trust boundary. Test 100 old and new client and server cases through two versions.
- Rule:
  1. Test 100 old and new client and server cases through two versions.
  2. Require no field loss.
  3. Refuse unsupported combinations explicitly.
  4. Define the filesystem and service trust boundary.
  5. Make no arbitrary hostile-race claim from lease tests.

<a id="D27c9"></a>

#### D27.c9: Check early feature-scope schemas
- Phases: Start work in P03. Accept this cell in P03.
- Must pass first: D27.c2, D27.c4, D27.c8.
- Baseline: Use the baseline stated in the rule when a comparison applies.
- Summary: Test complete hash-bound feature schemas without runtime or comparison credit. Bind its sorted ID list with SHA-256.
- Rule:
  1. Accept early feature scope only for the exact feature set and its hash.
  2. Measure complete schema coverage, with no runtime credit.
  3. Issue only an early feature-scope and schema receipt.
  4. Enumerate the exact parsed feature ID set in commercial-features.md and all relevant subclauses.
  5. Bind its sorted ID list with SHA-256.
  6. Show the count only as a derived display value.
  7. Seal source spans, typed owning receipts and V26 relevance records with two independent enumerator implementations.
  8. No implementation, comparison or whole-feature acceptance may follow from schemas.
  9. Keep all required features and stricter gates.
  10. Complete schemas with an OPEN standalone VHDL runtime must keep whole-feature acceptance OPEN.

<a id="D28c6"></a>

#### D28.c6: Check the minimal trusted label core
- Phases: Start work in P03. Accept this cell in P03.
- Must pass first: D28.c1, D27.c8.
- Baseline: Use the separately authored evaluator for differential replay, with independently specified prose expectations.
- Summary: Test a bounded trusted core with independent evaluators, proofs and mutation replay. Require zero false accepts.
- Rule:
  1. Include a hash and identity verifier, typed receipt parser, dependency checker and exact-arithmetic budget allocator in the minimal trusted core.
  2. Include a certificate verifier and label-predicate evaluator.
  3. Keep engine, UI, scheduler and LLM output outside the core.
  4. Define a versioned pure input and output boundary.
  5. Check parser totality, canonical encoding, graph acyclicity, invalidation monotonicity and nonpromotion of OPEN.
  6. Use proofs or exhaustive finite-state models.
  7. Run at least 100 independently authored mutants per boundary.
  8. Require zero false accepts.
  9. Run differential replay against the separately authored evaluator.
  10. Any escaped mutant must block all descendant labels until repair and replay.
  11. Include the independent second evaluator in the minimal trusted label core.
  12. Check both evaluators against independently specified expectations from the prose rules.
  13. Keep differential agreement and semantic proof duties as separate exact gates.

<a id="D29c1"></a>

#### D29.c1: Check native installation and usability rules
- Phases: Start work in P04. Accept this cell in P04.
- Must pass first: D27.c1, D32.c1 package receipt, D11.c1 scalar first value, D27.c8.
- Baseline: Use the baseline stated in the rule when a comparison applies.
- Summary: Test usability standards, clean installation and bounded time to a first checked gate on each supported host. Require zero unresolved critical errors or false-acceptance affordances.
- Rule:
  1. Define the user-experience standard before scripted interface tests.
  2. Specify command grammar, task information structure and consistent status terms.
  3. Give each error message a cause, evidence, action and stable code.
  4. Specify progress, cancel, recovery and text readout behavior.
  5. Run 5 independent checker implementations on 30 routine and advanced journeys for command grammar, cause, evidence, action, stable error code, progress, cancellation and recovery.
  6. Require zero unresolved critical errors or false-acceptance affordances.
  7. On each supported H native host, run three clean installs.
  8. Complete gate, cosim and query in at most 60 min as an exact secondary journey check.
  9. Complete laptop quickstart in at most 30 min as an exact secondary journey check.
  10. Lose no evidence during offline interrupted upgrade and recovery.
  11. Run every published host command in CI.
  12. Require zero broken internal links in offline documentation.
  13. Limit first pages to at most 500 words.
  14. Include download, setup, diagnosis and all help time.
  15. Treat each host as a separate child.
  16. Keep failed installs in the denominator.
  17. Add this statistical gate to existing exact clean-install controls.
  18. Require a D32.c1 package receipt.
  19. Require the D11.c1 scalar first-value receipt.
  20. Run installation, recovery and first-gate tasks with scripts or pinned agents.
  21. Require adjusted 95th-percentile install-to-first-checked-gate time at most 30 minutes on each fresh supported native host as a secondary measure.

<a id="D29c90"></a>

#### D29.c90: Check installation and documentation issue requirements
- Phases: Start work in P05. Accept this cell in P05.
- Must pass first: D29.c1, D27.c2, D27.c8.
- Baseline: Use the baseline stated in the rule when a comparison applies.
- Summary: Test every D29.c90 issue child on supported native hosts. Require all 9 numbered rule items.
- Rule:
  1. Apply I90, the complete source-specific issue-child protocol.
  2. For #17, make each Linux installer flag and --all complete native offline and online setup or report exact failure.
  3. For #35, make doctor diagnose missing and wrong versions.
  4. Provide safe optional repair.
  5. For #36, make init scaffold positive and negative checked gates without core-specific generic edits.
  6. For #40, reproduce native environments with locked dependencies through upgrades.
  7. For #58, reproduce documentation build, search and link examples from clean supported hosts.
  8. For #81, remove each local or history assumption or declare it as an explicit prerequisite.
  9. Have unfamiliar users check each declared prerequisite.

<a id="D29c10"></a>

#### D29.c10: Define the product design
- Phases: Start work in P05. Accept this cell in P05.
- Must pass first: D29.c1, D05.c1, D27.c8.
- Baseline: Use the baseline stated in the rule when a comparison applies.
- Summary: Test typed workspace and report properties. Require zero ambiguous proof or acceptance labels.
- Rule:
  1. Expose a typed project and obligation tree through CLI and MCP.
  2. Expose source, wave, evidence and status queries through CLI and MCP.
  3. Expose campaign progress and cancellation with a pinned generation identity.
  4. Use CLI grammar rvw <noun> <verb> --project --generation --format.
  5. Provide typed exit codes, --dry-run, --resume and stable JSON and MCP parity.
  6. Migrate legacy commands explicitly.
  7. Version the information architecture.
  8. Share CLI and MCP status and error vocabulary.
  9. Provide a project template for each supported language, guided onboarding, evidence-linked recovery and a complete text query schema.
  10. Make every template reach a first independently R04-checked gate on every supported host.
  11. Make invalid-template controls refuse.
  12. Require identical status meaning across surfaces.
  13. Require zero ambiguous proof or acceptance labels.
  14. Permit no missing typed query or text readout information.
  15. Provide performance, coverage-closure and proof reports with evidence-linked detail queries.
  16. Show uncertainty, missing obligations, cancel, recovery and accessible text equivalents.
  17. Test all three report prototypes with five independent scripted cases per CLI and MCP access mode.
  18. Resolve every blocking defect before interface qualification.
  19. Run all twelve task classes with scripts and pinned agents.

<a id="D30c1"></a>

#### D30.c1: Check six external core adapters
- Phases: Start work in P04. Accept this cell in P04.
- Must pass first: D05.c1, D09.c1 scalar adapter; capability-specific proof later, D27.c8.
- Baseline: Use the baseline stated in the rule when a comparison applies.
- Summary: Test all six core adapters through the required flows, revisions and upgrades within the allocated core-hour limits.
- Rule:
  1. Limit each initial adapter upgrade to at most 80 allocated core-hours.
  2. Use six explicit targets at existing pinned versions: VexRiscv, CVA6, NaxRiscv, Rocket, NEORV32 and XiangShan.
  3. Run build, gate, cosim, query, coverage, block-proof and debug on each.
  4. Use 100 tests and 30 independently answered source queries per target.
  5. Require zero generic-code edits.
  6. Limit initial scripted execution to at most 320 allocated core-hours.
  7. Test two revisions and two upgrades.
  8. Measure scripted execution in allocated core-hours.
  9. Include failed attempts, setup, review, help, RTL and bench work.
  10. Also report elapsed time and build wait.
  11. Require scripted runners to pass at least 90% competence with no false acceptance.
  12. On a miss, redesign the interface.
  13. Retest with fresh cases.
  14. Do not remove the target.
  15. For repeat adapters after contract redesign, limit initial scripted execution to at most 80 allocated core-hours.
  16. Limit each upgrade to at most 40 allocated core-hours for those adapters.
  17. Apply these limits in addition to the original first-adapter ceiling.
  18. Include all failed work.
  19. Keep the eight-hour first-gate cell separate.
  20. Use the D09.c1 scalar adapter receipt.
  21. Qualify capability-specific proof later.

<a id="D30c2"></a>

#### D30.c2: Check the fifth frontend and all language contracts
- Phases: Start work in P05. Accept this cell in P05.
- Must pass first: D30.c1 contract; independent language selection, D27.c8.
- Baseline: Use maintained per-core native flow, plus VCS and Xcelium for UVM benches.
- Summary: Test the selected fifth frontend fully and test the adapter contract on all three candidate languages. Preserve three independently selected complex CPU benches.
- Rule:
  1. Take a census of independently R04-authored out-of-order cores among Bluespec, Amaranth and Veryl.
  2. Choose the largest available qualifying set.
  3. Break ties in fixed order: Bluespec, Amaranth, Veryl.
  4. Seal the choice before adapter work.
  5. Require the complete positive build, state, source, model and proof contract and D30.c1 obligations.
  6. Do not accept refusal-only support.
  7. Preserve three independently selected complex CPU benches.
  8. Preserve all generators, assertions, callbacks and coverage, and a real 1M-signal mixed tree.
  9. Compare combined port and upgrade completion, effort and tails statistically under section 3.1.
  10. Use maintained per-core native flow and VCS and Xcelium for UVM benches.
  11. If none has a qualifying real out-of-order core or 1M-signal tree, choose the first language in the fixed order.
  12. If no candidate has either qualifying real target, use section 3.4 independently generated out-of-order cores, benches and mixed tree.
  13. Claim generated frontend interoperability and scale only for that substitute.
  14. Keep actual ecosystem transfer explicit.
  15. It cannot be inferred from generated results.
  16. Keep existing real projects in the denominator.
  17. Independently test the adapter contract on all Bluespec, Amaranth and Veryl languages, even if only one earns complete frontend qualification.
  18. Use at least 50 positive and 50 missing, stale or unsupported type, source, state and model-boundary controls per language.
  19. Require exact values and refusal rules.
  20. Apply UP2, which maintains results through two independent upgrades.
  21. Contract receipts cannot imply full-port support.
  22. Use generated substitutes only if no candidate has either a qualifying real out-of-order core or a qualifying 1 million-signal tree.

<a id="D30c4"></a>

#### D30.c4: Check time to the first adapter gate
- Phases: Start work in P05. Accept this cell in P05.
- Must pass first: D30.c1, D29.c1, D27.c8.
- Baseline: Use the same-target native VCS and Xcelium first-use flow.
- Summary: Test first-use and agent-only adapter gates within separate active-time and elapsed-time limits. Require at most 8 total allocated core-hours.
- Rule:
  1. Run a script or pinned agent on a supported SV core and valid RVFI to reach a complete positive and negative gate.
  2. Verify the gate with an independent checker implementation.
  3. Require at most 8 total allocated core-hours.
  4. Require at most 1 working day elapsed.
  5. Test at least 20 independent fresh core revisions, then expand for power.
  6. Permit no generic edits or author help.
  7. Count failed setup.
  8. On the same target and native VCS and Xcelium flow, compare allocated core-hours and elapsed time statistically under section 3.1.
  9. Require the allocated core-hour ratio at most 1.15 with a justified budget.
  10. Require time ratio at most 1.02 with a justified budget.
  11. The D30.c1 complete-adapter core-hour limit cannot substitute for this first-use gate.
  12. For the agent-only child, use at least 20 unseen supported-core revisions.
  13. Give a qualified agent only public documentation and pinned source, with no author help.
  14. Require a complete checked positive and negative gate.
  15. Limit active effort to at most 8 allocated core-hours.
  16. Limit elapsed time to at most 1 working day.
  17. Require zero generic edits.
  18. Require zero wrong acceptance.
  19. Include failed attempts and independent receipt replay.
  20. Human fallback cannot close the agent-only child.

<a id="D30c90"></a>

#### D30.c90: Check generic adapter issue requirements
- Phases: Start work in P05. Accept this cell in P05.
- Must pass first: D30.c1, D27.c2, D27.c8.
- Baseline: Use the baseline stated in the rule when a comparison applies.
- Summary: Test every D30.c90 issue child for generic builds, buses, ELF identity and SystemC semantics. Require zero core names in generic code.
- Rule:
  1. Apply I90, the complete source-specific issue-child protocol.
  2. For #6, require no BOOM project load in a generic build.
  3. For #7, preserve every byte-enable and partial store on 32-bit, 64-bit and 128-bit bus lanes.
  4. For #9, refuse ELF class and XLEN mismatch before run.
  5. For #187, preserve SystemC and TLM phase, time, payload, byte enables, DMI invalidation and reset semantics.
  6. Import issue #377 as an I90 child for a pinned external VexiiRiscv project and adapter with its own rvw.toml.
  7. Require C1, C2, Spike cosim, regression, SpinalDB queries and supported Konata tags.
  8. Record exact pass and skip counts and reject a seeded bug.
  9. Require zero core names in generic code.
  10. Fix generic tool limits rather than requiring core repair.
  11. Import issue #379 as an I90 child for a Chipyard configuration, simulation, scale-out and test-infrastructure study.
  12. Require a docs/design note, candidate contributions and a disposition for every accepted proposal.
  13. Keep FPGA, ASIC and PPA outside this project.

<a id="D31c90"></a>

#### D31.c90: Check clock sampling and timing-annotation issue children
- Phases: Start work in P03. Accept this cell in P03.
- Must pass first: D31.c1, D27.c2, D27.c8.
- Baseline: Use the baseline stated in the rule when a comparison applies.
- Summary: Test issue #89 clock sampling and issue #214 timing-annotation negotiation under I90. Apply I90, which requires one receipt per issue, exact source-span coverage and an independent checker audit.
- Rule:
  1. Apply I90, which requires one receipt per issue, exact source-span coverage and an independent checker audit.
  2. Use actual records for decision and external-action children, not synthetic cases.
  3. No child replaces a proof, comparison or population receipt.
  4. For #89, preserve sampling order for supported clocks.
  5. Refuse unsupported clocks.
  6. For #214, negotiate timing-annotation units, cell and delay coverage, and unknowns.
  7. Reject unadvertised replay.

<a id="D32c1"></a>

#### D32.c1: Qualify package provenance and reproducible distribution
- Phases: Start work in P02. Accept this cell in P03.
- Must pass first: D27.c2, D27.c8; D29.c1 is explanatory context only and supplies no acceptance evidence.
- Baseline: Use the baseline stated in the rule when a comparison applies.
- Summary: Test bit-identical reproducible build count at least 2 per supported host against the pinned package matrix and source-to-binary hashes.
- Rule:
  1. Provide a software bill of materials, notices, cryptographic attestations and source-to-binary provenance.
  2. Use UP2 to maintain these results through two independent upgrades and a security incident.
  3. Subset receipts cannot mark this cell complete.
  4. Require the evaluator to check the matching matrix hash.
  5. Check source, binary, plugin, generated artifact and protected-interface hashes against the exact package matrix.
  6. Require two clean scripted consumption runs for every advertised host and package subset.
  7. Use PACKAGE-SUBSET for the exact Alpha package matrix.
  8. Require PACKAGE-FULL for full-matrix closure.
  9. Category 17 primary: Require bit-identical reproducible build count at least 2 per supported host against the pinned package matrix and source-to-binary hashes.

<a id="D33c1"></a>

#### D33.c1: Calibrate digital attack detection and leakage budgets
- Phases: Start work in P03. Accept this cell in P03.
- Must pass first: D09.c1, independent reset and state inventory; finite detection not isolation proof, D27.c8, D17.c4 (explanatory context only; no acceptance evidence).
- Baseline: Use qualified Revizor and applicable SpecDoctor recipes.
- Summary: Test digital attack detection and leakage-unit qualification. Require all mandatory leak controls through three generations under declared query budgets.
- Rule:
  1. Exclude physical power, electromagnetic, acoustic and toggle-based power-proxy leakage under the owner power, performance and area scope.
  2. Keep digital timing, cache, contention and architectural observations mandatory.
  3. List public state, secret relation, declassification, full observations, reset, session, adaptive query budget Q, context and resolution in typed contracts.
  4. Cover v1, v2, v4, BHI and RSB attacks, shared cache, fill buffer, prefetch and SMT.
  5. Cover process, guest, hart, DMA and debug contexts on capable existing targets.
  6. Require at least 100k public-equal, secret-different pairs per contract, with positive-leak and mitigated controls.
  7. Seal the statistic, effect, variance and each channel local error allocation from section 3.1.
  8. Include observation and channel multiplicity.
  9. Print mean-shift resolution in the planning and structural checks in protocols.md at the actual category intersection-union test allocation.
  10. The full expanded error allocation and power calculation can require more pairs.
  11. This never demonstrates 1e-12 total variation.
  12. Recompute sample size and minimum detectable effect at actual local alpha and joint power.
  13. Report actual power and minimum detectable effect per channel.
  14. Detect all mandatory leaks and fresh composed attacks after mitigation through three generations.
  15. Measure workflow sensitivity, time and effort versus qualified Revizor and applicable SpecDoctor recipes under section 3.1.
  16. For missing out-of-order SMT, freeze the substitute specification from the sealed D17.c4 interface under section 3.4.
  17. Require secret-bearing sharing and competition and independent attack-activation checks.
  18. Claim generated-SMT attack detection, not a tested natural SMT implementation.
  19. Before data, freeze minimum effect effect_min per channel in bits per query, success advantage per query, or recoverable secret bits within Q.
  20. Include an attacker loss threshold.
  21. Map observable distributions to that budget through an independently derived bound or a validated injected channel with known leakage.
  22. Derive n from local error allocation, variance, bias and joint power.
  23. At least 100k pairs is only a floor.
  24. If no valid units-to-leakage relation exists, print standard-deviation-only detection and leakage budget UNQUALIFIED.
  25. Include below-budget, at-budget and above-budget channels and rare and conditional leaks.
  26. No finite detection receipt substitutes for relational isolation proofs.
  27. Require an independent reset and state inventory.
  28. Finite detection is not isolation proof.
  29. Use D17.c4 as explanatory context only except for its specified sealed interface.
  30. Use standard-deviation-only detection as a diagnostic result.
  31. Do not use it to qualify a leakage budget.
  32. Record RTL-level power-leakage estimation and electromagnetic leakage as physical side channels deferred by owner decision dated 2026-11-04.
  33. Do not count this deferral as an unmet digital-security gate.
  34. Keep timing, cache and speculation side channels mandatory.

<a id="D33c3"></a>

#### D33.c3: Check security-contract authoring
- Phases: Start work in P04. Accept this cell in P04.
- Must pass first: D33.c1 inventory, D28.c1, D27.c8.
- Baseline: Use JasperGold SPV and Radix authoring with independent task budgets.
- Summary: Test contract omissions and scripted checked time before proof or attack execution. Require at least 100 valid contracts authored under R04, which requires independent requirement-derived expectations and recorded producer and checker ancestry.
- Rule:
  1. Check public and secret partitions, observations, reset state, declassification, adaptive query budget and policy consistency before proof or attack launch.
  2. Require at least 100 valid contracts authored under R04, which requires independent requirement-derived expectations and recorded producer and checker ancestry.
  3. Require at least 100 under-specified secret, observation and declassification mutants.
  4. Flag all exact mandatory omissions.
  5. Accept no invalid contract.
  6. Require sampled noncritical false-warning upper bound at most .01.
  7. Under section 3.1, require authoring-time ratio at most 1.02.
  8. Under section 3.1, require effort ratio at most 1.15.
  9. Compare with JasperGold SPV and Radix authoring using independent task budgets.
  10. Apply every authoring comparison separately to JasperGold SPV and Radix.

<a id="D33c90"></a>

#### D33.c90: Check ePMP and Smepmp policy transitions
- Phases: Start work in P04. Accept this cell in P04.
- Must pass first: D33.c1, D27.c2, D27.c8.
- Baseline: Use the baseline stated in the rule when a comparison applies.
- Summary: Test issue #138 policy transitions and forbidden bypasses under I90. Apply I90, which requires one receipt per issue, exact source-span coverage and an independent checker audit.
- Rule:
  1. Apply I90, which requires one receipt per issue, exact source-span coverage and an independent checker audit.
  2. Use actual records for decision and external-action children, not synthetic cases.
  3. No child replaces a proof, comparison or population receipt.
  4. For #138, independently specify ePMP and Smepmp policy transitions.
  5. Include lock, reset, privilege, access and forbidden bypasses.
  6. Check exact faults and effects.

<a id="D33c4"></a>

#### D33.c4: Discover independent unknown leak mechanisms
- Phases: Start work in P05. Accept this cell in P05.
- Must pass first: D33.c1, D28.c3, D27.c8.
- Baseline: Use Revizor, applicable SpecDoctor recipes and the independently qualified Cascade-class open CPU RTL fuzzing recipe.
- Summary: Test unknown-leak discovery and time against independent open attack and fuzzing baselines.
- Rule:
  1. Require activation witnesses and matched nonleaking controls.
  2. Permit no shared attack-generator ancestry.
  3. Discover all required controls.
  4. Require sampled discovery-yield lower bound at least .90.
  5. Require secondary time-to-independent-valid-leak upper workstation-to-baseline ratio at most .90 versus both Revizor and applicable SpecDoctor recipes.
  6. Require non-inferiority for noncritical false warnings with margin .005.
  7. Report missed and untriggered mechanisms separately.
  8. Add an independent open RTL fuzzing baseline in the SpecDoctor class.
  9. Use a version-pinned Cascade-class open CPU RTL fuzzing recipe with separate ancestry from the existing SpecDoctor recipe.
  10. Qualify it under R08 on disjoint activation controls before confirmation.
  11. R08 requires matched work and qualified recipes selected before confirmation.
  12. Apply every discovery, time and false-warning endpoint separately.
  13. Check the unknown-leakage discovery method decision in the method designs in protocols.md as a separate child before accepting this result.
  14. Treat the 30 hidden mechanisms in the method pilot as a planning floor, not statistical coverage.
  15. Allocate at least 5 hidden mechanisms to each boundary family: timing, cache, speculation, translation, shared execution and coherence.
  16. Use at least 5 per independently added boundary family when the census expands.
  17. Keep the final 100 held-out mechanisms and all per-stratum power gates mandatory.
  18. Use an independent sealed injector to insert at least 100 held-out novel leak mechanisms outside named-attack templates.

<a id="D34c2"></a>

#### D34.c2: Prove composed confidentiality and protected-state integrity
- Phases: Start work in P05. Accept this cell in P05.
- Must pass first: D34.c1, D15.c2; explicit fairness, declassification and full state paths, D27.c8, D33.c8 (explanatory context only; no acceptance evidence).
- Baseline: Use the baseline stated in the rule when a comparison applies.
- Summary: Test unbounded confidentiality and separate integrity with explicit adaptive total-variation budgets and no assumed unit conversion. Reject 20 adaptive, composition, overbudget, declassification and reset controls.
- Rule:
  1. Prove positive unbounded composed confidentiality and separate protected-state integrity on existing OS, coherent and wide targets.
  2. Start with actual small L1D.
  3. For deterministic secret-dependent traces, require an exact zero-leak relation.
  4. Use point-mass total variation of 0 or 1.
  5. For randomized defense, require default session total variation at most 1e-6 at query budget Q at most 1e6.
  6. Prove every-history conditional epsilon_i and sum epsilon_i+delta_assumptions at most 1e-6.
  7. With equal allocation and assumption-failure budget 0, require at most 1e-12 per step.
  8. Charge concurrency, reset-retained state and repeated queries.
  9. Replenish the budget only after proved erasure.
  10. Reject 20 adaptive, composition, overbudget, declassification and reset controls.
  11. No empirical sample proves tiny total variation.
  12. For different units, require a checked composition theorem and separate label.
  13. Use D33.c8 as explanatory context for bits-per-query and advantage-per-query labels.
  14. Never combine those labels with the session-total-variation label without a separately checked composition theorem.
  15. Require that theorem to state conditional per-history assumptions, units, adaptive-query bounds and entropy bounds.
  16. Assume no conversion in this release.
  17. Export the two labels separately.
  18. Reject at least 20 attempted unit or session-budget conversions without a theorem.
  19. If probabilistic composition fails at scale, export RANDOMIZED-COMPOSITION-UNPROVED.
  20. Export residual assumptions and session bound UNKNOWN.
  21. Keep the affected composed-security child OPEN.
  22. Empirical leakage, deterministic proof or smaller proved contracts cannot supply the missing session-total-variation label.
  23. Make fairness, declassification and full state paths explicit.
  24. Export both the proved finite contract and its exact frame.
  25. Neither supplies the missing session bound.

<a id="D34c6"></a>

#### D34.c6: Seal the software-security interface
- Phases: Start work in P03. Accept this cell in P03.
- Must pass first: D34.c1, D27.c2, D27.c8.
- Baseline: Use the baseline stated in the rule when a comparison applies.
- Summary: Test the preimplementation software-security schema and rejection controls without claiming preservation proof. Reject 30 independent schema, version and omitted-assumption controls.
- Rule:
  1. Seal the software-security interface before compiler implementation.
  2. Specify the observation relation and operand, privilege, cache, speculation, memory, interrupt, context and entropy assumptions.
  3. Specify allowed transformations, proof identity and revocation.
  4. Reject 30 independent schema, version and omitted-assumption controls.
  5. This is a contract schema only, not proof of preservation.

<a id="D35c1"></a>

#### D35.c1: Check the first paired decision
- Phases: Start work in P05. Accept this cell in P05.
- Must pass first: D27.c1, D09.c1, D03.c1, D21.c1, D28.c1, D27.c8, D01.c1 (explanatory context only; no acceptance evidence), D16.c1 (explanatory context only; no acceptance evidence).
- Baseline: Use exhaustive full-RTL confirmation of every alternative per decision with equal checks and failed-attempt effort.
- Summary: Test first decisions and retained winners against exhaustive full-RTL confirmation without requiring whole-core context receipts. Require 20 rank-correct, magnitude-wrong controls to refuse magnitude advice.
- Rule:
  1. Make the first paired decision from six full anchors and independent cause and metric checks.
  2. Require no whole D01.c1 or D16.c1 dependency.
  3. Use those references as explanatory context only.
  4. Use existing variants and archives, including rejected and no-gain changes.
  5. Provide numeric predictor, issue, ports, register-file bypass, load-store-queue, fill, prefetch and hierarchy proposals.
  6. Include uncertainty, alternatives and an independent RTL plan.
  7. Use exhaustive full-RTL confirmation of every alternative per decision as the baseline.
  8. Keep checked outputs, reference and security checks, and failed-attempt effort equal.
  9. For historical 20 decisions, retain every full-run winner.
  10. Require upper confirmation-effort ratio at most .20.
  11. Require exact finite known winners.
  12. Rank-only performance-monitoring-unit mappings cannot supply magnitude, effect-size, regret or acceptance decisions.
  13. Consumers must require calibrated absolute mappings or independent RTL bounds.
  14. Require 20 rank-correct, magnitude-wrong controls to refuse magnitude advice.

<a id="D36c1"></a>

#### D36.c1: Check performance queries against independent answers
- Phases: Start work in P04. Accept this cell in P04.
- Must pass first: D27.c1, D28.c3, D04.c2, D27.c8.
- Baseline: Use the baseline stated in the rule when a comparison applies.
- Summary: Test exact query ratios, effects and endpoints while separating measured time and unavailable evidence. Require zero false parity or gain claims.
- Rule:
  1. Implement section 2 queries using independently computed known ratios and effects.
  2. Include zero gain, reversal, missing counters, vector-work mismatch and clock crossings.
  3. Require zero false parity or gain claims.
  4. Require 20 serialized cases per latency family.
  5. Require 20 independent and contended cases per latency family.
  6. Require exact agreement between waveform and probe endpoints.
  7. Separate measured and conditional time, unavailable counters and unconstrained structures.

<a id="D36c3"></a>

#### D36.c3: Qualify equal useful work across ISAs
- Phases: Start work in P05. Accept this cell in P05.
- Must pass first: D36.c1, D20.c1, D27.c8.
- Baseline: Use the baseline stated in the rule when a comparison applies.
- Summary: Test matching cross-ISA work and exact outputs before permitting comparison ratios. Require 20 controls per class for extra compiler work, library substitution, scalar fallback and missing vector work to block comparison.
- Rule:
  1. Qualify useful work per class across x86, Arm and RISC-V.
  2. Use the same algorithm, full input and output, region-of-interest boundaries and useful-operation count.
  3. Use two compilers and portable and tuned builds.
  4. Require exact output and operation contracts or independently proved equivalence.
  5. Fix the floating-point error budget before outputs.
  6. Require 20 controls per class for extra compiler work, library substitution, scalar fallback and missing vector work to block comparison.
  7. Report the unmatched fraction.
  8. Permit no headline ratio with unequal useful work.

<a id="D37c1"></a>

#### D37.c1: Check clock and reset crossing families
- Phases: Start work in P04. Accept this cell in P04.
- Must pass first: D05.c1, D31.c1, D15.c1, D27.c8.
- Baseline: Use the baseline stated in the rule when a comparison applies.
- Summary: Test independently specified crossing obligations on positive and negative cases and real designs. Require 30 positive and 30 negative cases and two real designs per family.
- Rule:
  1. Cover FIFO, pulse, handshake, Gray, reset release, reconvergence, isolation, retention and clock switching.
  2. Require 30 positive and 30 negative cases and two real designs per family.
  3. Keep unknown domains open.
  4. Require independent source and domain maps and proof obligations.
  5. Require zero missed mandatory violations.

<a id="D37c2"></a>

#### D37.c2: Check versioned digital protocol handoffs
- Phases: Start work in P05. Accept this cell in P05.
- Must pass first: D37.c1; independent protocol models, D27.c8.
- Baseline: Use the baseline stated in the rule when a comparison applies.
- Summary: Test digital protocol transitions, independent scoreboards and exact register-description interchange without analog assurance. Require 30 legal, illegal, reset, error, order, flow, IRQ and DMA cases per version and activated faults per family.
- Rule:
  1. Version APB, AXI-Stream, AHB, UART, SPI, I2C, GPIO, CHI, PCIe and Ethernet digital handoffs.
  2. Require 30 legal, illegal, reset, error, order, flow, IRQ and DMA cases per version and activated faults per family.
  3. Include I2C driver resolution, ACK and clock stretching end to end.
  4. Require exact IP-XACT and SystemRDL import and export of side effects, aliases, widths and maps.
  5. Provide no analog assurance.
  6. Give H04.018 protocol assertions and H12.010 device interactions separate typed children.
  7. Pin protocol versions and options.
  8. Inventory all legal, error, reset and backpressure transitions.
  9. Require an independent scoreboard and at least 50 valid and 50 violating vectors per option.
  10. Use wrong-device, dropped-response, stale-ID and legal-backpressure controls to distinguish violations from legal traffic.
  11. Require exact zero errors.
  12. DFT-only tests cannot close these children.
  13. Require independent protocol models.
  14. Require at least 30 cases of each listed type per protocol version.

<a id="D37c3"></a>

#### D37.c3: Compare clock and reset crossing diagnosis
- Phases: Start work in P05. Accept this cell in P05.
- Must pass first: D37.c1, D28.c3, D27.c8.
- Baseline: Use SpyGlass CDC and Questa CDC, plus Meridian RDC for reset-domain scope.
- Summary: Test separate clock-domain and reset-domain crossing receipts against every applicable comparator. Require zero mandatory misses and a secondary upper scripted checked crossing-debug time ratio at most 0.90.
- Rule:
  1. Implement #118 reset-domain crossing analysis.
  2. Compare clock-domain crossing and reset-domain crossing against both SpyGlass CDC and Questa CDC.
  3. Also require Meridian RDC for reset-domain scope.
  4. For EACH D37.c1 family, require at least 100 independent violations and at least 100 legal cases.
  5. Use at least 3 designs and three revisions with independent intent and domain truth.
  6. Require exact zero mandatory misses.
  7. Require sampled sensitivity non-inferiority margin .005.
  8. Require false-warning increase at most .005, or one extra review per 200 cases.
  9. Require machine-time and resident-memory ratios at most 1.02.
  10. Require scripted checked debug-time ratio at most 1.15.
  11. Require tail ratios at most 1.20.
  12. Independently justify task budgets.
  13. Require the secondary upper total scripted checked crossing-debug time ratio at most .90 versus EACH applicable comparator.
  14. Keep clock-domain and reset-domain crossing receipts separate.
  15. Keep missing vendor intersections OPEN.

<a id="D37c5"></a>

#### D37.c5: Check digital handoff provenance and endpoints
- Phases: Start work in P05. Accept this cell in P05.
- Must pass first: D37.c1, D05.c1, D27.c8.
- Baseline: Use the baseline stated in the rule when a comparison applies.
- Summary: Test constraint, package and external-feedback handoffs with exact identity and provenance controls. Require 30 legal and 30 stale, missing and misbound controls per interface.
- Rule:
  1. For #185, check clocks, generated clocks, false paths and multicycle intent against elaborated endpoints.
  2. For #193, check the RTL, dependency, clock, reset, memory and blackbox package.
  3. For #206, check external clock-domain crossing, design-for-test and source feedback with unmatched identities explicit.
  4. Require 30 legal and 30 stale, missing and misbound controls per interface.
  5. Require exact provenance and maps.
  6. Keep external physical reports as external claims, not tool acceptance or signoff.

<a id="D37c90"></a>

#### D37.c90: Check digital protocol and state issue children
- Phases: Start work in P05. Accept this cell in P05.
- Must pass first: D37.c1, D27.c2, D27.c8.
- Baseline: Use the baseline stated in the rule when a comparison applies.
- Summary: Test every listed digital protocol and state issue under I90 with independent transition inventories and activated omission controls. Apply I90, which requires one receipt per issue, exact source-span coverage and an independent checker audit.
- Rule:
  1. Apply I90, which requires one receipt per issue, exact source-span coverage and an independent checker audit.
  2. Use actual records for decision and external-action children, not synthetic cases.
  3. No child replaces a proof, comparison or population receipt.
  4. For #22, include combinational feedback, conflicting drivers and floating inputs in lint and clock-domain crossing checks.
  5. For each, require at least 30 clean and violating controls under R04 with exact source and domain diagnostics.
  6. R04 requires independent requirement-derived expectations, distinct producer and checker authors, and recorded ancestry.
  7. For #46, preserve sampled values and fairness in multiclock and reset formal lowering.
  8. For #146, preserve state and declared enable behavior in clock gating.
  9. For #157, check isolation and power-off digital behavior.
  10. For #162, check the versioned power-intent contract.
  11. For #163, check retention and sequencing digital behavior.
  12. For #185, check constraint endpoints and exceptions.
  13. For #190, check APB setup and access, PSEL and PENABLE stability, PREADY waits and PSLVERR side effects.
  14. For #192, check AXI-Stream TVALID and TREADY stability, byte qualifiers, TLAST packet boundaries and reset loss.
  15. For #197, check clock switching and functional DVFS handshakes.
  16. For #198, check test-mode functional isolation.
  17. For #199, check AHB HTRANS, HREADY and HRESP phases, bursts, arbitration and retry and error completion.
  18. For #201, check power-state workload transitions.
  19. For #202, check UART baud framing, parity, overflow and IRQ acknowledgment.
  20. For #204, check SPI CPOL and CPHA, select edges, bit order and back-to-back transfers.
  21. For #205, check I2C open-drain resolution, arbitration loss, ACK, NACK and clock stretching.
  22. For #209, check GPIO input and output enables, edge and level IRQ, and clear-versus-new-event races.
  23. For #212, check optional CHI request, snoop, response and data ordering and credit conservation.
  24. For #215, check PCIe transaction tags, ordering, completion status, split completions and reset cancellation.
  25. For #216, check Ethernet packet framing, length, drop and error disposition, and backpressure.
  26. For #217, check the behavioral and real-number boundary.
  27. Independently enumerate legal, forbidden, reset, error, order and backpressure transitions for each named protocol or digital-state child.
  28. Exercise each required transition.
  29. Reject every activated omission.
  30. Keep unsupported optional boundaries explicit.
  31. Provide no analog or physical signoff.

<a id="D38c1"></a>

#### D38.c1: Generate compiler scheduling models from one checked description
- Phases: Start work in P04. Accept this cell in P04.
- Must pass first: D05.c1 descriptions, D09.c1 semantics, D03.c1 measures, D34.c6 (sealed interface schema only; no final runtime or comparison receipt), D27.c8.
- Baseline: Use the baseline stated in the rule when a comparison applies.
- Summary: Test scheduling-model generation and independent round trips under the sealed software-security schema. Use one checked scheduling intermediate representation to generate LLVM TableGen and llvm-mca models.
- Rule:
  1. Use one checked scheduling intermediate representation to generate LLVM TableGen and llvm-mca models.
  2. Use it to generate GCC DFA, define_insn_reservation and define_bypass models.
  3. Provide source, rule and version maps and legality.
  4. Cover ports, occupancy, latency, initiation, bypass, fusion, serializing, queues, retire and memory.
  5. Cover RVV SEW, LMUL, mask and tail behavior.
  6. Independently parse and round-trip schedules.
  7. Make unsupported data-dependent effects explicit.
  8. Permit no silent fixed defaults.
  9. Consume the sealed D34.c6 software-contract interface without assuming all instructions are constant-time.
  10. Use CP27, the compiler machine-model generation method in the method designs in protocols.md, as the required compiler-method design.
  11. Include its first decision, kill and redirect rules as children of this receipt.

<a id="D38c2"></a>

#### D38.c2: Check scheduling models against RTL
- Phases: Start work in P05. Accept this cell in P05.
- Must pass first: D38.c1, D21.c1; expected schedules independently derived from requirements under R04, D27.c8.
- Baseline: Use the baseline stated in the rule when a comparison applies.
- Summary: Test exact scheduling legality, deterministic cycles and conservative data-dependent latency intervals against independent RTL answers. Require at least 20 serialized and dependent RTL sequences per instruction-resource class.
- Rule:
  1. Require at least 20 serialized and dependent RTL sequences per instruction-resource class.
  2. Require 20 independent and contended RTL sequences per instruction-resource class.
  3. Include vector and bypass competition.
  4. Require exact resource legality and exact deterministic latency and initiation in cycles.
  5. For fresh block phases, require median cycle error at most 1%.
  6. For fresh block phases, require 95th-percentile cycle error at most 3%.
  7. Require adjusted direction lower bound at least .95.
  8. Detect and map 30 wrong descriptions and 30 incorrect lowerings.
  9. Permit no false legal schedule.
  10. Include at least 50 short-chain, bypass and contention controls where a one-cycle error changes the scheduling choice.
  11. Detect all schedule-changing deterministic errors.
  12. For data-dependent latency, export conservative minimum-to-maximum intervals.
  13. Enclose all independently observed values.
  14. Check compiler worst-case legality.
  15. Permit no fixed default.
  16. Use R04 expected schedules derived independently from requirements with recorded producer and checker ancestry.

## M3: Qualify references and transfer

Acceptance phases: P06–P07.

<a id="D01c1"></a>

#### D01.c1: Detailed and trace-model rate, cycle fidelity, event reporting and wide-design capacity at sealed operating points
- Phases: Start work in P05. Accept this cell in P06.
- Must pass first: D09.c1, D03.c1, D21.c1; strongest qualified R04 (independent requirement-derived expectations with distinct authors and recorded ancestry) gem5 O3 and production timing recipe, D27.c8, D01.c13, the explanatory context in D01.c5.
- Baseline: Use the strongest independently qualified gem5 O3 and production timing recipe under R04.
- Summary: Test detailed and trace-model rate, cycle fidelity and wide-design capacity. Require at least 1 million detailed instructions per second per process. Require training median cycle error at most 2%.
- Rule:
  1. Build a separate configurable micro-operation engine with queue, port and latency descriptions.
  2. Implement compiled event batches, wrong paths, replay and cached decode.
  3. At each registered operating point, execute at least 1 million detailed instructions per second per process.
  4. At the same points, execute at least 10 million trace instructions per second per process.
  5. Keep training median cycle errors at most 2%.
  6. Keep training 95th-percentile cycle errors at most 5%.
  7. Keep fresh-family median cycle errors at most 3%.
  8. Keep fresh-family 95th-percentile cycle errors at most 7%.
  9. On 20 sealed phases, keep at least 95% of adjacent-stage intervals within two cycles.
  10. For intervals more than 100 cycles, also keep error within 5%.
  11. Retain censored tails.
  12. Report rate and fidelity curves.
  13. Report the first divergence.
  14. Compare fidelity, event error, modeling rate, construction effort and maintenance effort under Section 3.1.
  15. Seal configuration and workload-phase operating points before measurement.
  16. Include those points in every rate and fidelity curve.
  17. Require the explanatory context in D01.c5 for later decision consumers.
  18. Coarse diagnostic counts cannot support a design choice.
  19. Apply every rate and fidelity endpoint to an eight-wide design with ROB at least 600.
  20. Apply them separately to a ten-wide design with ROB at least 1000.
  21. Require scheduler capacity at least 256 entries in both wide designs.
  22. Require active memory and coherence contention in both wide designs.
  23. Use Section 3.4 sealed substitutes if needed.
  24. Never require a BOOM change.

<a id="D01c2"></a>

#### D01.c2: Generic adapters, functional execution and fabric accuracy on three unrelated cores
- Phases: Start work in P06. Accept this cell in P07.
- Must pass first: D01.c1 interface; functional expected transitions independently available, D27.c8.
- Baseline: Use independently available expected functional transitions.
- Summary: Test generic adapters, functional execution and fabric accuracy on three unrelated cores. Keep generic gem5 queue, port, replay and fabric hooks and C6 design-database adapters on three unrelated cores.
- Rule:
  1. Keep generic gem5 queue, port, replay and fabric hooks and C6 design-database adapters on three unrelated cores.
  2. Require zero core names in generic code.
  3. Require QEMU and Sail software-tier rate at least 20 million functional instructions per second.
  4. Check 100 legal, illegal and fault cases.
  5. Check 20 programs plus boot.
  6. Check 20 fabric points within 5% latency error and 10% bandwidth error.
  7. Functional rate does not qualify timing.

<a id="D01c3a"></a>

#### D01.c3a: Analytical and interval rates, intervention direction, fidelity, yield, cost and effort against qualified recipes
- Phases: Start work in P06. Accept this cell in P07.
- Must pass first: D01.c1, independent analytical equations, D27.c8.
- Baseline: Use the detailed tier for intervention direction and the strongest qualified analytical recipe for comparisons.
- Summary: Test analytical and interval rates, intervention direction, fidelity, yield, cost and effort against qualified recipes. Require at least 100 million modeled instructions per second per allocated host core.
- Rule:
  1. Implement an analytical and interval tier before the C6 design-database stage.
  2. Accept width, window, port and cache inputs.
  3. Require at least 100 million modeled instructions per second per allocated host core.
  4. Require at least 90% direction agreement versus the detailed tier on 20 fresh sweeps per parameter family.
  5. Publish errors and omitted effects.
  6. Compare fidelity and error against the strongest qualified analytical recipe under Section 3.1.
  7. Compare accepted-decision yield against that recipe.
  8. Compare total checked sweep cost against that recipe.
  9. Compare model construction hours and separate maintenance hours against that recipe.
  10. Seal analytical queueing and interval, trace-driven, and full-system candidate recipe classes on disjoint controls.
  11. Select within each applicable tier before confirmation.
  12. Require non-inferior results on all endpoints under Section 3.1.
  13. Require exact mandatory decision controls.
  14. Use canonical aggregate-rate in instructions per second.
  15. Use canonical normalized-rate in instructions per second per allocated host core.
  16. Use intervention-direction in probability units.
  17. Use fidelity-error-ratio in ratio units.
  18. Use accepted-decision-yield-difference in probability units.
  19. Use checked-sweep-cost-ratio, construction-hours-ratio and maintenance-hours-ratio in ratio units.
  20. Use mandatory-errors in count units.

<a id="D01c3b"></a>

#### D01.c3b: Shared-fabric many-hart rate, fidelity, yield, cost and effort at each required size
- Phases: Start work in P06. Accept this cell in P07.
- Must pass first: D01.c1, D12.c1, D35.c2a, D27.c8.
- Baseline: Use the strongest independently qualified full-system many-hart recipe.
- Summary: Test shared-fabric many-hart rate, fidelity, yield, cost and effort at each required size. Require 95th-percentile total-cycle error at most 7%.
- Rule:
  1. Implement shared-fabric many-hart tiers for 8, 16, 32 and 64 harts.
  2. At each size, require at least 100 thousand detailed modeled instructions per second per host core.
  3. Require 95th-percentile total-cycle error at most 7%.
  4. At 20 points per size, require contention-latency error at most 5%.
  5. At those points, require bandwidth error at most 10%.
  6. Measure rate and fidelity at the same point.
  7. Raise rates from D35.c2a demand.
  8. Keep these minimums.
  9. At each size, compare fidelity against the strongest independently qualified full-system and many-hart recipe under Section 3.1.
  10. Compare accepted-decision yield against that recipe.
  11. Compare checked sweep cost against that recipe.
  12. Compare construction hours and separate maintenance hours against that recipe.
  13. Seal gem5 detailed, interval and analytical, and trace-driven candidate classes before disjoint selection.
  14. Seal observation facilities before disjoint selection.
  15. Keep missing qualified comparisons OPEN.
  16. Use modeled-rate in instructions per second per host core.
  17. Use cycle-error, contention-error and bandwidth-error in fraction units.
  18. Use cycle-error-ratio, contention-error-ratio and bandwidth-error-ratio in ratio units.
  19. Use accepted-decision-yield-difference in probability units.
  20. Use checked-sweep-cost-ratio, construction-hours-ratio and maintenance-hours-ratio in ratio units.
  21. Use mandatory-errors in count units.

<a id="D01c4"></a>

#### D01.c4: Calibration effort and transfer accuracy on unseen configurations and both wide strata
- Phases: Start work in P07. Accept this cell in P07.
- Must pass first: D30.c3; independent RTL anchors, D27.c8. D01.c1 runtime receipt.
- Baseline: Use independent RTL anchors.
- Summary: Test calibration effort and transfer accuracy on unseen configurations and both wide strata. Require independent checkers to reach initial calibration in at most 2 weeks of scripted execution.
- Rule:
  1. Use three unseen configurations, including a hidden mechanism.
  2. Require independent checkers to reach initial calibration in at most 2 weeks of scripted execution.
  3. Before initial fitting and before refitting in each wide stratum, keep fresh-phase median cycle error at most 5%.
  4. Before initial fitting and before refitting in each wide stratum, keep fresh-phase 95th-percentile cycle error at most 10%.
  5. After fitting, apply ordinary D01.c1 limits.
  6. Permit no generic model edits.
  7. Count explicit abstentions.
  8. In both wide strata, seal calibration on six-wide designs only before extrapolation.
  9. Before refitting, require correct intervention-direction lower bound at least .90.
  10. After refitting, apply all D01.c1 bounds.
  11. Include wrong-window controls.
  12. Include issue-bandwidth controls.

<a id="D01c5"></a>

#### D01.c5: Exact rare events and bounded estimated-count errors before decision advice
- Phases: Start work in P06. Accept this cell in P07.
- Must pass first: D01.c1, D27.c8.
- Baseline: Use the D01.c1 baseline for error comparison.
- Summary: Test exact rare events and bounded estimated-count errors before decision advice. Require absolute estimated-minus-reference count error times S at most the preregistered smallest useful effect in the endpoint units divided by 4.
- Rule:
  1. Require exact occurrence, count and order for deterministic rare replay, recovery, fault and ordering events.
  2. Use at least 50 independent controls per event, including zero and one occurrences.
  3. For estimated counts, freeze sensitivity bound S from independent interventions.
  4. Require absolute estimated-minus-reference count error times S at most the preregistered smallest useful effect in the endpoint units divided by 4.
  5. When the reference count is at least 100, also require absolute estimated-minus-reference count error at most 1% of that count.
  6. Below 100, require exact counts or a reported conservative integer interval.
  7. Require that interval's full propagated decision error at most the preregistered smallest useful effect in the endpoint units divided by 4.
  8. Require 20 count-cancellation and rare-event-erasure controls to refuse advice.
  9. Compare error with the D01.c1 baseline using a ratio at most 1.02 plus the absolute budget.
  10. Express S in endpoint units per event.
  11. Require S to bound the absolute response to each event-count error.
  12. Reject 20 unit-rescaling controls whose decision changes when cycles become seconds.
  13. Reject 20 controls that pass only the count bound.
  14. Reject 20 controls that pass only the propagated decision bound.

<a id="D01c6"></a>

#### D01.c6: Predictor and prefetch component-trace fidelity, cost and invalid-trace detection against independent anchors and qualified recipes
- Phases: Start work in P06. Accept this cell in P07.
- Must pass first: D01.c1, D21.c1, D27.c8.
- Baseline: Use independent full RTL anchors, detailed D01.c1 and qualified ChampSim for their specified comparisons.
- Summary: Test predictor and prefetch component-trace fidelity, cost and invalid-trace detection against independent anchors and qualified recipes. Require non-inferior error ratio at most 1.02 versus ChampSim.
- Rule:
  1. Implement a ChampSim and CBP-class component-trace tier for predictors and prefetchers.
  2. Use standard traces with full-input trace provenance.
  3. Use at least 20 held-out interventions per mechanism and three generations against independent full RTL anchors.
  4. Require direction lower bound at least .95.
  5. Require MPKI absolute error at most .1.
  6. Above MPKI 5, also require relative error at most 2%.
  7. Compare total checked sweep cost with detailed D01.c1 and qualified ChampSim under Section 3.1.
  8. Require upper cost ratio at most .90 versus the detailed tier.
  9. Require non-inferior error ratio at most 1.02 versus ChampSim.
  10. Detect all reordered, truncated and wrong-path-loss controls.
  11. No component-only result may claim full-core timing.

<a id="D01c90"></a>

#### D01.c90: Every issue-specific obligation in D01.c90 with its required exact evidence, comparisons and refusal controls
- Phases: Start work in P06. Accept this cell in P07.
- Must pass first: D01.c1, D27.c2, D27.c8.
- Baseline: Use the independent policies, traces and full RTL anchors and qualified ChampSim, CBP, gem5 and Scarab-class recipes specified below.
- Summary: Test every issue-specific obligation in D01.c90 with its required exact evidence, comparisons and refusal controls. For each timing-qualified mechanism, require median cycle error at most 3%.
- Rule:
  1. Apply I90, the source-specific issue-child evidence protocol, to every issue below.
  2. For issue #12, fit synthetic known parameters.
  3. Recover held-out predictions.
  4. For issue #13, run independently checked RV32 and in-order configurations under R04 (independent requirement-derived expectations with distinct authors and recorded ancestry).
  5. For issue #72, activate every declared wide-model mechanism.
  6. Reject idealized omissions.
  7. For issue #124, round-trip cache and fabric topology with exact endpoint identity.
  8. For issue #125, reconcile per-link traffic and latency against independent probes.
  9. For issue #160, replay sealed sweeps with all rejected alternatives and immutable provenance.
  10. For issue #365, specify explicit prefetch and replacement policies.
  11. Include bandwidth, pollution, coverage, timeliness and competing traffic.
  12. Use 50 independent state-transition controls per policy.
  13. Use 20 held-out intervention anchors.
  14. Require direction lower bound at least .95.
  15. Require MPKI absolute error at most .1.
  16. Above 5, require MPKI relative error at most 2%.
  17. Require median cycle errors at most 3%.
  18. Require 95th-percentile cycle errors at most 7%.
  19. Compare ChampSim and detailed gem5 at matched fidelity.
  20. Require wrong-path and trace-loss controls to refuse.
  21. For issue #360, match direct, indirect, call and return classification and actual targets to an independent trace reference exactly.
  22. Use at least 50 controls per BTB and RAS overflow, underflow, alias, compressed and context-state family.
  23. Use 20 held-out traces.
  24. Report target MPKI separately from direction.
  25. Require independent RTL anchors for timing claims.
  26. For timing claims, require component MPKI absolute error at most .1.
  27. For timing claims above MPKI 5, require relative error at most 2%.
  28. For timing claims, require direction lower bound at least .95.
  29. For issue #359, specify a generic micro-operation-cache contract for lookup, fill, bandwidth, capacity, replacement and hit latency.
  30. Specify fence.i, context and coherence invalidation.
  31. Specify compressed, block and redirect handling.
  32. Use 50 independent hit, miss, invalidation and boundary controls per family.
  33. Require exact agreement against an independent policy.
  34. Require identical ELF, retirements and complete exits.
  35. Use 20 held-out independent RTL interventions.
  36. Require direction lower bound at least .95.
  37. Require median cycle errors at most 3%.
  38. Require 95th-percentile cycle errors at most 7%.
  39. Compare cost and error with a Scarab-class trace recipe under Section 3.1.
  40. Draft an upstream patch.
  41. Keep tuning in the project only.
  42. For issue #358, bind optional direction and target RTL events to source, ELF, hart, region of interest, ordinal and unit.
  43. Use at least 50 known mismatch, missing, speculation and alignment controls to reject false agreement.
  44. Require at least one native existing-target comparison.
  45. Keep exact observed direction and target counts separate from inferred retirement.
  46. Also require component MPKI and held-out anchor gates for timing-qualified claims.
  47. For issue #357, specify explicit multilevel BTB capacities, latencies, replacement and update.
  48. Specify bounded FTQ prefetch outstanding queues.
  49. Use 50 independent squash, stale, translation-fault and retry controls per family.
  50. Preserve exact transactions.
  51. Report footprint change in intervention trials with identical ELF and complete exit.
  52. For timing-qualified output, use 20 held-out full RTL anchors.
  53. For timing-qualified output, require direction lower bound at least .95.
  54. For timing-qualified output, require median cycle error at most 3%.
  55. For timing-qualified output, require 95th-percentile cycle error at most 7%.
  56. Native gem5 behavior alone earns no RTL fidelity.
  57. For issue #356, seal source, configuration, fit, split, event-map, ELF and C2 prediction hashes before RTL scores.
  58. Use at least three native repeats per held-out workload.
  59. Include C2 parsing.
  60. Require model speed at least 50 times warmed RTL speed at the same initial 10% IPC and 15% event limits.
  61. Charge startup, build and capture separately.
  62. Keep fresh held-out confirmation and final parent accuracy and comparison gates required.
  63. Require stale and split-overlap controls to refuse.
  64. Share the ledger between cancellable CLI and MCP.
  65. For issue #355, use dependency, independent ALU, pointer-chase, independent-load and branch controls.
  66. Use at least 5 held-out workloads by 3 event families on an existing small OoO target.
  67. Seal ELF and trace split and physical event-sampling map.
  68. Require complete exact C1 run-result and C2 trace identities.
  69. For the initial model, require IPC error at most 10%.
  70. Require nonzero-event error at most 15%.
  71. Keep tighter final parent bounds required.
  72. Use correlation only with at least 3 nonconstant samples.
  73. Make zero and missing events explicit.
  74. For issue #354, export source-bound effective fetch, issue, ROB, LSQ, FU, predictor, cache and TLB configuration fields and extraction keys.
  75. Round-trip every modeled field exactly.
  76. Require 20 width, queue, predictor, cache and unsupported-structure mutants to refuse.
  77. Declare wrong-path limits in branch and cache timing modules.
  78. Keep those limits in project data.
  79. Require no core-source repair prerequisite.
  80. For issue #351, pin an independent CBP TAGE-SC-L revision and storage.
  81. Require per-branch prediction and state to match on allocation, useful aging, loop confidence and SC override.
  82. Use at least 50 controls per family.
  83. Use 20 held-out traces.
  84. Record every approximation in BOOM-like project settings.
  85. Require exact reference MPKI, warmup, reset and oracle bound.
  86. Additionally require component-anchor bounds for RTL claims, never reference-trace agreement alone.
  87. For every timing-qualified mechanism above, additionally use 20 held-out independent full RTL interventions across three generations.
  88. For each such timing-qualified mechanism, require median cycle error at most 3%.
  89. For each such timing-qualified mechanism, require 95th-percentile cycle error at most 7%.
  90. For each such timing-qualified mechanism, require direction lower bound at least .95.
  91. Component-only MPKI reference checks do not imply whole-core timing.
  92. Qualify ChampSim and CBP and Scarab-class candidate recipes on disjoint controls.
  93. Apply I90.

<a id="D01c7"></a>

#### D01.c7: Complete machine descriptions, divergence localization and exact speculative store-byte versioning
- Phases: Start work in P06. Accept this cell in P07.
- Must pass first: D01.c1, D05.c1, D27.c8.
- Baseline: Use the independent D05.c1 structure inventory.
- Summary: Test complete machine descriptions, divergence localization and exact speculative store-byte versioning. Require zero false locations.
- Rule:
  1. Provide a versioned machine-description schema for micro-operations, queue and port counts, latency, arbitration, speculation, replay and memory topology.
  2. Specify units and supported ranges.
  3. Round-trip every declared field against the independent D05.c1 structure inventory on three core lineages.
  4. Permit no silent defaults.
  5. Use at least 20 wrong-size, wrong-port and wrong-latency mutants per structure type.
  6. Reject these mutants or mark them unconstrained.
  7. Locate the exact first instruction or event divergence for 100 seeded timing faults with the model-RTL checker.
  8. Require zero false locations.
  9. Require 95th-percentile localization at most 60 s after event ingestion at 1 million instructions per second.
  10. Implement memory-renaming MR1 (#362 and #72) as speculative exact-byte store-value versioning.
  11. Keep it distinct from store sets and ordinary address forwarding.
  12. Allocate a version per store byte at dispatch.
  13. Tag each version by thread, ROB age and speculation epoch.
  14. Unresolved address versions cannot supply data.
  15. At lookup, select the youngest older resolved same-thread version per byte.
  16. Retain load source and version information.
  17. Retain each load's unresolved-older-store dependency set.
  18. At address resolution, check all younger executed loads.
  19. Replay from the oldest affected load when an alias or source changes.
  20. Permit only same-thread younger speculative loads to see versions.
  21. Permit no other hart or device to see them before ordered retirement.
  22. Retire stores in order after permission and fault checks.
  23. Commit bytes to the architectural memory queue in RVWMO order.
  24. Release versions only after all readers retire or replay.
  25. On branch or exception rollback, drop younger epochs.
  26. Restore the prior map on rollback.
  27. Clear all versions on reset.
  28. Drain required order for fences, atomics and device accesses.
  29. Bypass this optimization for those accesses.
  30. Stall on resource exhaustion.
  31. Never overwrite a live version.
  32. Use generation tags for version reuse.
  33. Never create a value from unresolved partial overlap or faults.
  34. Mark alternative value-prediction, cross-thread-forwarding and logical-register interpretations UNSUPPORTED-MR1.
  35. They are not equivalent contracts.
  36. Implement these transitions in the model without silent defaults.
  37. Include allocation, lookup, alias, replay, retirement and recovery latency and capacity parameters.

<a id="D02c1"></a>

#### D02.c1: Model admission, direction, false gains and regret across sealed structural changes and interactions
- Phases: Start work in P06. Accept this cell in P07.
- Must pass first: D01.c1, D21.c1, D27.c8.
- Baseline: Use the baseline stated in the rule when a comparison applies.
- Summary: Test model admission, direction, false gains and regret across sealed structural changes and interactions. Require adjusted admission lower bound at least 0.80.
- Rule:
  1. Seal 20 changes each for predictor, issue, memory and hierarchy.
  2. Seal 20 combined changes.
  3. Use three structure distances.
  4. Include one hidden interacting mechanism.
  5. Include SMT, prefetch and fabric cases.
  6. For the interval pilot, use at least 100 independent design and workload clusters per mechanism by distance by generation.
  7. Require adjusted admission lower bound at least 0.80.
  8. Require direction lower bound at least 0.90.
  9. Require false-gain upper bound at most 0.05.
  10. Require regret below the preregistered smallest useful effect in the endpoint units.

<a id="D04c90"></a>

#### D04.c90: Every issue-specific obligation in D04.c90 with its required exact evidence, comparisons and refusal controls
- Phases: Start work in P06. Accept this cell in P06.
- Must pass first: D04.c1, D27.c2, D27.c8.
- Baseline: Use the baseline stated in the rule when a comparison applies.
- Summary: Test every issue-specific obligation in D04.c90 with its required exact evidence, comparisons and refusal controls. Require all 5 numbered rule items.
- Rule:
  1. Apply I90, the source-specific issue-child evidence protocol.
  2. For issue #4, archive independent review of metric definitions and stored-folder gate predicates.
  3. Reproduce every identified defect.
  4. Verify each correction without unresolved false-pass findings.
  5. Apply I90 to this issue child.

<a id="D04c5"></a>

#### D04.c5: Event-set observability and discriminating proposals without magnitude claims from rank-only evidence
- Phases: Start work in P06. Accept this cell in P06.
- Must pass first: D04.c2, D03.c4, D27.c8.
- Baseline: Use the baseline stated in the rule when a comparison applies.
- Summary: Test event-set observability and discriminating proposals without magnitude claims from rank-only evidence. Require zero magnitude claims from rank-only data.
- Rule:
  1. For each leaf in the explanatory context in D03.c4, classify observability under a proposed HPM set.
  2. Report EXACT, CALIBRATED-APPROXIMATE or unobservable.
  3. Provide a minimal discriminating event proposal with bias, uncertainty and cost.
  4. Use at least 100 aliased, missing and sufficient event-set cases independently specified under R04 (independent requirement-derived expectations with distinct authors and recorded ancestry) across three lineages.
  5. Require exact coverage classifications.
  6. Require zero magnitude claims from rank-only data.

<a id="D05c2c"></a>

#### D05.c2c: Navigation, completion and scripted checked time against each applicable editor baseline
- Phases: Start work in P07. Accept this cell in P07.
- Must pass first: D05.c1, D29.c1, D29.c2; scripted runners, D27.c8, the explanatory context in D06.c4, the explanatory context in D05.c2a.
- Baseline: Use every applicable baseline from the D05.c2a interface contract.
- Summary: Test the machine capability and exact correctness of navigation, completion and scripted checked time against each applicable editor baseline. Require zero wrong accepted results.
- Rule:
  1. Keep D05.c1 navigation deadlines for projects in the interface contract from D05.c2a.
  2. Compare correct completion with sampled margin .005 against every applicable D05.c2a interface baseline.
  3. Compare navigation time with margin 1.02 against each baseline.
  4. Compare total scripted checked time with margin 1.15 against each baseline.
  5. Compare tails with margin 1.20 against each baseline.
  6. Record task-specific effort and tail-budget justification.
  7. Require the D06.c4 receipt before the stronger productivity claim.
  8. The navigation receipt alone cannot close productivity.

<a id="D05c3"></a>

#### D05.c3: Generator-debugger correctness and repair effort against complete qualified native debugging flows
- Phases: Start work in P07. Accept this cell in P07.
- Must pass first: D05.c1, D29.c1, D29.c2; independent generator failures, D27.c8, D05.c6.
- Baseline: Use the strongest complete qualified IntelliJ JVM debugger and VS Code Java debugger native flow as specified below.
- Summary: Test generator-debugger correctness and repair effort against complete qualified native debugging flows. Require zero stale nodes.
- Rule:
  1. Provide a Spinal and Chisel elaboration debugger with component, Area and conditional breakpoints.
  2. Provide stepping, parameters, partial hardware, parent, child, type and connection views with exact source.
  3. Use 30 sealed failure and repair tasks per language.
  4. Require exact context answers.
  5. Require zero stale nodes.
  6. Require break-to-context 95th-percentile at most 2 s.
  7. Require at least 90% verified fixes.
  8. Share stopped context across CLI and MCP.
  9. Compare complete repair effort under Section 3.1 against the fixed native comparator frame.
  10. Use Spinal and Chisel on IntelliJ JVM debugger and VS Code Java debugger.
  11. Pin JDK, Scala and build versions.
  12. Require both comparators to answer stopped-parameter, partially constructed hardware, parent, child, type and connection questions.
  13. Seal at least 10 disjoint qualifying controls for each facility and failure class.
  14. Include parameter, naming, connection, conditional, width and ordering failure classes.
  15. Select the strongest complete native flow before repair-task reveal.
  16. Include setup, instrumentation, restart and failed fixes.
  17. Keep unsupported facilities as denominator holes.
  18. A weak baseline cannot qualify.
  19. Require secondary verified scripted checked-time upper ratio at most .90.
  20. Keep other comparison endpoints non-inferior.
  21. Require the semantic-index, language-server and elaboration-debug method decision in the method designs in protocols.md before this runtime result can close.

<a id="D07c12"></a>

#### D07.c12: Constraint legality, randomized distributions and deterministic replay with independently validated solutions
- Phases: Start work in P06. Accept this cell in P06.
- Must pass first: D07.c11, D27.c8.
- Baseline: Use the baseline stated in the rule when a comparison applies.
- Summary: Test constraint legality, randomized distributions and deterministic replay with independently validated solutions. Use at least 50 legal, UNSAT and invalid controls per family.
- Rule:
  1. Implement a constraint solver and randomized distributions with seed, state and replay.
  2. Cover every relevant IEEE construct.
  3. Use at least 50 legal, UNSAT and invalid controls per family.
  4. Independently validate solutions.
  5. Use predeclared distribution tests.
  6. Accept no illegal solution.

<a id="D07c13"></a>

#### D07.c13: Coverage-bin and assertion semantics with exact counts and event-region ordering
- Phases: Start work in P07. Accept this cell in P07.
- Must pass first: D07.c12, D27.c8.
- Baseline: Use the baseline stated in the rule when a comparison applies.
- Summary: Test coverage-bin and assertion semantics with exact counts and event-region ordering. Use at least 50 independent controls per family.
- Rule:
  1. Implement covergroup, cross, transition, illegal and ignore bins.
  2. Implement simulation SVA sampled, local, multiclock, strong and weak semantics.
  3. Use at least 50 independent controls per family.
  4. Require exact hit, abort and fail counts.
  5. Require exact region order.

<a id="D14c6"></a>

#### D14.c6: Check cross-unit temporal coverage and scripted checked time
- Phases: Start work in P06. Accept this cell in P06.
- Must pass first: D14.c1, D14.c2, D27.c8.
- Baseline: Tuned UVM, Breker and STING.
- Summary: Test the correctness of cross-unit temporal coverage and scripted checked time. Require an upper noninferiority allocated core-hours ratio at most 1.15.
- Rule:
  1. Create an independent cross-unit temporal hazard inventory.
  2. Include ROB full, issue starvation, replay, TLB miss, branch recovery, cache miss, IRQ, DMA and coherence.
  3. Include every pair.
  4. Include every specification-mandated or dependency-connected triple.
  5. Independently enumerate exact tuple counts before implementation.
  6. Publish reachable, unreachable and unknown totals and witnesses.
  7. Exercise concurrent overlap for each reachable tuple.
  8. Exercise each order permutation for each reachable tuple.
  9. Exercise reset cancellation for each reachable tuple.
  10. Allow no mandatory hole to close by timeout.
  11. Compare authoring and maintenance against tuned UVM and Breker and STING.
  12. Require an upper noninferiority allocated core-hours ratio at most 1.15.
  13. Require the secondary upper ratio at most .90 for verified bin updates.
  14. Keep exact semantics mandatory.

<a id="D14c9"></a>

#### D14.c9: Select and qualify the coverage closure method
- Phases: Start work in P06. Accept this cell in P06.
- Must pass first: D14.c1, D14.c2, D27.c8, D10.c1.
- Baseline: Coverage-directed SAT and SMT, contextual bandit, LLM-directed and hardware-state-feedback candidates.
- Summary: Test coverage-method selection and independent ISA legality. For each required stratum, detect every activated omission and solve every legal goal. Use at least 50 of each, or 10 times the hazard-family count when larger.
- Rule:
  1. Select the coverage closure method CC27.
  2. Compare coverage-directed SAT and SMT, contextual bandit, LLM-directed and hardware-state-feedback candidates on disjoint controls with equal training and tuning.
  3. Freeze the winner by checked closure time, legality and total cost before confirmation.
  4. Require zero false closure.
  5. After two failed improvements, redirect to constraint decomposition with a checked queue of unsolved goals.
  6. Do not close an unreachable bin without proof.
  7. Before using the coverage planner on any ISA family, require that family legality relation and all its option partitions from D10.c1.
  8. Independently test held-out legal, illegal and omitted-state cases at the original family control floors.
  9. Every omitted legality clause must fail qualification.
  10. Require that planner benefit cannot qualify its own legality checker.
  11. For each width, SMT, coherence, ISA-option and shared-resource stratum, require at least 50 activated omissions and 50 legal goals.
  12. Detect every activated omission in each stratum.
  13. Solve every legal goal in each stratum.
  14. Increase both counts to at least 10 times the independently enumerated hazard-family count in that stratum when larger.
  15. Cover every hazard family and mandated higher-order interaction at least once.
  16. Keep the full source and hazard census as the denominator.

<a id="D15c90"></a>

#### D15.c90: Check source-specific formal issue mappings
- Phases: Start work in P07. Accept this cell in P07.
- Must pass first: D15.c1, D27.c2, D27.c8.
- Baseline: Use the baseline stated in the rule when a comparison applies.
- Summary: Test the correctness of source-specific formal issue mappings. For #67, require that X optimism and pessimism controls follow declared four-state semantics.
- Rule:
  1. Apply I90, the source-specific issue protocol, to these issue requirements: #18 sequential relations include reset, retiming and memory.
  2. For #19, require that datapath equivalence covers rounding and NaN and flags versus independently checked under the independence protocol R04 C.
  3. For #20, require that information flow separates confidentiality and integrity.
  4. For #21, require that deep positive proofs retain induction and nonvacuity.
  5. For #60, require that CEX visualization and what-if replay preserve original-state identity.
  6. For #61, require that full SVA lowering preserves infinite-trace and fairness semantics.
  7. For #63, require that generic riscv-formal harness has no BOOM names and detects interface mutants.
  8. For #67, require that X optimism and pessimism controls follow declared four-state semantics.
  9. For #107, prove all declared connectivity paths with guards and forbidden paths.
  10. For #117, require that shared runner preserves status, timeout, certificate and failure logs for each caller.
  11. For #142, require that concurrent device transactions preserve W1C and read-clear and alias and byte-enable and reset ordering and partial effects.
  12. For #294, require that all mandatory application, grid, swarm and both vendor proof comparisons stay required.
  13. Apply the complete I90 protocol.
  14. This P07 receipt checks issue-to-obligation mapping only.
  15. It cannot close #294 proof-grid, reachable-state-swarm or vendor comparisons.
  16. Those receipts close only at their defining later cells.

<a id="D15c7p1"></a>

#### D15.c7p1: Compare the connectivity application
- Phases: Start work in P06. Accept this cell in P06.
- Must pass first: D15.c2p1, D15.c4, D27.c8.
- Baseline: JasperGold and VC Formal under the complete FC comparison protocol.
- Summary: Test the comparison of the connectivity application. For final application 1 comparison, apply FC, the formal-application comparison protocol in section 3.5, including all four metric children and both comparators.
- Rule:
  1. Require connectivity application.
  2. For final application 1 comparison, apply FC, the formal-application comparison protocol in section 3.5, including all four metric children and both comparators.
  3. Retain every unknown and positive proof.

<a id="D15c7p2"></a>

#### D15.c7p2: Compare the register application
- Phases: Start work in P06. Accept this cell in P06.
- Must pass first: D15.c2p2, D15.c4, D27.c8.
- Baseline: JasperGold and VC Formal under the complete FC comparison protocol.
- Summary: Test the comparison of the register application. For final application 2 comparison, apply FC, the formal-application comparison protocol in section 3.5, including all four metric children and both comparators.
- Rule:
  1. Compare the CSR application.
  2. For final application 2 comparison, apply FC, the formal-application comparison protocol in section 3.5, including all four metric children and both comparators.
  3. Retain every unknown and positive proof.

<a id="D15c7p3"></a>

#### D15.c7p3: Compare the X propagation application
- Phases: Start work in P06. Accept this cell in P06.
- Must pass first: D15.c2p3, D15.c4, D27.c8.
- Baseline: JasperGold and VC Formal under the complete FC comparison protocol.
- Summary: Test the comparison of the X propagation application. For final application 3 comparison, apply FC, the formal-application comparison protocol in section 3.5, including all four metric children and both comparators.
- Rule:
  1. Compare the X propagation application.
  2. For final application 3 comparison, apply FC, the formal-application comparison protocol in section 3.5, including all four metric children and both comparators.
  3. Retain every unknown and positive proof.

<a id="D15c7p4"></a>

#### D15.c7p4: Compare the equivalence application
- Phases: Start work in P06. Accept this cell in P06.
- Must pass first: D15.c2p4, D15.c4, D27.c8.
- Baseline: JasperGold and VC Formal under the complete FC comparison protocol.
- Summary: Test the comparison of the equivalence application. For final application 4 comparison, apply FC, the formal-application comparison protocol in section 3.5, including all four metric children and both comparators.
- Rule:
  1. Compare the SEC application.
  2. For final application 4 comparison, apply FC, the formal-application comparison protocol in section 3.5, including all four metric children and both comparators.
  3. Retain every unknown and positive proof.

<a id="D15c7p5"></a>

#### D15.c7p5: Compare the liveness application
- Phases: Start work in P06. Accept this cell in P06.
- Must pass first: D15.c2p5, D15.c4, D27.c8.
- Baseline: JasperGold and VC Formal under the complete FC comparison protocol.
- Summary: Test the comparison of the liveness application. For final application 5 comparison, apply FC, the formal-application comparison protocol in section 3.5, including all four metric children and both comparators.
- Rule:
  1. Require liveness application.
  2. For final application 5 comparison, apply FC, the formal-application comparison protocol in section 3.5, including all four metric children and both comparators.
  3. Retain every unknown and positive proof.

<a id="D15c7p6"></a>

#### D15.c7p6: Compare the security application
- Phases: Start work in P06. Accept this cell in P06.
- Must pass first: D15.c2p6, D15.c4, D27.c8.
- Baseline: JasperGold and VC Formal under the complete FC comparison protocol.
- Summary: Test the comparison of the security application. For final application 6 comparison, apply FC, the formal-application comparison protocol in section 3.5, including all four metric children and both comparators.
- Rule:
  1. Require security application.
  2. For final application 6 comparison, apply FC, the formal-application comparison protocol in section 3.5, including all four metric children and both comparators.
  3. Retain every unknown and positive proof.

<a id="D15c7p7"></a>

#### D15.c7p7: Compare the proof coverage application
- Phases: Start work in P06. Accept this cell in P06.
- Must pass first: D15.c2p7, D15.c4, D27.c8.
- Baseline: JasperGold and VC Formal under the complete FC comparison protocol.
- Summary: Test the comparison of the proof coverage application. For final application 7 comparison, apply FC, the formal-application comparison protocol in section 3.5, including all four metric children and both comparators.
- Rule:
  1. Require proof coverage and cores application.
  2. For final application 7 comparison, apply FC, the formal-application comparison protocol in section 3.5, including all four metric children and both comparators.
  3. Retain every unknown and positive proof.

<a id="D15c7p8"></a>

#### D15.c7p8: Compare the mutation application
- Phases: Start work in P06. Accept this cell in P06.
- Must pass first: D15.c2p8, D15.c4, D27.c8.
- Baseline: JasperGold and VC Formal under the complete FC comparison protocol.
- Summary: Test the comparison of the mutation application. For final application 8 comparison, apply FC, the formal-application comparison protocol in section 3.5, including all four metric children and both comparators.
- Rule:
  1. Require mutation application.
  2. For final application 8 comparison, apply FC, the formal-application comparison protocol in section 3.5, including all four metric children and both comparators.
  3. Retain every unknown and positive proof.

<a id="D15c7p9"></a>

#### D15.c7p9: Compare the unreachability application
- Phases: Start work in P06. Accept this cell in P06.
- Must pass first: D15.c2p9, D15.c4, D27.c8.
- Baseline: JasperGold and VC Formal under the complete FC comparison protocol.
- Summary: Test the comparison of the unreachability application. For final application 9 comparison, apply FC, the formal-application comparison protocol in section 3.5, including all four metric children and both comparators.
- Rule:
  1. Require unreachability application.
  2. For final application 9 comparison, apply FC, the formal-application comparison protocol in section 3.5, including all four metric children and both comparators.
  3. Retain every unknown and positive proof.

<a id="D15c8"></a>

#### D15.c8: Compare counterexample diagnosis and replay
- Phases: Start work in P07. Accept this cell in P07.
- Must pass first: D15.c4, D18.c1, D27.c8.
- Baseline: Jasper Visualize and Verdi.
- Summary: Test the comparison of counterexample diagnosis and replay. Require zero false repairs.
- Rule:
  1. Compare counterexample debug against Jasper Visualize AND Verdi.
  2. Replay the original RTL.
  3. Minimize under frozen temporal, input and state deletion operators.
  4. Check 1-minimality independently.
  5. Modify only declared interventions in a what-if run.
  6. Use exact suffixes independently expected under R04, the independence protocol.
  7. Label instrumented designs clearly.
  8. Use at least 100 independent real and seeded root causes.
  9. Require exact fault locations.
  10. Require zero false repairs.
  11. Require the secondary verified scripted checked-time upper ratio at most .90.
  12. Require a checked-time noninferiority ratio at most 1.02.
  13. Require a 95th-percentile effort ratio at most 1.20.
  14. Require a 99th-percentile effort ratio at most 1.20.

<a id="D15c9"></a>

#### D15.c9: Qualify assertion synthesis
- Phases: Start work in P06. Accept this cell in P06.
- Must pass first: D15.c1, D15.c4, D27.c8.
- Baseline: Qualified JasperGold and VC Formal property-mining flows.
- Summary: Test the qualification of assertion synthesis. Use the statistical comparison in section 3.1 for verified useful assertions per allocated core-hours lower bound at least 1 divided by 1.05 versus qualified JasperGold AND VC Formal property-mining flows.
- Rule:
  1. Require assertion synthesis: seal independent true invariants and fresh bug classes.
  2. Require that mined assertions require initiation and consecution and nonvacuity certificates and no circular training assumptions.
  3. Require all false and vacuous controls rejected.
  4. Require held-out noncritical defect sensitivity lower bound at least .95.
  5. Use the statistical comparison in section 3.1 for verified useful assertions per allocated core-hours lower bound at least 1 divided by 1.05 versus qualified JasperGold AND VC Formal property-mining flows.
  6. Every assertion reports source, scope, assumptions and invalidation.

<a id="D15c7p10"></a>

#### D15.c7p10: Compare automatic structural formal checks
- Phases: Start work in P06. Accept this cell in P06.
- Must pass first: D15.c2p10, D15.c4, D27.c8.
- Baseline: JasperGold Superlint, VC Formal AutoChecks and applicable Questa Formal checks.
- Summary: Test the comparison of automatic structural formal checks. Require zero mandatory misses.
- Rule:
  1. Compare final structural automatic checks against JasperGold Superlint AND VC Formal AutoChecks AND applicable Questa Formal checks on the same independently enumerated structure and intent frame.
  2. Use the statistical comparison in section 3.1 for conclusive fraction, checked-result-time, construction hours and debug hours separately.
  3. Apply all section 3.1 margins.
  4. Require zero mandatory misses.
  5. Require positive proof controls.
  6. Keep unknown results open.
  7. Use noninferiority as a noninferiority label only.
  8. Do not infer vendor superiority from the formal application receipts.

<a id="D16c4"></a>

#### D16.c4: Maintain and transfer wide refinement proofs
- Phases: Start work in P06. Accept this cell in P06.
- Must pass first: D16.c3; independent target custody, D15.c4, D27.c8.
- Baseline: Use the D15.c4 comparators. Treat Siemens Questa Processor and OneSpin as one processor-formal product lineage. Compare Axiomise formalISA separately.
- Summary: Test proof maintenance, transfer to independent wide lineages and all required comparisons. Require at least one held-out independently authored under the independence protocol R04 RTL or separately authored generator without shared template and scaffolding.
- Rule:
  1. Maintain the complete proof through three sealed structural generations.
  2. Construct and maintain proofs on two other wide lineages at equal scripted tuning budgets.
  3. Require at least one held-out independently authored under the independence protocol R04 RTL or separately authored generator without shared template and scaffolding.
  4. Require at least 4 structurally different organizations including LSU and recovery.
  5. Use the same geometry and complete proof obligations.
  6. Use the statistical comparison in section 3.1 for construction and maintenance effort and checked results versus D15.c4 comparators.
  7. Label generated ancestry.
  8. Missing independent proof stays open.
  9. Include the Siemens Questa Processor and OneSpin product lineage as a required processor-formal comparator.
  10. Include Axiomise formalISA as a separate required comparator.
  11. Use the same state relations, assumptions and proof budgets.
  12. Apply all time, capacity and effort endpoints and exact positive proofs.
  13. Treat Siemens Questa Processor and OneSpin as one named processor-formal product lineage.
  14. Compare Axiomise formalISA separately.

<a id="D16c6"></a>

#### D16.c6: Prove and maintain natural whole-core refinement
- Phases: Start work in P07. Accept this cell in P07.
- Must pass first: D16.c3, D16.c4, D15.c4, D27.c8.
- Baseline: Use the baseline stated in the rule when a comparison applies.
- Summary: Test proof and maintenance of natural whole-core refinement. Require proof maintenance at most 40 active allocated core-hours per RTL revision.
- Rule:
  1. Require that natural whole-core refinement is REQUIRED for unqualified Formal Full: one natural target.
  2. Require at least 6 dispatch, at least 6 retire and at least 400 ROB.
  3. Record build, complete state and hard-feature activation in the census.
  4. Complete the same valid unbounded implementation-to-specification refinement as the whole-wide proof.
  5. Keep that proof across three sealed redesigns.
  6. Retain all original construction-effort gates.
  7. Retain all original maintenance gates.
  8. Retain all named AND-comparator gates.
  9. Treat a natural target with at least 4-wide geometry as an intermediate receipt only.
  10. Require that generated at least 512-ROB artifacts stay where stated but cannot close this natural child.
  11. Missing target or proof remains OPEN.
  12. Require at most 40 active allocated core-hours of proof maintenance per RTL revision for each of the three sealed redesigns.
  13. Include failed repairs and manual invariant updates in those hours.
  14. Require the original maintenance comparison ratio at most 1.15 against each applicable qualified comparator.

<a id="D17c4"></a>

#### D17.c4: Prove shared SMT ownership, ordering and progress
- Phases: Start work in P06. Accept this cell in P06.
- Must pass first: D17.c1, D17.c2; independent capable target, not BOOM work, D33.c1, D27.c8.
- Baseline: Qualified JasperGold-based ordering, coherence and ownership flows under RP03.
- Summary: Test proof of shared SMT ownership, ordering and progress. Require zero mandatory misses.
- Rule:
  1. Use actual SMT with at least 2 threads sharing frontend and shared and dynamic rename and free-list and issue and ROB and LSU and recovery.
  2. Exercise one thread’s flush, reset, IRQ and debug while the other has stores, misses and replay.
  3. Exercise every shared-resource transition.
  4. Run at least 100 scenarios.
  5. Activate at least 25 faults in each ownership, recovery, ordering and progress family.
  6. Require zero mandatory misses.
  7. Require a sensitivity lower bound at least 0.95 per family with power.
  8. Prove thread ownership, conservation, progress and microarchitectural happens-before.
  9. Check per-thread state and ordering independently.
  10. Require that separate harts do not qualify.
  11. First census open OoO RISC-V SMT targets.
  12. If absent, 3.4 supplies independently generated at least 2-thread OoO SMT RTL with genuine dynamic shared resources and simultaneous hard-feature activation.
  13. Require that all proofs and fault tests remain.
  14. Label the claim generated-SMT ownership, order and progress capability, not validation of an existing open SMT core.
  15. Require that D33.c1 consumes the same pinned contract, not a newly easier target.
  16. Apply RP03, the proof construction and two-revision maintenance comparison protocol, to every proof and control in this row.

<a id="D17c5"></a>

#### D17.c5: Prove instruction visibility
- Phases: Start work in P06. Accept this cell in P06.
- Must pass first: D17.c2, D12.c1, D27.c8.
- Baseline: Use the baseline stated in the rule when a comparison applies.
- Summary: Test proof of instruction visibility. Run at least 100 independent allowed and forbidden histories.
- Rule:
  1. For instruction visibility #103, check self-modifying code, local fence.i and remote instruction-sync protocols across I-cache and prefetch and speculation and translation.
  2. Run at least 100 independent allowed and forbidden histories.
  3. Run 20 stale-fetch and order mutants.
  4. Require exact independent fetch and retirement answers.
  5. Extend D17.c2 abstraction with instruction-fetch visibility.
  6. Require positive unbounded proof for each advertised integration.
  7. Make no assumption that a local fence.i flushes other harts.

<a id="D17c6"></a>

#### D17.c6: Prove Ztso ordering
- Phases: Start work in P06. Accept this cell in P06.
- Must pass first: D17.c2, D12.c1, D27.c8.
- Baseline: Use the baseline stated in the rule when a comparison applies.
- Summary: Test proof of Ztso ordering. Require zero wrong verdicts.
- Rule:
  1. For Ztso #184, pin TSO mode and the RVWMO boundary.
  2. Pin store-buffer forwarding, multi-copy visibility, mixed-mode harts, AMO and fence and device restrictions.
  3. Run at least 200 independent litmus tests with 1,000 schedules each.
  4. Use herd7 and independent exhaustive bounded truth.
  5. Require zero wrong verdicts.
  6. Require 20 dropped-order and mode mutants rejected.
  7. Prove admitted Ztso axioms via D17.c2 µhb mapping.
  8. Require that RVWMO proof alone cannot close Ztso.

<a id="D17c7"></a>

#### D17.c7: Prove shared translation invalidation
- Phases: Start work in P06. Accept this cell in P06.
- Must pass first: D17.c3, D10.c1, D27.c8.
- Baseline: Use the baseline stated in the rule when a comparison applies.
- Summary: Test proof of shared translation invalidation. For each 2-, 4- and 8-hart child, run at least 100 legal COATCheck-class histories.
- Rule:
  1. For shared TLB shootdown #145, check sfence.vma, hfence.gvma and hfence.vvma, ASID and VMID reuse, in-flight walks, page-table updates, remote IPI and ack, selective and global invalidation and DMA and IOTLB boundaries.
  2. For each 2-, 4- and 8-hart child, run at least 100 legal COATCheck-class histories.
  3. For each child, run 100 forbidden histories.
  4. Run 20 stale-walk and reordered-ack mutants.
  5. Require exact independent translation answers.
  6. Require positive inductive visibility and progress proof with OS protocol preconditions.
  7. Do not infer remote invalidation from a local sfence.

<a id="D17c11"></a>

#### D17.c11: Qualify natural SMT integration
- Phases: Start work in P07. Accept this cell in P07.
- Must pass first: D17.c4, D17.c13, D27.c8.
- Baseline: Use the baseline stated in the rule when a comparison applies.
- Summary: Test the qualification of natural SMT integration. Use a natural dynamically shared out-of-order SMT target with at least 2 live threads.
- Rule:
  1. Require natural SMT integration for unqualified SMT Full.
  2. Use a natural dynamically shared out-of-order SMT target with at least 2 live threads.
  3. Execute all SMT ownership, ordering, recovery, safety and progress obligations at each capacity point in S25, the shared SMT scale protocol.
  4. Run all activated-fault tests at each point.
  5. Do not close this cell with an interface-only or generated receipt.
  6. Require that small natural targets keep separate support tier.

<a id="D17c12"></a>

#### D17.c12: Qualify natural coherence integration
- Phases: Start work in P07. Accept this cell in P07.
- Must pass first: D17.c3, D17.c10, D27.c8.
- Baseline: Qualified JasperGold-based ordering, coherence and ownership flows under RP03.
- Summary: Test the qualification of natural coherence integration. Use a directory-coherent target with at least 8 requesters plus coherent DMA and IOMMU.
- Rule:
  1. Require natural coherence integration for unqualified coherence Full.
  2. Use a directory-coherent target with at least 8 requesters plus coherent DMA and IOMMU.
  3. Include private L1, banked L2 and shared LLC.
  4. Apply all original coherence transition and data and SWMR and deadlock and fair-progress proofs, abstraction checks, activated faults and RP03 compares.
  5. Record build, ancestry and hard-feature activation in the census.
  6. Require that generated or permission-only projection cannot close it.

<a id="D17c13"></a>

#### D17.c13: Prove SMT at each required scale
- Phases: Start work in P06. Accept this cell in P06.
- Must pass first: D17.c1, D15.c2, the sealed schema interface of D17.c4, D27.c8.
- Baseline: Use the baseline stated in the rule when a comparison applies.
- Summary: Test proof of SMT at each required scale. Require at least 6 dispatch slots, 6 retirement slots and 400 ROB entries.
- Rule:
  1. Apply S25, the shared SMT scale protocol, at each required dispatch, retirement and ROB geometry.
  2. Require at least 6 dispatch slots, 6 retirement slots and 400 ROB entries.
  3. Require at least 8 dispatch slots, 8 retirement slots and 600 ROB entries.
  4. Require at least 10 dispatch slots, 10 retirement slots and 1000 ROB entries.
  5. Run at least 2 simultaneously active threads.
  6. For T active threads, each thread must occupy at least 1 divided by twice T of the ROB capacity during the common occupancy window. Apply the full S25 scale protocol.
  7. Require combined occupancy at least 90% for at least 1000 cycles.
  8. Require issue and LSQ queue occupancy at least 75%.
  9. Require at least 32 outstanding misses, including at least 8 per thread.
  10. Exercise shared issue, PRF, cache, MSHR and LSQ contention and simultaneous recoveries.
  11. Run at least 50 valid and 50 activated fault controls per resource per geometry.
  12. Provide positive unbounded ownership, order, safety and progress proofs.
  13. Discharge fairness.
  14. Replay the original state.
  15. Keep all original SMT comparisons.
  16. Use counters to witness occupancy.
  17. Require that draining or a static ROB partition cannot pass the dynamic-sharing child.

<a id="D17c15"></a>

#### D17.c15: Qualify ordering proof-closure benefit
- Phases: Start work in P06. Accept this cell in P06.
- Must pass first: D17.c2, D17.c3, D17.c10, D17.c14, D27.c8.
- Baseline: Each independently qualified JasperGold-based ordering and coherence flow, including the pinned RTLCheck-style baseline.
- Summary: Test checked proof-closure-time upper ratio at most 0.90 against each qualified JasperGold ordering and coherence flow.
- Rule:
  1. Accept ordering benefit only against a qualified strong baseline with every proof and escape gate intact.
  2. Require D17.c2 unbounded RVWMO proofs, D17.c3 directory proofs and D17.c10 coherence method receipts.
  3. Seal at least 100 independent bugs per supported bug family before outcomes, including fairness, transient races and omitted map edges.
  4. Require zero false accepted proofs.
  5. Require no lost escapes against either comparator.
  6. Include failed proofs, map construction, review, repair and two revisions in time and effort.
  7. Require that all original noninferiority and unbounded proof gates remain mandatory.
  8. Map effort alone cannot close this primary.
  9. An independent ordering baseline implementation reproduces a pinned RTLCheck-style microarchitectural happens-before flow on JasperGold.
  10. Apply the shared baseline-strength rule, vendor-recommended setup and recorded configuration and baseline-strength controls.
  11. Select the strongest ordering baseline configuration on disjoint strength controls before confirmation.
  12. A weak or unqualified baseline cannot support superiority.
  13. Detect every sealed ordering, coherence and SMT-sharing bug exactly.
  14. Category 9 primary: Require checked proof-closure-time upper ratio at most 0.90 against each qualified JasperGold ordering and coherence flow.

<a id="D18c2"></a>

#### D18.c2: Qualify complete wave queries at both trace sizes
- Phases: Start work in P05. Accept this cell in P06.
- Must pass first: D18.c1; the independence protocol R04 oracles, D27.c8, D18.c11.
- Baseline: Verdi FSDB and KDB on identical complete 1 TB visibility and source data.
- Summary: Test the qualification of complete wave queries at both trace sizes. Require resident memory at most 4 GiB for those classes.
- Rule:
  1. Create eight query cells: point-value, bounded-signal-range, hierarchy-name-source, bounded-driver-cone, bounded-transaction, bounded-CEX-join, all-signal-predicate-scan and aggregate-transition-occupancy.
  2. Seal 10 queries per class per design at 100 GB and 1 TB.
  3. For the first six classes, require 95th-percentile latency at most 5 s at 100 GB.
  4. For those classes, require 95th-percentile latency at most 30 s at 1 TB.
  5. Require resident memory at most 4 GiB for those classes.
  6. Require scans at most 60 s at 100 GB.
  7. Require scans at most 600 s at 1 TB.
  8. Return exact complete streamed results.
  9. Require index time at most 2 times sequential decode time.
  10. Report cold and warm timings, cache bytes and index bytes.
  11. Raise speed floors from the demand census.
  12. Retain the minima.
  13. Use section 3.1 statistical comparisons for each query class latency and resident memory against Verdi FSDB and KDB.
  14. Use identical complete 1 TB visibility and source data.
  15. Use margins of 1.02.
  16. Retain every failed or unsupported query.

<a id="D18c5"></a>

#### D18.c5: Check transaction debug joins
- Phases: Start work in P06. Accept this cell in P07.
- Must pass first: D18.c2, D37.c2, D27.c8.
- Baseline: Verdi.
- Summary: Test the correctness of transaction debug joins. Require at least 100 checked episodes per protocol against H05.011 through H05.013 in Verdi Protocol Analyzer and H22.001 in Verisium Debug.
- Rule:
  1. Require transaction debug on APB and AXI and TileLink and CHI and DMA and IRQ traces: at least 100 independent request-response and retry and reset and ordering episodes per protocol.
  2. Require exact complete joins and independent causal endpoints.
  3. Require zero orphan or invented links.
  4. Require 95th-percentile transaction-to-source and wave navigation at most 1 s at 100 GB.
  5. Require that latency at most 5 s at 1 TB.
  6. Compare query time against Verdi under section 3.1 with a ratio at most 1.02.
  7. Require exact common-scope identities.
  8. Compare H05.011, H05.012 and H05.013 against Verdi Protocol Analyzer transaction, source and performance joins.
  9. Compare the transaction portion of H22.001 against Verisium Debug on the same checked tasks.

<a id="D18c7"></a>

#### D18.c7: Qualify structural debug at one million signals
- Phases: Start work in P06. Accept this cell in P06.
- Must pass first: D18.c1, D05.c1, D27.c8.
- Baseline: Verdi nSchema and nTrace.
- Summary: Test the qualification of structural debug at one million signals. Require cold structural-answer time at most 5 s.
- Rule:
  1. At a real 1 million signals, check schematic and structural debug for exact connectivity and active-driver and source mapping against independent elaboration.
  2. Require hierarchical depth queries, fanin and fanout, clocks and transaction overlays.
  3. Allow no omitted live edge.
  4. Require cold structural-answer time at most 5 s.
  5. Require 95th-percentile navigation time at most 1 s.
  6. Require hierarchy expansion query time at most 2 s.
  7. Use cancellable pagination.
  8. Use the statistical comparison in section 3.1 for task time and effort against Verdi nSchema and nTrace at 3.1 margins.

<a id="D18c10"></a>

#### D18.c10: Qualify the virtual-platform debugger
- Phases: Start work in P06. Accept this cell in P06.
- Must pass first: D18.c6, D11.c5, D29.c1, D27.c8.
- Baseline: The qualified Fast Models debugger workflow.
- Summary: Test the qualification of the virtual-platform debugger. Require at least 50 valid and 50 stale and denied and wrong-time controls per task.
- Rule:
  1. Implement typed virtual-platform debugger operations: attach, stop, continue, step, breakpoint, register and memory read and write, and reset.
  2. Require at least 50 valid and 50 stale and denied and wrong-time controls per task.
  3. Require zero state and time and generation errors.
  4. Compare completed tasks against the qualified Fast Models debugger workflow.
  5. Compare all endpoints under section 3.1.
  6. Use a completion margin of .005.
  7. Use a machine-time ratio margin of 1.02.
  8. Use a scripted recovery-time ratio margin of 1.15.
  9. Use a tail ratio margin of 1.20.
  10. Require that observation transport alone cannot pass.

<a id="D20c4"></a>

#### D20.c4: Seal behavior sub-strata and class debt limits
- Phases: Start work in P06. Accept this cell in P06.
- Must pass first: D20.c1, D10.c1, D11.c1, D22.c1, D27.c8, D20.c2b as explanatory context only.
- Baseline: Use the baseline stated in the rule when a comparison applies.
- Summary: Test the sealing of behavior sub-strata and class debt limits. Require at least 10 independent full-anchor families per named sub-stratum.
- Rule:
  1. Require vector gather-scatter, reduction and permutation behavior sub-strata.
  2. Include ML dense, sparse, convolution, attention, quantized, dynamic and fallback sub-strata.
  3. Include media image, audio, video, resampling, hash, public and symmetric crypto sub-strata.
  4. Include BLAS and vector and ONNX and TFLite and llama.cpp and FFmpeg and libvpx and Opus and OpenSSL and mbedTLS-class applications under ancestry audit.
  5. Record each family’s RVV state: reference-only, built, output-checked, RTL-integrated, full-anchor, calibrated.
  6. Pin VLEN and ELEN and SEW and LMUL and masks and tails and vstart and fault semantics.
  7. Missing operators and fallback remain weighted debt.
  8. Require scalar diagnostics separate from native vector tracks.
  9. Require at least 10 independent full-anchor families per named sub-stratum.
  10. Require two full inputs per family.
  11. Require at least 5 families to reach calibrated state.
  12. Audit ancestry.
  13. Expand for precision and power.
  14. This P06 receipt seals the sub-strata and their input and anchor method only.
  15. Require that all executed counts and performance claims close later in D20.c2b as explanatory context only.
  16. Retain the explicit scope of the complete-census and substitute routes in 3.4.
  17. For each class, require aggregate debt weight at most 5% under sealed equal-family weights.
  18. Include missing operators, scalar fallback, unsupported input shapes and unqualified useful-work mappings in that debt.
  19. Require deployment-weighted debt at most 5% under qualified deployment weights.
  20. Mark the class UNQUALIFIED above either applicable ceiling.
  21. Publish debt but no class ratio or overall headline that includes it as qualified.
  22. Require that scalar fallback remains visible and never counts as vector execution.
  23. Add mandatory JIT and managed-runtime sub-strata: browser-style JavaScript and WebAssembly, JVM and managed garbage-collector workloads.
  24. Pin runtime tiers, compilation and deoptimization phases, collection pauses and useful outputs.
  25. Require at least 10 independent full-anchor families per new sub-stratum.
  26. Require at least five calibrated families per new sub-stratum.
  27. Expand for power.
  28. Retain all class debt ceilings.
  29. This early receipt defines unsampled anchors only.
  30. A sampled execution claim requires the later sampled corpus child.

<a id="D25c3a"></a>

#### D25.c3a: Check verified agent campaign benefit
- Phases: Start work in P06. Accept this cell in P06.
- Must pass first: D25.c2, D35.c1; severe escapes invalidate dependent cohorts, D27.c8.
- Baseline: Use shell-plus-upstream and the strongest qualified named coding agent, plus all named relevant commercial EDA agents.
- Summary: Test adjusted median total verified campaign-time upper ratio at most 0.75 against shell-plus-upstream, the strongest qualified coding agent and every required commercial EDA agent per provider.
- Rule:
  1. Retain censored failures in fixed-deadline analysis.
  2. A point median 25% reduction cannot pass alone.
  3. Require the adjusted total machine-cost upper ratio at most 1.02 per accepted change.
  4. Require the adjusted scripted recovery-time upper ratio at most 1.02.
  5. Use section 3.1 for both comparisons.
  6. Weight whole cost before reveal.
  7. Use the 0.005 sampled non-inferiority quality margin.
  8. Keep mandatory safety exact.
  9. Compare identical pinned models, context, information and budgets against the strongest qualified shell-plus-upstream recipe.
  10. Also compare them against the leading agent recipe for IDE and CLI use.
  11. Use multi-week decisions across three mechanism families, two compilers and three generations.
  12. Pilot at least 30 campaign clusters per stratum, then expand for power.
  13. Count repeated context and token load, failed work, no-gain work, late winners and help.
  14. Pin released versions of Codex CLI, Claude Code CLI, Cursor agent and GitHub Copilot agent as comparator candidates.
  15. Select the strongest qualified agent on disjoint R08 comparator-matching controls before confirmation.
  16. Compare against both shell-plus-upstream and the selected agent recipe.
  17. Use at least 2 independent model providers.
  18. Within each provider pair, pin the same model on candidate and comparators.
  19. Require original strata and secondary benefits to pass separately per provider.
  20. Permit no provider pooling or ancestry claim.
  21. Include Cadence ChipStack AI Super Agent and Synopsys AgentEngineer solutions on the Synopsys Autopilot Platform in commercial EDA agent comparisons.
  22. Include Synopsys.ai Copilot as the assistant-class comparator.
  23. Use the exact version tuple in the commercial agent pin register in commercial-features.md.
  24. Require every named comparator on each relevant engineering outcome under original benefit, safety and cost bounds.
  25. Qualify feature relevance with independent task witnesses before results.
  26. A general coding agent cannot substitute for an EDA agent.
  27. Keep a comparator OPEN when its exact build identity is missing.
  28. For fixed-internal-model products, compare complete systems.
  29. Publish the model mismatch.
  30. Do not claim a matched-model effect for those products.
  31. Before confirmation, replace a renamed commercial agent with its documented successor on the same required task and feature frame.
  32. Independently verify lineage, version and capability coverage.
  33. Keep a withdrawn product comparison OPEN if no qualified successor exists.
  34. A weaker product cannot replace it.
  35. Pin the transition before results.
  36. Retain the old product record.
  37. Severe escapes must invalidate dependent cohorts.
  38. Reassess the strongest open coding agent every 30 calendar days and at each model or tool upgrade.
  39. Select on disjoint sealed tasks with equal tuning and total budgets before confirmation.
  40. Pin model, weights or service version, prompts, tools and permissions.
  41. Restart affected confirmation under a reserved attempt when that pin changes.
  42. Retain all failed attempts and alpha charges.
  43. Category 13 primary: Require adjusted median total verified campaign-time upper ratio at most 0.75 against shell-plus-upstream, the strongest qualified coding agent and every required commercial EDA agent per provider.

<a id="D25c3b"></a>

#### D25.c3b: Check campaign completion analysis
- Phases: Start work in P06. Accept this cell in P06.
- Must pass first: D25.c2, D35.c1; severe escapes invalidate dependent cohorts, D27.c8.
- Baseline: Use the candidate and baseline campaign survival curves from the parent comparison.
- Summary: Test completion and censoring rules without selecting only completed campaigns. Return INCONCLUSIVE if either survival curve does not cross 0.5.
- Rule:
  1. Count campaign completion only when every required task reaches independently verified terminal output and no wrong accepted action occurs.
  2. Use registered clustered Kaplan-Meier analysis under justified independent administrative censoring.
  3. Fix the deadline before start.
  4. Give failed and abandoned campaigns no completion event before the deadline.
  5. Include their full deadline exposure in restricted-mean time.
  6. Return INCONCLUSIVE if either survival curve does not cross 0.5.
  7. Return INCONCLUSIVE if the simultaneous median-ratio bound is unbounded.
  8. Never substitute a median of completers.
  9. Report restricted-mean time separately with its own claim budget.
  10. Severe escapes must invalidate dependent cohorts.

<a id="D25c3c"></a>

#### D25.c3c: Check agent recovery and contamination controls
- Phases: Start work in P06. Accept this cell in P06.
- Must pass first: D25.c2, D35.c1; severe escapes invalidate dependent cohorts, D27.c8. the sealed schema interface of D25.c3a; it supplies no final runtime evidence.
- Baseline: Use the pinned named comparator configurations and independent reference answers.
- Summary: Test durable campaign recovery and fresh-family benefit with independent contamination custody. Require zero duplicate or wrong accepted actions.
- Rule:
  1. Add 100 stale-context, lost-context and session-reset cases during multi-week work.
  2. Resume solely from durable campaign state.
  3. Reconstruct tasks, claims and generations exactly.
  4. Require zero duplicate or wrong accepted actions.
  5. Permit no lost obligations.
  6. Compare resumed completion with margin .005.
  7. Compare machine recovery time with ratio 1.02.
  8. Use section 3.1 statistical comparisons against the D25.c3a comparators, each with justified budgets.
  9. Pin model versions before generating fresh semantic variants.
  10. Keep hidden task answers and canary strings outside public prompts, logs and training feeds.
  11. Record provider retention settings, model version, known cutoff or UNKNOWN, access history and cryptographic custody hashes.
  12. Do not infer absence of contamination from a stated cutoff.
  13. Test at least 20 canary-extraction and 20 leaked-answer controls per provider.
  14. Quarantine the family for detected canaries or unexpected solution matches.
  15. Invalidate dependent claims.
  16. Replace it with fresh independently authored families.
  17. Rerun with the same reserved alpha, attempt and power rules.
  18. Report public-benchmark, held-out and fresh-family results separately.
  19. Require the fixed engineering benefit to pass on fresh families.
  20. Keep unknown custody OPEN.
  21. Severe escapes must invalidate dependent cohorts.
  22. Test equal task completion with unequal campaign completion, unequal deadlines, informative dropout and more than 50% censored campaigns.
  23. Seal disjoint development, held-out and freshly generated post-model-freeze task families in an independent custody service.

<a id="D25c4"></a>

#### D25.c4: Check complete-campaign tails
- Phases: Start work in P07. Accept this cell in P07.
- Must pass first: D25.c3a, D25.c3b, D25.c3c, D27.c8.
- Baseline: Use each campaign comparator from the parent campaign comparisons.
- Summary: Test critical campaign tails and their preassigned fallbacks without replacing median benefit. Require 95th-percentile and 99th-percentile verified completion-time upper ratios at most 1.20.
- Rule:
  1. Compare critical complete-campaign tails against each campaign comparator.
  2. Fix the deadline at 90 days.
  3. Require 95th-percentile and 99th-percentile verified completion-time upper ratios at most 1.20.
  4. Cluster by project and campaign.
  5. Retain failed and abandoned campaigns at full deadline exposure.
  6. Seal the quantile survival method and independent power calibration.
  7. For each unidentifiable quantile, use its preassigned restricted-mean time to day 90 fallback.
  8. Require its upper candidate-to-baseline ratio at most 1.02.
  9. Also require day-90 completion difference lower bound at least -.005.
  10. Make both fallback endpoints critical, separately budgeted and powered.
  11. Keep median benefit mandatory.
  12. Tails cannot rescue median benefit.

<a id="D25c6"></a>

#### D25.c6: Check each required agent outcome
- Phases: Start work in P07. Accept this cell in P07.
- Must pass first: D25.c2, D25.c3a, D25.c3b, D27.c8, D25.c3a.
- Baseline: Apply every relevant commercial EDA agent comparator and rule from D25.c3a.
- Summary: Test all required engineering outcomes separately across projects, providers and upgrade generations. Require exactly zero wrong accepted outputs separately per stratum.
- Rule:
  1. For #119 root-cause tasks, require an independently reproduced cause and verified repair.
  2. For adapter creation, require a versioned adapter and complete positive and negative conformance.
  3. For coverage closure, require all assigned bins hit or valid global exclusions.
  4. For specification-change review, require a complete affected-obligation and assumption map with independent audit.
  5. Cross all outcomes with 10 independent projects and initial plus two upgrade generations.
  6. Require correct completion at least .80 separately per stratum.
  7. Require exactly zero wrong accepted outputs separately per stratum.
  8. Require risk upper bound at most .01 separately per stratum.
  9. Require machine cost non-inferiority ratio at most 1.02 per stratum.
  10. Use the D25.c3a parent receipt for the Category 13 primary campaign-time benefit.
  11. Keep rejection of misleading evidence orthogonal.
  12. It must never substitute for a task.
  13. Map PR #373 seeded-bug benchmark evidence to this cell and native task receipts.
  14. Merge must not qualify those receipts.
  15. Cross every outcome, upgrade and project stratum with the same at least 2-provider axis.
  16. Permit no rescue by averaging providers.
  17. Add a required outcome that implements and verifies a microarchitecture change in RTL.
  18. Require independent sequential equivalence checking or complete stated correctness proofs, plus complete regression.
  19. Add a required outcome that runs a performance-optimization campaign to a checked result.
  20. Require sealed predictions and independently checked retained winners.
  21. Cross both added outcomes with the same ten projects, two providers and initial plus two upgrades.
  22. For each added outcome stratum, require completion at least .80.
  23. Require zero wrong accepts.
  24. Require risk upper bound at most .01.
  25. Require the time benefit.
  26. Require the separate machine non-inferiority gate.
  27. Require the adjusted scripted recovery-time upper ratio at most 1.02 per outcome stratum.
  28. Neither added outcome can close by design advice alone.
  29. Apply the complete D25.c3a commercial EDA agent comparison contract to every relevant outcome.
  30. Include every named product, exact build pins, relevance, safety, benefit, cost and model-mismatch rules.

<a id="D29c2"></a>

#### D29.c2: Define the complete scripted task and accessibility matrix
- Phases: Start work in P06. Accept this cell in P06.
- Must pass first: D30.c2, D27.c8, D34.c4 (explanatory context only; it supplies no acceptance evidence), D35.c3 (explanatory context only; it supplies no acceptance evidence), D27.c1 (explanatory context only; it supplies no acceptance evidence), D35.c4 (explanatory context only; it supplies no acceptance evidence), D38.c3 (explanatory context only; it supplies no acceptance evidence), D29.c2 (explanatory context only; it supplies no acceptance evidence).
- Baseline: Use the baseline stated in the rule when a comparison applies.
- Summary: Test all 300 task crossings and 900 accessible interface variants. Require zero wrong accepted results.
- Rule:
  1. Use the fixed matrix of supported hosts, SpinalHDL, Chisel, SystemVerilog, VHDL and the fifth frontend, and all listed tasks.
  2. Include install, gate, cosim, diagnosis-entry, repair, proof-unknown, coverage-closure and upgrade-recovery in the task set.
  3. Also include model-onboarding-calibration, architecture-search, compiler-model-generation and security-contract-authoring.
  4. Keep 300 named product cells with IDs formed from D29.c2, host, language and task.
  5. Use that D29.c2 reference as context for ID formation.
  6. Give each cell text retrieval, cancellation and recovery child modes, for 900 total test variants.
  7. Keep the complete matrix, with the fifth language fixed by D30.c2.
  8. Pin OS, CLI, MCP and agent versions.
  9. Use native CLI and MCP clients on macOS, Windows/WSL2 and Linux.
  10. Test complete text query and status outputs on each supported host.
  11. Permit no silent unsupported cross-products.
  12. Bind each task to an immutable tool-generation ID and its defining capability receipt.
  13. Publish task witnesses.
  14. Freeze required and low-relevance tiers under V26, the relevance-review protocol.
  15. Keep all 300 base crossings and all 900 access variants visible.
  16. Before marking a low-relevance crossing not applicable, independently prove the absence of an actual task.
  17. Reopen crossings for new task evidence.
  18. Retain each original crossing ID and a separate exact semantic and accessibility control.
  19. Unproved equivalence or any distinct access need prevents merging.
  20. Run all 300 host, language and task crossings as scripted or agent tests.
  21. Run all 900 text retrieval, cancellation and recovery variants against independently specified answers and status.
  22. Require a requirement certificate independent of D27.c1 for genuine nonapplicability, never an adverse result.
  23. Keep incomplete and refused work in the denominator.
  24. Use the strictest group margin and deadline.

<a id="D29c7"></a>

#### D29.c7: Check documentation and label comprehension
- Phases: Start work in P06. Accept this cell in P06.
- Must pass first: D27.c8. the sealed schema interface of D29.c11; it supplies no final runtime evidence.
- Baseline: Use native vendor documentation under task-specific budgets.
- Summary: Test mandatory task-answer error count exactly zero against independent expected documentation and status answers on every host, language and task class.
- Rule:
  1. Answer without author help.
  2. Require zero wrong acceptance, proof or safety answers on required controls.
  3. Require adjusted noncritical answer-error upper bound at most .01.
  4. Detect 20 stale, missing and contradictory documentation mutants.
  5. Documentation links or successful commands alone cannot close this cell.
  6. Compare verified completion statistically with non-inferiority margin .005 against native vendor documentation.
  7. Compare scripted or pinned-agent help-processing time with upper ratio margin 1.15 under task-specific budgets.
  8. Have the pinned agents read all exported label types.
  9. Test permitted and prohibited proof, finite, population, natural, generated, privacy and non-inferiority claims.
  10. Require zero wrong mandatory proven or population readings.
  11. Include every RL24 release-vector label and inherited label.
  12. Use the D29.c11 compact text schema in CLI and MCP default outputs.
  13. Return the full-vector hash beside the D29.c11 compact text.
  14. Retrieve the complete RL24 vector and reasons in one action.
  15. Acceptance consumers must verify that vector.
  16. Require zero false Full interpretations in mandatory controls.
  17. Compact transport must never change predicates.
  18. Use pinned agents to answer at least 100 task, status, unknown and recovery questions per host, language and task class using documentation only.
  19. Check the answers against independent expected answers.
  20. Check every exported label type against its complete release predicate.
  21. Category 15 primary: Require mandatory task-answer error count exactly zero against independent expected documentation and status answers on every host, language and task class.
  22. Seal the D29.c11 schema interface no later than P05, before this cell starts. Freeze the six fields, text limits, receipt hash, retrieval call, full-vector fields and verification predicates stated in D29.c11 rules 14 through 18.
  23. An independent schema checker must reject missing fields, wrong hashes, stale vectors and altered predicates before P06. This interface receipt supplies no D29.c11 final comprehension or benefit result.

<a id="D29c9"></a>

#### D29.c9: Check repair from the first install or adapter failure
- Phases: Start work in P07. Accept this cell in P07.
- Must pass first: D29.c7, D27.c8.
- Baseline: Use the strongest qualified native or vendor repair guide.
- Summary: Test correct independent repair of the leading error classes within time and effort bounds. Limit 95th-percentile time to at most 30 min.
- Rule:
  1. Independently rank the top 20 install and adapter error classes from a sealed support census.
  2. Include dependency, ABI, architecture, permission, stale-schema and capture errors.
  3. Use fresh scripted test cases per access mode.
  4. Limit 95th-percentile time to at most 30 min.
  5. Require zero unsafe or wrong accepted repairs.
  6. Compare allocated core-hours per independently verified repair statistically against the strongest qualified native or vendor guide.
  7. Require the adjusted core-hour upper ratio at most .90.
  8. Retain all completion and tail non-inferiority margins.
  9. Run scripted or pinned-agent repairs for all 20 error classes.
  10. Require success lower bound at least 0.90.
  11. Require adjusted checked-repair-time upper ratio at most 0.90 against the strongest qualified native or vendor guide.

<a id="D29c11"></a>

#### D29.c11: Check two-level text labels
- Phases: Start work in P07. Accept this cell in P07.
- Must pass first: D29.c10, D29.c7, D27.c8.
- Baseline: Compare the existing full-vector view under identical tasks and budgets.
- Summary: Test the six-field text schema and one-call retrieval of the complete decision vector.
- Rule:
  1. Never hide caveats in an optimistic word.
  2. Require noncritical error upper bound at most 1%.
  3. Require verified completion non-inferiority margin .005.
  4. Require scripted checked-task core-hour ratio at most 1.15.
  5. Require tail ratios at most 1.20.
  6. Compare the existing full-vector view under identical tasks and budgets.
  7. Block decisions for a missing or stale vector.
  8. Test size and meaning on all original tasks and scripted access variants.
  9. Truncation cannot remove a limitation.
  10. Use an independent checker implementation to check default text against the stated label fields, size limits and expected label predicates.
  11. Include truncated, stale and wrong-frame views in comprehension tests.
  12. Check all original tasks with scripts against independent expected label predicates.
  13. Require zero wrong proof, population or natural-source label outputs.
  14. Use exactly six default text fields: category, tier, frame, evidence class, comparison status and open-gate count.
  15. Limit the default text to 40 words and two lines of at most 120 Unicode characters each.
  16. Exclude the fixed receipt hash and typed retrieval command from the text limits.
  17. Retrieve the complete typed vector, scope, status, strongest unsupported claim, blocked endpoints, actual loss, margin and all open claims with one typed call.
  18. Require every acceptance consumer to verify that complete vector before a decision.
  19. Publish the sealed schema interface by P05 for D29.c7. Preserve its identity in the P07 runtime receipt. Any schema change invalidates and reruns the D29.c7 consumer checks.

<a id="D30c3"></a>

#### D30.c3: Check unseen core transfer
- Phases: Start work in P06. Accept this cell in P06.
- Must pass first: D30.c1, D30.c2, D27.c8, D01.c4 (explanatory context only; it supplies no acceptance evidence).
- Baseline: Use Metals and sbt for Vex and Nax, native SV for CVA6, Chipyard and sbt for Rocket, GHDL, nvc and Sigasi for NEORV32, and upstream Chisel, Mill and sbt for XiangShan.
- Summary: Test sealed unseen-core transfer count at least 2 against the independent adapter obligation inventory, with distinct language and generator ancestries.
- Rule:
  1. Seal two unseen cores from different language and generator ancestries.
  2. Apply the same adapter obligations and effort bounds.
  3. Permit no generic edits.
  4. Keep later model onboarding as a separate consumer qualified in D01.c4, which is explanatory context here.
  5. Use Metals and sbt for Vex and Nax native comparisons.
  6. Use native SV for CVA6.
  7. Use Chipyard and sbt for Rocket.
  8. Use GHDL, nvc and Sigasi for NEORV32.
  9. Use upstream Chisel, Mill and sbt for XiangShan.
  10. For other languages, negotiate unsupported status without a generic-all-HDL claim.
  11. Use checker implementations with ancestry independent of the initial adapter implementations.
  12. Category 16 primary: Require sealed unseen-core transfer count at least 2 against the independent adapter obligation inventory, with distinct language and generator ancestries.

<a id="D30c8"></a>

#### D30.c8: Check a non-RISC-V CPU adapter
- Phases: Start work in P07. Accept this cell in P07.
- Must pass first: D30.c1, D09.c1, D27.c8.
- Baseline: Use the baseline stated in the rule when a comparison applies.
- Summary: Test an independent non-RISC-V adapter without closing a RISC-V ISA claim or requiring a BOOM change. Require zero ISA names in generic code.
- Rule:
  1. Add one independently authored non-RISC-V CPU adapter on an existing target or a sealed interface substitute.
  2. Use at least 100 positive and 100 fault controls.
  3. Require exact architectural transitions and complete trace identity.
  4. Require zero ISA names in generic code.
  5. Report a separate adapter frame.
  6. This test cannot close a RISC-V ISA claim or require a BOOM change.

<a id="D32c5"></a>

#### D32.c5: Qualify package channels and contribution tooling
- Phases: Start work in P06. Accept this cell in P06.
- Must pass first: D32.c1, D29.c1, D27.c8.
- Baseline: Use the baseline stated in the rule when a comparison applies.
- Summary: Test two clean installs and two upgrades per signed package channel with offline provenance and rollback.
- Rule:
  1. Provide signed Homebrew, one named Linux distribution and conda packages on every applicable supported host.
  2. Require two clean independent installs and two upgrades per channel.
  3. Test offline use, provenance and rollback.
  4. Permit no hidden network fetch.
  5. Provide a reproducible agent-task benchmark covering all four #119 strata.
  6. Use sealed holdouts, raw failed attempts and versioned scoring.
  7. Require searchable archives with stable URLs, version history and export.
  8. Support links from Discord discussions to archived decision records.
  9. Test the links with scripted records.
  10. Provide a reproducible first-patch command path checked by scripts from a clean checkout.

<a id="D32c90"></a>

#### D32.c90: Check release and contribution issue tooling
- Phases: Start work in P06. Accept this cell in P06.
- Must pass first: D32.c1, D27.c2, D27.c8.
- Baseline: Use the baseline stated in the rule when a comparison applies.
- Summary: Test independently checked intake cases and a release checklist with complete package hashes.
- Rule:
  1. Apply I90, which requires one receipt per issue, exact source-span coverage and an independent checker audit.
  2. No child replaces a proof, comparison or population receipt.
  3. For #38, use an independent checker to check the scripted patch and vulnerability intake results for CONTRIBUTING, SECURITY and templates.
  4. For #78, provide a release checklist with machine-checkable evidence links and complete package hashes.

<a id="D32c6"></a>

#### D32.c6: Qualify published comparison evidence
- Phases: Start work in P07. Accept this cell in P07.
- Must pass first: D32.c1, D32.c5, D27.c8.
- Baseline: Use the baseline stated in the rule when a comparison applies.
- Summary: Test comparison receipt exports, manifests and replay data. Keep the fully reproducible public label OPEN when the exported evidence cannot support replay. Permit no credential or private-source leakage.
- Rule:
  1. Give every exported comparison label a reproducible receipt and raw-data bundle.
  2. Include a sealed manifest, source and build hashes, calculation code and independent replay instructions.
  3. Export the configured data subset and an exact redaction inventory.
  4. Label unreproducible restricted claims RESTRICTED-AUDIT, never publicly reproducible.
  5. Keep the fully reproducible public label OPEN until supported.
  6. Permit no credential or private-source leakage.

<a id="D32c8"></a>

#### D32.c8: Check contribution and disclosure tooling
- Phases: Start work in P06. Accept this cell in P06.
- Must pass first: D32.c1, D27.c8.
- Baseline: Use the baseline stated in the rule when a comparison applies.
- Summary: Test 20 contribution and 20 disclosure cases for exact policy routing without private-report leakage.
- Rule:
  1. Provide a private reporting route.
  2. Test report routing and configured response deadlines with scripts.
  3. Require all cases to follow the published policy without leaking private reports.
  4. Provide automated contribution checks and a tested exception path.
  5. Test 20 contribution and 20 disclosure cases with scripts.
  6. Check private reporting, embargo handling and revocation without leaking private reports.
  7. Keep capability_status, public_release_authorized and community_milestones as distinct machine fields.
  8. Test at least 20 empty-usage-record controls.
  9. Require them to change only community_milestones.
  10. Test at least 20 missing-rights controls and at least 20 missing-security-receipt controls.
  11. Require them to change public_release_authorized.
  12. Treat rights status as owner input.
  13. Do not use rights or adoption status to gate capability_status.

<a id="D33c2"></a>

#### D33.c2: Compare confidentiality and integrity verification
- Phases: Start work in P07. Accept this cell in P07.
- Must pass first: D34.c2, D34.c3, D27.c8.
- Baseline: Use both JasperGold Security Path Verification and Cycuity Radix.
- Summary: Test the paired geometric-mean ratio of seconds per conclusive checked contract. Require the adjusted candidate-to-comparator upper ratio at most 0.90 against both JasperGold Security Path Verification and Cycuity Radix.
- Rule:
  1. Require at least 300 independent confidentiality and integrity contracts.
  2. Cover transient execution, cache-SMT, boot-PMP, DMA-IOMMU, guest and debug, with valid hard proofs and violations.
  3. Require exact zero unsound verdicts and exact mandatory violations.
  4. Compare with both JasperGold Security Path Verification and Cycuity Radix.
  5. Use the same RTL, contracts, observations and budgets.
  6. Measure scripted diagnosis core-hours-ratio and scripted checked-time-ratio separately.
  7. Require each ratio to be non-inferior with an upper bound at most 1.15.
  8. Require checked-capacity-ratio, in conclusive contracts per core-hour, to have lower bound at least 1 divided by 1.05.
  9. Require sampled solved and sensitivity differences to have lower bounds at least -.005.
  10. Require resident-memory and storage ratios at most 1.02.
  11. Require all metrics against both vendors.
  12. Permit no alternative-comparator rescue.
  13. Preserve confidentiality, integrity, proof and attack labels and absent intersections.
  14. Category 18 primary: Measure seconds per conclusive checked contract with a paired geometric mean.
  15. Require the adjusted candidate-to-comparator upper ratio at most 0.90 against both JasperGold Security Path Verification and Cycuity Radix.

<a id="D33c5"></a>

#### D33.c5: Detect adversarial microarchitectural faults
- Phases: Start work in P07. Accept this cell in P07.
- Must pass first: D33.c1, D34.c3, D27.c8.
- Baseline: Use the baseline stated in the rule when a comparison applies.
- Summary: Test independently activated adversarial faults and retain relational-proof requirements for positive security guarantees. Require at least 100 independently activated faults per class plus allowed controls.
- Rule:
  1. Cover transient injection, replay-state corruption, stale permission and tags, and speculative fault effects across attacker-controlled timing.
  2. Seal attacker authority and protected assets.
  3. Require at least 100 independently activated faults per class plus allowed controls.
  4. Catch exact mandatory integrity and leak violations.
  5. Require detection lower bound at least .95 per class.
  6. Independently replay counterexamples on original RTL.
  7. Safety diagnostic coverage alone cannot close adversarial integrity or confidentiality claims.
  8. Require relational proofs for positive guarantees.

<a id="D33c6"></a>

#### D33.c6: Execute declared SMT attacks
- Phases: Start work in P07. Accept this cell in P07.
- Must pass first: D33.c1, D17.c4, D27.c8.
- Baseline: Use the baseline stated in the rule when a comparison applies.
- Summary: Test execution of every declared SMT attack contract on the sealed substitute or a capable natural target. Require all 6 numbered rule items.
- Rule:
  1. Execute every declared SMT attack contract on the sealed SMT substitute or capable existing natural target.
  2. Require secret-bearing sharing and competition and independent attack-activation witnesses.
  3. Include all sibling contexts, reset-retained state and mitigation bypasses.
  4. Require exact mandatory leak detection and powered D33.c1 detection, time and effort comparisons.
  5. State generated-SMT attack detection only on generated receipts.
  6. An interface specification alone cannot close this execution receipt.

<a id="D33c8"></a>

#### D33.c8: Validate leakage-unit mappings
- Phases: Start work in P06. Accept this cell in P06.
- Must pass first: D33.c1, D34.c1, D27.c8.
- Baseline: Use the baseline stated in the rule when a comparison applies.
- Summary: Test quantitative digital leakage mappings against known channels and exact invalid-mapping controls. Require upper relative mapping error at most 2%.
- Rule:
  1. Create a leakage-unit mapping deliverable per digital timing, cache, contention and architectural channel class.
  2. Derive observation-to-bits-per-query, advantage-per-query or secret-bits-per-Q bounds.
  3. Validate on at least 50 injected known-leakage channels.
  4. Use at least 50 zero, rare, conditional and misspecified controls.
  5. Include below-budget, at-budget and above-budget cases, bias and adaptive composition.
  6. Provide analytic bounds and powered empirical calibration.
  7. Require upper relative mapping error at most 2%.
  8. Require mapping error at most minimum effect effect_min divided by 4 in channel units.
  9. Accept zero invalid mappings.
  10. Do not use them to close a quantified-leakage claim.
  11. Use standard-deviation-only results as diagnostic evidence only.
  12. Require a valid leakage-unit mapping for quantified claims.

<a id="D34c3"></a>

#### D34.c3: Prove protected-state integrity and capability safety
- Phases: Start work in P06. Accept this cell in P06.
- Must pass first: D34.c1, D17.c3, independent policy specification, D27.c8, D12.c1 (explanatory context only; no acceptance evidence).
- Baseline: Use the baseline stated in the rule when a comparison applies.
- Summary: Test authorization, progress and capability-safety proofs across the full integrity boundary matrix. Require at least 20 allow and 20 forbidden, reset and replay cases per boundary.
- Rule:
  1. Cover code, data, metadata, page tables, PMP, IOMMU, privilege, guest, debug, boot and device assets.
  2. Cover CPU, DMA, guest, hart and debug requesters.
  3. Cover read, write, execute, atomic and control actions, epochs, outstanding requests, reset and revocation.
  4. Prove no unauthorized mutation or authority release.
  5. Prove authorized progress.
  6. Require at least 20 allow and 20 forbidden, reset and replay cases per boundary.
  7. Require at least 100 activated integrity faults.
  8. Require zero mandatory misses.
  9. Require powered detection lower bound at least .95.
  10. Include TLB, IOTLB, stale tags, boot rollback and retries.
  11. Require 100 boot, PMP and debug cases.
  12. Require 20 bypass mutants.
  13. Test CoVE, Smmtt, ePMP, Smepmp and pointer masking only on capable targets.
  14. Treat 20 allow and 20 forbidden taint cases as instrumentation tests, not proof.
  15. Require CHERI capability safety under #210 on capable targets.
  16. Cover unforgeability, bounds, permissions, tag integrity, monotonicity, sealing, unsealing and revocation assumptions.
  17. Require positive unbounded proofs.
  18. Require 20 legal and 20 forbidden cases and 20 tag, bounds and revocation mutants per boundary.
  19. Require exact mandatory effects.
  20. D12.c1 tags alone cannot close capability-safety proof.
  21. Use that reference only as explanatory context.
  22. Require an independent policy specification.

<a id="D34c4"></a>

#### D34.c4: Export proved software security contracts
- Phases: Start work in P07. Accept this cell in P07.
- Must pass first: D34.c2, D34.c3, D38.c1 (sealed interface schema only; no final runtime or comparison receipt); confidentiality and integrity never share leakage allowance, D27.c8.
- Baseline: Use the baseline stated in the rule when a comparison applies.
- Summary: Test software and OS consumption of versioned security contracts and proved Zkt latency assumptions. Require refusal by 30 unsupported, expired and assumption-violating consumers.
- Rule:
  1. Provide a software-consumable versioned constant-time and security contract.
  2. Specify instructions, operand, privilege and cache assumptions, allowed observations, context-switch and interrupt rules, entropy, declassification, proof hashes and revocation.
  3. Prove advertised Zkt operand-independent latency.
  4. Use 10k operand pairs per instruction and configuration, with variable-latency controls.
  5. Separate issue, complete and retire observations.
  6. Use the sealed D38.c1 compiler interface to consume contracts and accept or reject secret-sensitive schedules.
  7. Require an independent OS consumer to check handoff and context policy and invalidation on upgrade.
  8. Require refusal by 30 unsupported, expired and assumption-violating consumers.
  9. Confidentiality and integrity must never share leakage allowance.

<a id="D34c5"></a>

#### D34.c5: Check entropy CSR and security-policy controls
- Phases: Start work in P07. Accept this cell in P07.
- Must pass first: D34.c3, D10.c1, D27.c8.
- Baseline: Use the baseline stated in the rule when a comparison applies.
- Summary: Test exact entropy and seed CSR effects and policy violations without claiming physical entropy quality. Require 30 legal and 30 health, access and replay violations per interface.
- Rule:
  1. For entropy and seed CSR #203, check health, protocol, failure and software behavior.
  2. Require 30 legal and 30 health, access and replay violations per interface.
  3. Require independently exact effects and refusals.
  4. Keep physical entropy quality as an assumption.
  5. Also apply D34.c3 controls to landing-pad, shadow-stack, ePMP, pointer-mask and test-enable policies.
  6. Permit no mandatory misses.

<a id="D35c90"></a>

#### D35.c90: Check prospective calibration and drift
- Phases: Start work in P06. Accept this cell in P06.
- Must pass first: D35.c1, D27.c2, D27.c8.
- Baseline: Use the baseline stated in the rule when a comparison applies.
- Summary: Test issue #31 predictions against independent full anchors and invalidate consumers when calibration drifts. Apply I90, which requires one receipt per issue, exact source-span coverage and an independent checker audit.
- Rule:
  1. Apply I90, which requires one receipt per issue, exact source-span coverage and an independent checker audit.
  2. Use actual records for decision and external-action children, not synthetic cases.
  3. No child replaces a proof, comparison or population receipt.
  4. For #31, compare sealed prospective predictions with independent full anchors in a calibration ledger.
  5. Drift must invalidate consumers.
  6. Preserve all failed and no-gain updates.

<a id="D36c4"></a>

#### D36.c4: Qualify native comparator measurements
- Phases: Start work in P06. Accept this cell in P06.
- Must pass first: D04.c2, D36.c3, D27.c8.
- Baseline: Use the named Zen 5 and M-series systems with each pinned and qualified measurement route.
- Summary: Test counter attribution, fallback time measurements and uncertainty on named Zen 5 and M-series systems. Require overhead and bias at most minimum effect effect_min divided by 4.
- Rule:
  1. Use named Zen 5 and M-series systems for the comparator harness.
  2. Pin model, OS, compiler, affinity, governor and frequency policy, and measured frequency distribution.
  3. Pin SMT off and on where available, counter permissions, thermal steady state and background load.
  4. On Zen 5, use Linux perf_event_open and perf stat cycles and instructions with task and region-of-interest binding.
  5. Record enabled and running counts with no unaccounted multiplexing.
  6. On macOS M-series, use version-pinned Instruments CPU Counters and xctrace export.
  7. Alternatively, use a privileged kperf and kpc private-framework adapter with probed event IDs and signed raw configuration.
  8. Never assume undocumented ABI stability.
  9. Qualify each OS and CPU route on at least 20 known-work loops plus sleep, migration, overflow and background-load controls.
  10. Distinguish active cycles from reference ticks and per-task from system-wide counts.
  11. Cross-check two routes where available.
  12. Require overhead and bias at most minimum effect effect_min divided by 4.
  13. Missing attribution must refuse cycle claims.
  14. Treat macOS affinity as a measured placement constraint, not promised hard pinning.
  15. For fallback, use mach_continuous_time or monotonic elapsed time with the same output, region-of-interest, thermal and noise controls.
  16. Label fallback evidence MEASURED-TIME-ONLY and cycles UNAVAILABLE.
  17. Valid COUNTER-QUALIFIED or MEASURED-TIME-ONLY results close only the appropriate measurement service.
  18. Fallback cannot close cycle-ratio hypotheses.
  19. Use independent output and work-count controls and counter-presence and semantic checks.
  20. Require at least 30 repeats per point, then expand for power.
  21. Require repeatability coefficient of variation at most 1%.
  22. For magnitude decisions, require bias plus uncertainty at most minimum effect effect_min divided by 4.
  23. Refuse noisy, missing-counter and SMT-misbound runs.
  24. Report refusal and loss counts, raw runs and event-unit calibration.

<a id="D37c6"></a>

#### D37.c6: Check test-access metadata and functional isolation
- Phases: Start work in P07. Accept this cell in P07.
- Must pass first: D37.c1, D34.c3, D27.c8.
- Baseline: Use the baseline stated in the rule when a comparison applies.
- Summary: Test exact test-access connectivity and metadata and mandatory functional isolation without physical assurance. Require 30 legal and 30 mode, reset and protected-state violations per interface.
- Rule:
  1. Check test-access metadata and isolation under #198, #200, #208 and #211.
  2. Cover TAP chains, resets and instruction lengths, scan and test enable, memory dimensions, ports and clocks, and MBIST and repair interfaces.
  3. Require 30 legal and 30 mode, reset and protected-state violations per interface.
  4. Require exact connectivity and metadata and mandatory functional isolation.
  5. Provide no BIST insertion, manufacturing or physical assurance.

<a id="D38c4"></a>

#### D38.c4: Integrate native compiler scheduling descriptions
- Phases: Start work in P06. Accept this cell in P06.
- Must pass first: D38.c2, D21.c1, D27.c8, D38.c3 (explanatory context only; no acceptance evidence).
- Baseline: Use the baseline stated in the rule when a comparison applies.
- Summary: Test native compiler integration and held-out kernels without claiming final compiler-quality comparisons early. Require at least 20 fresh kernels per instruction-resource class.
- Rule:
  1. For #367 and #369, integrate generated scheduling descriptions into two native LLVM and GCC versions and held-out kernels.
  2. Independently check parsed compiler resource and latency tables and legal generated code against full RTL anchors.
  3. Require at least 20 fresh kernels per instruction-resource class.
  4. Require exact outputs and legality.
  5. Reject all wrong-schedule and stale-model controls.
  6. Report code-cycle error, scheduling-choice error, construction hours and maintenance hours separately.
  7. Use existing compiler-quality bounds from the sealed D38.c3 interface without claiming those final comparison receipts early.
  8. Use D38.c3 as explanatory context in the predecessor column.
  9. Use the sealed D38.c3 interface and quality bounds at P06.
  10. Do not require the final comparison receipt early.
  11. Do not claim the final comparison receipt early.

## M4: Integrate engines and durable workflows

Acceptance phases: P08–P10.

<a id="D01c3c"></a>

#### D01.c3c: Qualify independent full-system RTL anchors for every required many-hart size without early-route partitioning
- Phases: Start work in P07. Accept this cell in P08.
- Must pass first: D01.c3b, D21.c1; independent RTL anchors, D27.c8.
- Baseline: Use independent full-system RTL timing anchors.
- Summary: Test independent full-system RTL anchors for every required many-hart size without early-route partitioning. For each 8, 16, 32 and 64-hart child, use independent full-system RTL timing anchors.
- Rule:
  1. For each 8, 16, 32 and 64-hart child, use independent full-system RTL timing anchors.
  2. Match topology, coherence, devices and traffic between each anchor and its model.
  3. Use at least 20 held-out topology, coherence and traffic points per size.
  4. Include bandwidth saturation and cross-hart interference.
  5. Check complete trace ends, order and outputs.
  6. Never use the detailed model as the RTL truth.
  7. Inject 20 shared-fabric errors into both related models.
  8. Require anchors to reject all injected errors.
  9. Use model-to-model direction as diagnostic evidence only.
  10. Apply Section 3.4 to generated fallback systems.
  11. Label their results as generated-system timing capacity.
  12. Produce anchors with hierarchical full-system RTL builds and independent functional retirement checks.
  13. Produce this early route without partitioning.
  14. Keep partitioned anchors as a separate acceptance child after the distributed simulation feasibility receipt.
  15. For 32 and 64 harts, distribute independent traffic points across Kubernetes.
  16. Reuse only hash-identical cold builds.
  17. Execute all at least 20 full-topology points with exact trace-end checks.
  18. Require complete suffix validation for checkpoints.
  19. Reduced hart counts and detailed-model timing cannot supply anchors.
  20. Report checked anchor wall time per point.
  21. Report checked anchor core-hours per point.
  22. Keep demand shortages OPEN.

<a id="D01c10"></a>

#### D01.c10: Description-first model and RTL configuration agreement before independent extraction
- Phases: Start work in P07. Accept this cell in P08.
- Must pass first: D01.c7, D05.c1, D27.c8.
- Baseline: Use the later independent RTL inventory.
- Summary: Test description-first model and RTL configuration agreement before independent extraction. Require at least 20 missing, reversed and default mutants per field family to refuse.
- Rule:
  1. Produce both model configuration and RTL parameter and adapter configuration from one sealed machine description.
  2. Do this on three unrelated lineages before RTL extraction.
  3. Require exact agreement of every declared field, unit and unsupported range.
  4. Require at least 20 missing, reversed and default mutants per field family to refuse.
  5. Compare with the later independent RTL inventory.
  6. Permit no result-driven correction.

<a id="D02c2"></a>

#### D02.c2: Useful prediction intervals and transfer across generations for direct open-suite advice
- Phases: Start work in P07. Accept this cell in P08.
- Must pass first: D02.c1; D01.c1 baseline class; separate from synthetic CI calibration, D27.c8, the explanatory context in D28.c3a.
- Baseline: Use the D01.c1 baseline class. Keep this separate from synthetic confidence-interval calibration.
- Summary: Test useful prediction intervals and transfer across generations for direct open-suite advice. Require adjusted coverage bounds between 0.94 and 0.98, inclusive.
- Rule:
  1. Use nominal 95% prediction intervals.
  2. Require adjusted coverage bounds between 0.94 and 0.98, inclusive.
  3. Require median interval width at most the preregistered smallest useful effect in the endpoint units.
  4. Require 95th-percentile width at most 2 times the preregistered smallest useful effect in the endpoint units.
  5. Report the unconditional admitted-and-covered fraction.
  6. Report abstentions and errors after reveal.
  7. Maintain these requirements through three sealed structural generations.
  8. Cover predictor and recovery, issue and queue, and memory and translation, including interaction.
  9. Require error on two oversized held-out configurations at most 1.5 times concurrent in-envelope error.
  10. Check twelve ideal and component modes on 20 microbenchmarks.
  11. Compare fidelity, coverage, width, yield, direction and effort under Section 3.1.
  12. Apply the .98 upper coverage cap only to useful model prediction intervals.
  13. It is not an upper cap on conservative statistical confidence coverage in the explanatory context in D28.c3a.
  14. Limit this receipt to direct open-suite inputs only.
  15. It must refuse proxy advice.
  16. Keep the proxy route as a separate acceptance child.

<a id="D02c3"></a>

#### D02.c3: Search-method benefit and safe pruning against random and grid baselines at sealed budgets
- Phases: Start work in P07. Accept this cell in P08.
- Must pass first: D02.c1, D01.c3a, D01.c3b, D21.c1, D27.c8.
- Baseline: Use frozen random and grid search at equal total checked cost.
- Summary: Test search-method benefit and safe pruning against random and grid baselines at sealed budgets. Require regret at most the preregistered smallest useful effect in the endpoint units divided by 4.
- Rule:
  1. Select among Bayesian optimisation with uncertainty acquisition, multi-objective NSGA-II, active learning and multi-fidelity promotion.
  2. For multi-fidelity promotion, use analytical, then interval, then detailed, then RTL stages.
  3. Freeze random and grid search as baselines.
  4. Per mechanism and distance, use at least 30 independent sealed search spaces.
  5. Use model-evaluation budgets of 32, 128 and 512 per space.
  6. Use RTL-confirmation budgets of 8, 32 and 128 per space.
  7. Keep each budget as a separate child.
  8. Expand independent spaces for power.
  9. Seal checked cycle cost, fidelity and scripted checked time objectives before reveal.
  10. Seal feasibility and selection before reveal.
  11. Use no physical objective.
  12. At equal total checked cost, require non-inferior regret, direction and yield under Section 3.1.
  13. Against each baseline, require secondary lower useful accepted decisions per evaluation ratio at least 1.10.
  14. Re-evaluate all cheap-tier rejects in hidden detailed and RTL controls.
  15. Require exact mandatory winner retention.
  16. Require pruning-loss upper bound at most .005.
  17. Require regret at most the preregistered smallest useful effect in the endpoint units divided by 4.
  18. Count failed and pruned candidates.
  19. Count all fidelity-handoff costs.
  20. Permit no result-dependent budget change.

<a id="D05c5"></a>

#### D05.c5: The full editor feature inventory, generated documents and separate PSS and e-language authoring obligations
- Phases: Start work in P08. Accept this cell in P08.
- Must pass first: D05.c1, D05.c3, D05.c1, D27.c8, the explanatory context in D29.c2.
- Baseline: Use Sigasi and DVT document flows and DVT authoring tasks as specified below.
- Summary: Test the full editor feature inventory, generated documents and separate PSS and e-language authoring obligations. Require preview-refresh 95th-percentile at most 2 s for supported incremental cases.
- Rule:
  1. Seal the feature inventory from pinned Sigasi, DVT and Metals feature lists and generator needs.
  2. Include live elaboration preview, parameter-space browsing, structural and schematic editing, and semantic hardware-type highlighting.
  3. Include Area and Bundle hierarchy refactoring, source, type and driver navigation, and stopped-generator inspection.
  4. Require independent positive, invalid, stale and boundary expected outcomes for each feature and language child.
  5. Permit no missing feature or wrong accepted edit.
  6. Require preview-refresh 95th-percentile at most 2 s for supported incremental cases.
  7. Keep the index deadline for full refresh.
  8. Generate microarchitecture pipeline and interface documents from the database beyond CSR documentation.
  9. Check at least 100 independently known stage and interface facts on each of three lineages.
  10. Require exact IDs, timing, handshake and unknown fields.
  11. Require 20 stale, omitted and reversed-edge controls to refuse publication.
  12. Compare document construction and update effort against Sigasi and DVT flows under Section 3.1.
  13. Create separate PSS and e-language authoring task children.
  14. Cover parsing, constraint navigation, references, semantic refactoring, generated-test joins and failure recovery.
  15. Apply the explanatory context in D29.c2 to every applicable host, access and skill child.
  16. Per task and language, use at least 50 legal cases.
  17. Per task and language, use at least 50 invalid or stale cases.
  18. Require exact semantic preservation.
  19. Require zero wrong edits.
  20. Runtime interoperability receipts cannot close editor tasks.
  21. Freeze the denominator from the D05.c1 explanatory edit-family inventory before implementation.
  22. Count unsupported cases as failures.
  23. Permit no post-result support subset.
  24. Require all CPU-REQUIRED feature children for the Qualified CPU tier.
  25. Keep CPU-LOW-RELEVANCE feature children visible as OPEN until their own receipts pass.
  26. Require those children for a whole-vendor feature claim.
  27. Apply V26 independent task witnesses before results to each feature, including PSS and e-language tasks.
  28. Engine limits or failed controls cannot justify a low-relevance label.
  29. Compare verified completion, scripted checked time and completion tails with DVT for each PSS and e-language authoring task under Section 3.1.

<a id="D06c1"></a>

#### D06.c1: Safe semantic edits and per-release diagnostic correctness across every required language and design class
- Phases: Start work in P09. Accept this cell in P09.
- Must pass first: D05.c1, D07.c1; D15.c3 only for SEC labels, D27.c8.
- Baseline: Use the baseline stated in the rule when a comparison applies.
- Summary: Test safe semantic edits and per-release diagnostic correctness across every required language and design class. Require zero wrong accepted edits.
- Rule:
  1. Seal 100 edits per design class and language.
  2. Cover rename and shadowing, hierarchy extraction, split ports, type and width, parameters and generics, pipelines and queues.
  3. Cover reset and domain edits, foreign boundaries and cross-file moves.
  4. Include module, interface, modport, package, VHDL entity, record and generate, macros and conditional elaboration.
  5. Include at least 30 functional edits.
  6. Include 20 generator failures.
  7. Require zero wrong accepted edits.
  8. Independently validate state, output and property changes.
  9. Require SEC proof where claimed.
  10. For the per-release machine gate, freeze at least 100 edit cases per language and design class.
  11. Include rename, hierarchy move, width change and generator parameter change.
  12. Independently check expected diagnostics, source joins and refactor SEC.
  13. Require zero wrong joins.
  14. Require zero accepted inequivalent refactors.
  15. Require 100% of required diagnostics.
  16. For SV and VHDL, require 95th-percentile incremental diagnostic latency at most 2 s.
  17. For generators, require 95th-percentile incremental diagnostic latency at most 30 s.
  18. Replay each release.

<a id="D06c2"></a>

#### D06.c2: Feedback latency, cache correctness and complete lint-class coverage against qualified commercial tools
- Phases: Start work in P10. Accept this cell in P10.
- Must pass first: D06.c1; raw build and lint logs, D27.c8.
- Baseline: Use qualified SpyGlass and applicable Questa Lint on the same designs.
- Summary: Test feedback latency, cache correctness and complete lint-class coverage against qualified commercial tools. Require width and domain feedback 95th-percentile at most 2 s.
- Rule:
  1. Require width and domain feedback 95th-percentile at most 2 s.
  2. Require first checked cycle 50th-percentile at most 30 s.
  3. Require first checked cycle 95th-percentile at most 90 s.
  4. Require exact clean and cached state and output.
  5. Reject all 30 invalidation mutants.
  6. Seal an independent lint inventory from standards, qualified commercial rule classes and public escapes.
  7. Set rule count to the full independent mandatory-class inventory.
  8. Use at least 20 positive cases per class.
  9. Use at least 20 negative cases per class.
  10. Apply no fixed 60-rule ceiling.
  11. Cover 100% of mandatory classes.
  12. Require at most 5% independently dismissed findings on three real designs.
  13. Compare lint breadth and finding correctness with qualified SpyGlass and applicable Questa Lint on the same designs under Section 3.1.
  14. Compare inventory-class coverage, sensitivity, dismissal rate, analysis time and repair effort.
  15. Block acceptance for exact mandatory rule misses.
  16. Rule aliases do not add breadth.
  17. Include Spinal and Chisel conditional latch inference as a mandatory generator lint class.
  18. Include implicit and explicit width truncation.
  19. Include uninitialized hardware.
  20. Include clock and reset crossing.
  21. Include elaboration-versus-runtime confusion.
  22. Count each class separately with exact source-level diagnostics.

<a id="D06c90"></a>

#### D06.c90: Every issue-specific obligation in D06.c90 with its required exact evidence, comparisons and refusal controls
- Phases: Start work in P10. Accept this cell in P10.
- Must pass first: D06.c1, D27.c2, D27.c8.
- Baseline: Use the baseline stated in the rule when a comparison applies.
- Summary: Test every issue-specific obligation in D06.c90 with its required exact evidence, comparisons and refusal controls. Require all 7 numbered rule items.
- Rule:
  1. Apply I90, the source-specific issue-child evidence protocol.
  2. For issue #28, return exact changed ports, state, connections and behavior from semantic design differences on sealed edits.
  3. Include no-change cases and equivalent refactors.
  4. For issue #74, measure cold and incremental builds and checked runs with matched instrumentation.
  5. Retain losses.
  6. Reject stale-cache gains.
  7. Apply I90 to both issue children.

<a id="D06c5"></a>

#### D06.c5: Exact generated-RTL semantic differences and stable explanations at both source levels
- Phases: Start work in P10. Accept this cell in P10.
- Must pass first: D06.c1, D15.c3, D27.c8.
- Baseline: Use the baseline stated in the rule when a comparison applies.
- Summary: Test exact generated-RTL semantic differences and stable explanations at both source levels. Require zero invented or deleted effects.
- Rule:
  1. Test semantic generated-RTL differences on 100 independently sealed edits per language.
  2. Include hierarchy, state, connectivity, parameter, reset, retiming, equivalent renaming and behavior edits.
  3. Require exact independently specified changed-object sets.
  4. Require exact independently specified changed-relation sets.
  5. Require zero invented or deleted effects.
  6. Explain changes at generator and RTL levels with stable IDs.
  7. Keep unknown behavioral equivalence unknown.
  8. Require proof for an equivalence label.

<a id="D06c6"></a>

#### D06.c6: Qualify parameterized components with independently checked proofs, integrations and invalid-reuse controls
- Phases: Start work in P10. Accept this cell in P10.
- Must pass first: D06.c1, D15.c3, D37.c1, D27.c8, the explanatory context in D30.c1.
- Baseline: Use the baseline stated in the rule when a comparison applies.
- Summary: Test parameterized components with independently checked proofs, integrations and invalid-reuse controls. Require SEC across two generator upgrades.
- Rule:
  1. Provide a verified parameterized component library with generators, contracts, examples and proof certificates.
  2. Include synchronous and asynchronous FIFOs, arbiters, CAMs, free lists, age matrices, credit counters and synchronizers.
  3. Require a positive unbounded proof or independently checked cutoff theorem under R04 (independent requirement-derived expectations with distinct authors and recorded ancestry) for each declared width, depth, port and domain range.
  4. Sampled small instances never prove a range.
  5. Prove safety.
  6. Prove progress under explicit fairness.
  7. Prove reset, wrap and credit conservation.
  8. Prove domain assumptions.
  9. Independently check and replay certificates.
  10. Compose certificates as assume-guarantee lemmas in two unrelated target integrations using D30.c1 interface adapter contracts.
  11. Require SEC across two generator upgrades.
  12. Require 20 activated contract, parameter and certificate mismatches per component to invalidate reuse.
  13. Prove only digital abstraction for synchronizers, not analog metastability probability.

<a id="D06c11"></a>

#### D06.c11: Qualify incremental elaboration correctness and latency with explicit cache-reuse rejection and fallback rules
- Phases: Start work in P08. Accept this cell in P08.
- Must pass first: D05.c1, D05.c3, D27.c8.
- Baseline: Use cold full rebuild for correctness only, never as a passing incremental receipt.
- Summary: Test incremental elaboration correctness and latency with explicit cache-reuse rejection and fallback rules. Require zero stale identities.
- Rule:
  1. Decide the incremental elaboration method IE27 for Spinal and Chisel separately.
  2. Seal 100 edits per language at 1 million signals.
  3. Require full-rebuild equality.
  4. Require zero stale identities.
  5. On the frozen edit distribution, require first-prototype compilation 95th-percentile at most 10 s.
  6. Require elaboration 95th-percentile at most 20 s.
  7. Require total 95th-percentile at most 30 s.
  8. Reject cache reuse for a hidden global dependency.
  9. After two failed iterations, redirect to persistent elaboration workers and demand-driven compiler IR updates.
  10. Retain cold full rebuild as a checked fallback.
  11. Never use cold full rebuild as a passing incremental receipt.

<a id="D07c1"></a>

#### D07.c1: Qualify integrated simulation only after the kernel method receipt and every exact language gate pass
- Phases: Start work in P08. Accept this cell in P08.
- Must pass first: D07.c4, D31.c1, D07.c13, D07.c9, D27.c8. D13.c1 supplies explanatory context only. Full D13.c1 acceptance is not a prerequisite.
- Baseline: Use the baseline stated in the rule when a comparison applies.
- Summary: Test integrated simulation only after the kernel method receipt and every exact language gate pass. Require zero semantic mismatches.
- Rule:
  1. Accept integrated simulation semantics only after the kernel method receipt and every exact language gate pass.
  2. Require zero semantic mismatches.
  3. Implement X, Z and driver resolution, event regions, timing, classes, constraints, covergroups, simulation SVA and foreign calls.
  4. Require one open path to run the whole flow.
  5. Partial engines cannot be combined into a fictitious complete path.
  6. Use exact clause tests from D31.c1.
  7. Require the four-state event-kernel method decision receipt before integrated semantic acceptance.
  8. Method approval cannot replace any language-semantic test.

<a id="D07c3"></a>

#### D07.c3: Qualify enabled acceleration options with independent ablations and complete support for any winning GPU backend
- Phases: Start work in P09. Accept this cell in P09.
- Must pass first: D07.c1; D07.c4 pins predecessor source and build and options; upstream same-job runs, D27.c8, the explanatory context in D31.c3.
- Baseline: Use independent ablations and upstream runs of the same job with pinned D07.c4 source, build and options.
- Summary: Test enabled acceleration options with independent ablations and complete support for any winning GPU backend. For each enabled option, require lower rate ratio at least 1.05 or upper build ratio at most 0.95 on its target stratum.
- Rule:
  1. Run independent ablations for dependency partitioning, multithread scheduling, PGO/LTO, code locality and incremental compilation.
  2. For each enabled option, require lower rate ratio at least 1.05 or upper build ratio at most 0.95 on its target stratum.
  3. Compare each option on other strata under Section 3.1.
  4. Disable unhelpful options.
  5. Preserve results.
  6. Require exact unchanged events and outputs.
  7. Declare external gate-netlist and SDF capability without physical generation.
  8. Test advertised replay in the explanatory context in D31.c3.
  9. If a GPU candidate wins sealed semantic, rate and cost selection, deliver its backend.
  10. If a GPU candidate wins sealed semantic, rate and cost selection, maintain its backend through the complete runtime, UVM and debug matrix and upgrades.
  11. A winning prototype alone cannot close acceleration support.

<a id="D07c90"></a>

#### D07.c90: Every issue-specific obligation in D07.c90 with its required exact evidence, comparisons and refusal controls
- Phases: Start work in P09. Accept this cell in P09.
- Must pass first: D07.c1, D27.c2, D27.c8.
- Baseline: Use fresh processes, independent references and confirmed native target comparisons as specified below.
- Summary: Test every issue-specific obligation in D07.c90 with its required exact evidence, comparisons and refusal controls. Require 20 unsupported-lowering and missing-accessor controls to refuse.
- Rule:
  1. Apply I90, the source-specific issue-child evidence protocol.
  2. For issue #14, match persistent runs to fresh processes for state, output, seed and isolation.
  3. For issue #116, reject backend requests outside declared semantics with status.
  4. For issue #126, preserve callbacks, assertions and outcomes on unchanged cocotb benches.
  5. For issue #295, require the whole open runtime to satisfy the complete clause inventory and both named simulator comparisons.
  6. For issue #345, pin native circt-verilog, slang and Arcilator.
  7. Lower captured RTL.
  8. Implement reset, clock, memory, RVFI, C1 run-result and C2 trace accessors.
  9. Use small targets, then existing medium and large OoO targets.
  10. Require exact complete terminal C2 against the reference before rate comparison.
  11. Require 20 unsupported-lowering and missing-accessor controls to refuse.
  12. Separate compilation from execution.
  13. Draft confirmed upstream defects only.
  14. For issue #344, capture exact thread and compiler PGO bytes.
  15. Capture training ELF, RTL, tool, flags and hierarchy-bridge boundaries.
  16. Require 20 stale, PROFOUTOFDATE and boundary mutants to refuse.
  17. Use fresh alternating held-out pairs on existing medium and large targets.
  18. Compare flat, thread, split and hierarchy builds.
  19. Require bit-identical complete C2.
  20. Report build seconds, peak resident memory and execution kHz separately.
  21. Independently confirm the winner before opt-in.
  22. Draft upstream reproducers only.
  23. Apply I90 to every issue child.

<a id="D08c1"></a>

#### D08.c1: Complete serializable state, exact restores and qualified cross-engine checkpoint portability
- Phases: Start work in P09. Accept this cell in P09.
- Must pass first: D09.c1, D07.c1, independent device and reset harness, D27.c8.
- Baseline: Use uninterrupted destination runs and an independent complete-state inventory.
- Summary: Test complete serializable state, exact restores and qualified cross-engine checkpoint portability. Reject 20 corrupt or missing fields.
- Rule:
  1. Serialize DUT, memory, scheduler, random-number generator, stimulus and devices.
  2. Test 100 cross-process suffix-identical restores.
  3. Reject 20 corrupt or missing fields.
  4. Reject 10 combined omissions.
  5. Run 1,000 branches at 100 points.
  6. Require resident-memory growth at most 5% in a 72-hour soak.
  7. Require restore launch-to-region-of-interest gain at least 5 times.
  8. Require checkpoint spacing at most 1 million DUT cycles plus every region of interest.
  9. Retain at most 1 TiB of checkpoints, deltas and index per 1 billion cycles.
  10. Report the original trace separately.
  11. Use an independent complete-state inventory.
  12. For the cross-engine child, transfer two-state Verilator fast-forward to the four-state and UVM engine at region of interest and back.
  13. Pin a versioned complete state, scheduler, foreign-state and random-number-generator schema.
  14. Use at least 100 checkpoints per design and state stratum.
  15. Require suffix-identical events and architectural outputs against uninterrupted destination runs.
  16. Require 20 hidden-state, region, X-origin, device and callback omissions to refuse restore.
  17. Keep unrepresentable states as explicit unsupported children.
  18. Never fabricate X values.
  19. Require all declared source and destination pairs for full advertised portability.

<a id="D08c2"></a>

#### D08.c2: Sampling weights, warmup convergence, cycle accuracy and checked long-job deadlines
- Phases: Start work in P10. Accept this cell in P10.
- Must pass first: D08.c1, D21.c1; no functional work counted as RTL, D27.c8.
- Baseline: Use full anchors and complete VCS and Xcelium jobs.
- Summary: Test sampling weights, warmup convergence, cycle accuracy and checked long-job deadlines. Require BBV and SimPoint weights within 0.5 percentage point of full anchors.
- Rule:
  1. Require BBV and SimPoint weights within 0.5 percentage point of full anchors.
  2. Require their sum within 1e-6 of full anchors.
  3. Double warmup until drift is at most 1%.
  4. Fail if convergence does not occur by 1 billion warmup instructions or 24 h.
  5. Require total-cycle error at most 2% per class.
  6. Apply R07 (preregistered statistical validity and joint-power rules) statistical rules to small deltas.
  7. Complete boot and shell plus checked SQLite region of interest in less than 8 h.
  8. Complete actual 1 billion dependent checked RTL retirements in at most 48 h.
  9. Report longer production tails.
  10. Compare complete jobs against VCS and Xcelium under Section 3.1.

<a id="D08c90"></a>

#### D08.c90: Every issue-specific obligation in D08.c90 with its required exact evidence, comparisons and refusal controls
- Phases: Start work in P10. Accept this cell in P10.
- Must pass first: D08.c1, D27.c2, D27.c8.
- Baseline: Use original reference and RTL continuations and uninterrupted execution as specified below.
- Summary: Test every issue-specific obligation in D08.c90 with its required exact evidence, comparisons and refusal controls. Require 20 independent continuations per profile to match the original reference and RTL exactly.
- Rule:
  1. Apply I90, the source-specific issue-child evidence protocol.
  2. For issue #56, pin QEMU, OpenSBI and Buildroot.
  3. Require boot outputs and real RTL handoff to agree.
  4. For issue #132, require restored state to yield suffix-identical event and output histories.
  5. For issue #182, require stress agents to obey controller and NoC ordering, backpressure and fairness under saturation.
  6. For issue #183, reproduce full-run phases with weighted samples within owning accuracy budgets.
  7. For issue #191, replay exact prior state and source identity on reverse-step.
  8. For issue #213, validate DRAM-adapter units, bank and rank maps, refresh, ordering and model-version handshake.
  9. Reject invalid contracts.
  10. For issue #350, use separate FP, privilege and VM profiles.
  11. Preserve raw f0, FPR, NaN-box, fcsr, satp, PMP and page RAM.
  12. Invalidate TLB.
  13. Check A/D and fault continuations.
  14. Include the complete device, IRQ, timer, stimulus and pseudorandom-number-generator envelope.
  15. Require 20 independent continuations per profile to match the original reference and RTL exactly.
  16. Refuse unmodeled I/O.
  17. Qualify Spike before the QEMU exporter.
  18. Keep multihart unsupported until a separately checked global-boundary and order contract exists.
  19. For issue #348, hold the interval from start position S through start position S plus length L fixed, excluding the final position.
  20. For each warmup length W, capture at the fixed start position S minus W.
  21. Verify the architectural suffix first.
  22. On a cached learned-predictor target, measure signed CPI bias with paired random-memory seeds and fixed timing.
  23. Require chosen-warmup adjusted absolute bias at most 1%.
  24. Also require that bias at most the preregistered smallest useful effect in the endpoint units divided by 4.
  25. Weight CPI by instruction count.
  26. Never average IPC.
  27. Keep uncached VexRiscv startup separate.
  28. Mark a missing counter or baseline inconclusive.
  29. For issue #347, use RV32IM M-mode RAM-only rvw.arch-checkpoint/1 at checkpoint position K more than 0.
  30. Preserve all GPRs, PC, profile CSRs and RAM.
  31. Require fresh Spike and adapter-plugin RTL restores to read back state before fetch at a nonreset PC.
  32. Require exact retirements equal to warm-up count W plus interval length L versus the original continuation on 20 load, store, branch and CSR cases.
  33. Require GPR, CSR and RAM corruption, short-trace, timeout and unsupported-adapter controls to refuse.
  34. Sample completion never means program PASS.
  35. For issue #346, serialize quiescent fresh-process scheduler time, clock phase, RAM, pending transactions and random-number-generator state.
  36. Serialize devices, IRQ, monitor and RVFI counters.
  37. At 20 boundaries each on VexRiscv and an existing medium OoO target, require byte-exact C2 suffix against uninterrupted execution.
  38. Require exact terminal counters against uninterrupted execution.
  39. Require 20 stale, corrupt and external-I/O controls to refuse.
  40. Measure save and restore seconds.
  41. Measure bytes and amortized checked throughput.
  42. Apply I90 to every issue child.

<a id="D13c1"></a>

#### D13.c1: Check complete UVM and SystemVerilog semantics
- Phases: Start work in P09. Accept this cell in P09.
- Must pass first: D07.c1 SV mechanisms; D31.c1 expectations, D27.c8.
- Baseline: Use the baseline stated in the rule when a comparison applies.
- Summary: Test the correctness of complete UVM and SystemVerilog semantics. Pin IEEE 1800.2-2020, the Accellera reference commit and the IEEE 1800-2023 SV denominator.
- Rule:
  1. Pin IEEE 1800.2-2020, the Accellera reference commit and the IEEE 1800-2023 SV denominator.
  2. Independently map each required API and clause to positive and defined negative tests.
  3. Run at least 50 cases per complex family.
  4. Cover the complete factory, configuration and resource semantics.
  5. Cover phases, objections and drain semantics.
  6. Cover sequence arbitration and virtual sequences.
  7. Cover TLM, callbacks, reports and catchers.
  8. Cover RAL aliases, prediction, frontdoor and backdoor access.
  9. Cover constraint inheritance, arrays, uniqueness, conditional, soft and inline constraints.
  10. Cover solve-before, distribution, randc and unsatisfiable explanations.
  11. Require exact small-domain solution sets.
  12. Use powered tests for larger distributions.
  13. Cover covergroups, crosses, illegal and ignore bins, transitions and per-instance persistence.
  14. Cover assertions and vacuity.
  15. Allow no mandatory waiver.

<a id="D13c2"></a>

#### D13.c2: Run unchanged UVM benches and compare vendor flows
- Phases: Start work in P10. Accept this cell in P10.
- Must pass first: D13.c1; feature total frame frozen before engine selection, D27.c8.
- Baseline: The same benches on VCS and Xcelium.
- Summary: Test unchanged UVM execution, protocol checks and migration against both vendor flows. Require at least one path to support the whole flow.
- Rule:
  1. Run the unmodified pinned UVM library and three independently chosen complex CPU benches through two simulator and UVM upgrades.
  2. Test two open paths where advertised.
  3. Require at least one path to support the whole flow.
  4. Provide VIP for TileLink and AXI, IRQ and debug, deterministic memory and an RVFI scoreboard.
  5. Run 30 legal cases per protocol.
  6. Run 30 illegal, reset and error cases per protocol.
  7. An error report, scoreboard failure or assertion failure must fail C1, C3 and C4 even without process exit.
  8. Require exact semantic equality.
  9. Use the statistical comparison in section 3.1 for valid completion and total migration and upgrade effort versus same benches on VCS AND Xcelium.
  10. Use pyuvm and cocotb as additional paths only.

<a id="D13c90"></a>

#### D13.c90: Check source-specific UVM issues
- Phases: Start work in P10. Accept this cell in P10.
- Must pass first: D13.c1, D27.c2, D27.c8.
- Baseline: Use the baseline stated in the rule when a comparison applies.
- Summary: Test the correctness of source-specific UVM issues. For #296, require that one complete open SV UVM path runs the full pinned UVM inventory and both vendor comparisons, without substituting pyuvm.
- Rule:
  1. Apply I90, the source-specific issue protocol, to these issue requirements: #178 unchanged SV UVM benches retain phases, factory, sequences, callbacks, coverage and objections.
  2. For #296, require that one complete open SV UVM path runs the full pinned UVM inventory and both vendor comparisons, without substituting pyuvm.
  3. Apply the complete I90 protocol.
  4. Import issue #378 as an I90 child for a CORE-V-VERIF design study of agents, scoreboards, ISS links, interrupts, debug, test plans, coverage and regression.
  5. Record measured open-simulator support separately from commercial requirements.
  6. Require a reuse map, a docs/design note and a disposition for every proposal.
  7. Plan follow-up issues for accepted proposals without opening them in this roadmap task.

<a id="D14c3"></a>

#### D14.c3: Check coverage interchange and PSS scenario interchange
- Phases: Start work in P10. Accept this cell in P10.
- Must pass first: D14.c1, D13.c1 coverage semantics, D27.c8, D14.c7 as explanatory context only.
- Baseline: IMC.
- Summary: Test the correctness of coverage interchange and PSS scenario interchange. Require 100% of advertised bin identities and source relations round-trip exactly, including exclusions, configuration changes and hierarchy.
- Rule:
  1. Require IMC-class code and functional and assertion coverage and UCIS: exact bin and hit and source and exclusion and attempt and vacuity and failure semantics or checked conversion.
  2. Require 100% of advertised bin identities and source relations round-trip exactly, including exclusions, configuration changes and hierarchy.
  3. Report unsupported mappings as separate unsupported feature cells.
  4. Keep all mandatory unmapped points open.
  5. Run 100 merge and upgrade cases.
  6. Run 30 stale, corrupt and exclusion negative controls.
  7. Require zero denominator loss.
  8. Require zero double merges.
  9. Use the statistical comparison in section 3.1 for merge and query and closure time and real-defect sensitivity versus IMC.
  10. Require PSS reuse and scenario IR choice: 20 action and resource and constraint and dependency round trips with exact logical model and RTL outcomes, distinct timing.
  11. This cell qualifies interchange.
  12. Keep complete PSS generation mandatory under D14.c7.
  13. Treat the D14.c7 reference here as explanatory context only.
  14. Include all independently inventoried action and resource and constraint and dependency constructs.
  15. Treat 20 round trips as bootstrap.
  16. Require positive and negative semantic controls for every advertised construct.
  17. Require that full generation claims require the planned qualified full-inventory receipt.

<a id="D14c8"></a>

#### D14.c8: Check self-checking multihart exercisers
- Phases: Start work in P10. Accept this cell in P10.
- Must pass first: D14.c1, D12.c1, D11.c1, D27.c8.
- Baseline: A qualified Threadmill-class flow.
- Summary: Test the correctness of self-checking multihart exercisers. Require zero false passes.
- Rule:
  1. Use Threadmill-class self-checking bare-metal multihart exercisers.
  2. Emit embedded result checks without a lockstep reference.
  3. For each ordering family and each state family, run at least 100 legal cases on two targets.
  4. For each such family, run at least 100 activated defect cases on those targets.
  5. Include reset and exception races.
  6. Compare embedded verdicts with independent complete truth for the obligations described in D11.c1 and D12.c1.
  7. Treat those references as explanatory context only.
  8. Require zero false passes.
  9. Require zero wrong failures.
  10. Detect all mandatory errors.
  11. Use the statistical comparison in section 3.1 for generation and closure time and effort against qualified Threadmill-class flow.

<a id="D15c5"></a>

#### D15.c5: Qualify formal grid and single-host benefit
- Phases: Start work in P10. Accept this cell in P10.
- Must pass first: D15.c2, D23.c1, D26.c1, D15.c11; planning interface before full D24.c1 as explanatory context only service, D27.c8.
- Baseline: JasperGold and VC Formal grid modes and equal-core-hour single-host runs.
- Summary: Test adjusted checked-result-time upper ratio at most 0.90 against each JasperGold and VC Formal at equal core-hours.
- Rule:
  1. Accept formal benefit only with the required method receipt and both vendor comparisons.
  2. Require distributed proof grid on Kubernetes and community compute: engine portfolios across Yosys and SBY and ABC and pono and rIC3 and avy and EBMC, property partitioning, dependency scheduling and checked lemma and proof caching and sharing.
  3. Require grid sizes 1, 8, 64, 512 nodes, 16 cores per node.
  4. At each size freeze identical property and assumption sets and equal total core-hour budgets versus JasperGold AND VC Formal grid modes.
  5. Use the statistical comparison in section 3.1 for solved fraction, checked time, total core-hours, resident memory and storage and construction and debug effort.
  6. Report full strong and weak scaling curves and first unsolved size.
  7. For independent scalable property sets, require strong-scaling efficiency at least 60% to 64 nodes.
  8. For those sets, require strong-scaling efficiency at least 50% to 512 nodes.
  9. Include scheduling, transport and certificate checking in both measurements.
  10. Report single dependent proof latency separately.
  11. Include RTL, assumptions, engine, kernel and proof relation in cache keys.
  12. Run 100 invalid lemma, poisoned cache, wrong-assumption, worker-loss, duplicate and partition controls.
  13. Require exactly zero false accepts.
  14. Do not publish stale results.
  15. Every reused lemma must have an independently checked under the independence protocol R04 certificate or replay.
  16. Quarantine untrusted community results.
  17. Require that three upstream and RTL generations retain sound sharing and invalidation.
  18. Keep other application and swarm superiority endpoints secondary.
  19. Require that all exact, positive-proof and non-inferior gates remain required.
  20. Every route requires the open formal-engine architecture decision receipt, including its redirect and transport controls.
  21. An existing independent engine also needs its own pinned architecture, native certificate checker, independent replay and no unsupported transport.
  22. Require that method approval never replaces positive proof or either vendor comparison.
  23. Reserve one half of the local route budget for the grid route and one half for an equal-core-hour single-host route before outcomes.
  24. On the single-host route compare both vendors at 1, 8 and 24 hours and 16, 64 and 256 GiB on identical properties and hardware.
  25. Apply the same Category 8 primary ratio, soundness and noninferiority gates.
  26. This narrower receipt says single-host formal benefit.
  27. It cannot close distributed scaling or the grid duty, which stays OPEN when vendor grid terms cannot match.
  28. Category 8 primary: Require adjusted checked-result-time upper ratio at most 0.90 against each JasperGold and VC Formal at equal core-hours.

<a id="D15c6"></a>

#### D15.c6: Compare simulation-seeded proof search
- Phases: Start work in P10. Accept this cell in P10.
- Must pass first: D15.c1, D08.c1, D17.c1; independent reset-reachable state inventory, D27.c8.
- Baseline: Reset-only formal, random starts, alternative state-selection methods, JasperGold state-swarm and comparable VC Formal recipes.
- Summary: Test the comparison of simulation-seeded proof search. Require the secondary upper checked-time ratio at most 0.90 versus reset-only formal.
- Rule:
  1. Require simulation-seeded start-state swarm with automatic seed selection and depth search.
  2. Seal 100 independently authored under the independence protocol R04 deep bugs in at least 10 unit classes plus 100 legal and no-bug controls, with bug depth 1 thousand and 100 thousand and 1 million cycles and independent activation witnesses.
  3. Compare state selection (coverage, distance, structural diversity), random starts and reset-only formal at equal core-hours.
  4. Also use the statistical comparison in section 3.1 against JasperGold state-swarm AND VC Formal comparable recipes that start from simulation.
  5. Replay exact detected counterexamples from reset on the original RTL.
  6. Do not allow arbitrary unreachable-state bug to count.
  7. Use time-to-valid-bug, detection yield, scripted setup time and core-hours as endpoints.
  8. Require the secondary upper checked-time ratio at most 0.90 versus reset-only formal.
  9. Keep all other statistical endpoints noninferior against qualified commercial flows under section 3.1.
  10. Retain swarm depth-search curves and missed bugs.
  11. Label unreachability from sampled states as local only.
  12. Global proofs must still have reset coverage and induction.
  13. Reject 30 corrupted, incomplete or unreachable state snapshots.
  14. This supports superiority over reset-only only.
  15. A commercial state-swarm superiority label needs its own registered at most .90 secondary time bound against each named vendor.
  16. Noninferiority must never support a beats-vendor label.

<a id="D15c10"></a>

#### D15.c10: Prove C and C++ transaction refinement
- Phases: Start work in P10. Accept this cell in P10.
- Must pass first: D15.c3, D31.c1, D27.c8.
- Baseline: Qualified VC Formal DPV and applicable JasperGold C2RTL flows.
- Summary: Test proof of C and C++ transaction refinement. Pin C11 and C++17 subsets, integer and floating-point semantics, object lifetime, memory and alias rules and ABI.
- Rule:
  1. Require C/C++ transaction refinement (also #19): evaluate HW-CBMC/goto-cc, CBMC and Clang/LLVM translation on disjoint controls.
  2. Pin C11 and C++17 subsets, integer and floating-point semantics, object lifetime, memory and alias rules and ABI.
  3. Unsupported constructs explicitly refuse.
  4. Treat undefined behavior as an input error with an independent witness, never as proof success or silently assumed unreachable.
  5. Map function calls and returns to ready and valid transactions.
  6. Define persistent state, reset, byte memory, aliasing, permitted stuttering and latency and progress.
  7. Prove combinational, sequential and stateful or pipelined units.
  8. Run at least 50 positive controls per class.
  9. Run at least 50 violating controls per class.
  10. Include wider units, alias, reset and backpressure.
  11. Independently replay every counterexample.
  12. Check positive certificates or distinct encodings.
  13. Unsupported function types, UB and stale source negatives must refuse.
  14. Use the statistical comparison in section 3.1 for conclusive fraction, checked time, scripted construction time and debug effort versus qualified VC Formal DPV AND applicable JasperGold C2RTL flows.
  15. Retain existing floating-point and SEC checks.

<a id="D16c5"></a>

#### D16.c5: Qualify block refinement
- Phases: Start work in P09. Accept this cell in P09.
- Must pass first: D16.c1, D15.c3, D27.c8, D16.c3 as explanatory context only.
- Baseline: Use the baseline stated in the rule when a comparison applies.
- Summary: Test the qualification of block refinement. Qualify the QUALIFIED-BLOCK-REFINEMENT tier with unbounded refinement of LSU, TLB and cache block transactions on two unrelated targets.
- Rule:
  1. Qualify the QUALIFIED-BLOCK-REFINEMENT tier with unbounded refinement of LSU, TLB and cache block transactions on two unrelated targets.
  2. Check that refinement independently under R04, the independence protocol.
  3. Run at least 50 valid controls per block.
  4. Run at least 50 violating controls per block.
  5. Check reset, initiation, state and memory relation, progress and nonvacuity.
  6. Require an independent certificate or encoding replay.
  7. List the exact block boundary and assumptions in the receipt.
  8. It cannot close whole-core D16.c3 as explanatory context only.

<a id="D17c9"></a>

#### D17.c9: Qualify reusable unit scoreboards
- Phases: Start work in P10. Accept this cell in P10.
- Must pass first: D14.c1, D17.c1, D27.c8.
- Baseline: Use the baseline stated in the rule when a comparison applies.
- Summary: Test the qualification of reusable unit scoreboards. Require at least 50 valid and 50 fault controls per unit plus stale and version and partial-state negatives.
- Rule:
  1. Provide a versioned reusable unit-scoreboard library for LSU, TLB and caches.
  2. Use independent transition and ordering semantics.
  3. Use versioned request, response, state and reset adapters.
  4. Require exact agreement on every unit inventory described by D14.c1 as explanatory context only.
  5. Reuse unchanged generic code on two unrelated targets.
  6. Require at least 50 valid and 50 fault controls per unit plus stale and version and partial-state negatives.
  7. Require zero wrong verdicts.

<a id="D18c3"></a>

#### D18.c3: Qualify reverse replay
- Phases: Start work in P10. Accept this cell in P10.
- Must pass first: D18.c1, D08.c1, D27.c8, D18.c11.
- Baseline: The integrated Verdi workflow.
- Summary: Test the qualification of reverse replay. Require 100 hidden locations including just-before-checkpoint, cold storage and restart.
- Rule:
  1. Reverse 10 thousand cycles with 95th-percentile latency at most 60 s.
  2. Replay a 1 billion-deep failure from the nearest checkpoint in at most 30 min.
  3. Require an exact suffix.
  4. Require 100 hidden locations including just-before-checkpoint, cold storage and restart.
  5. Include load, lookup and reference and original artifact cost.
  6. Use the statistical comparison in section 3.1 for integrated workflow versus Verdi.
  7. Keep verified repair in D19.

<a id="D18c4"></a>

#### D18.c4: Check X and Z origin tracing
- Phases: Start work in P09. Accept this cell in P09.
- Must pass first: D18.c1, D07.c1, D27.c8.
- Baseline: Verdi.
- Summary: Test exact X and Z origin tracing and investigation cost. Require X-origin tracing on at least 100 independently specified under the independence protocol R04 X and Z cases covering uninitialized storage, reset, multiple drivers, resolution, force and release and mixed scheduler regions: exact origin set, active driver path and first propagation timestamp, including ambiguity sets.
- Rule:
  1. Require X-origin tracing on at least 100 independently specified under the independence protocol R04 X and Z cases covering uninitialized storage, reset, multiple drivers, resolution, force and release and mixed scheduler regions: exact origin set, active driver path and first propagation timestamp, including ambiguity sets.
  2. Refuse all 20 masked-X and wrong-origin controls.
  3. Use the statistical comparison in section 3.1 for total investigation time at most 1.02 and scripted checked time at most 1.15 versus Verdi with task budgets.
  4. Require zero margin for deterministic origin quality.

<a id="D18c9"></a>

#### D18.c9: Check assertion debug
- Phases: Start work in P10. Accept this cell in P10.
- Must pass first: D18.c1, D07.c1, D27.c8.
- Baseline: Applicable Verdi, Verisium Debug and SimVision facilities.
- Summary: Test the correctness of assertion debug. Require at least 50 valid and 50 invalid or stale cases per family across three designs.
- Rule:
  1. Require assertion debug: inspect independently known sampled values, pending assertion threads, local variables, abort and disable, vacuity and first failing cycle.
  2. Require at least 50 valid and 50 invalid or stale cases per family across three designs.
  3. Require exact answers.
  4. Require zero wrong joins after restore.
  5. Use the statistical comparison in section 3.1 for verified diagnosis time, effort and tails versus applicable Verdi AND Verisium Debug AND SimVision facilities.
  6. Use E-Trace transport receipts as wrong-subject negative controls.

<a id="D19c90"></a>

#### D19.c90: Check source-specific repair issues
- Phases: Start work in P10. Accept this cell in P10.
- Must pass first: D19.c1, D27.c2, D30.c6, D27.c8.
- Baseline: Use the baseline stated in the rule when a comparison applies.
- Summary: Test the correctness of source-specific repair issues. Require all 4 numbered rule items.
- Rule:
  1. Apply I90, the source-specific issue protocol, to these issue requirements: #27 proposed repairs require independent original-RTL replay and no wrong accepted merge.
  2. For #32, require that bug memory retrieves held-out known causes without leaking sealed answers.
  3. For #45, require that bisection on real history identifies the independently confirmed first bad revision and handles nonmonotonic failures explicitly.
  4. Apply the complete I90 protocol.

<a id="D23c1"></a>

#### D23.c1: Check the regression farm and status-query service
- Phases: Start work in P09. Accept this cell in P09.
- Must pass first: D27.c1, D27.c2, D07.c1, D27.c8.
- Baseline: Use the baseline stated in the rule when a comparison applies.
- Summary: Test regression closure, durable generations, fault recovery and status-query response. Require zero lost, duplicate or stale accepts.
- Rule:
  1. For #25, provide a graph from requirements to tests, proofs and coverage closure.
  2. Support reuse, selection, cancel acknowledgements, flake and trend tracking, waiver expiry and immutable publication.
  3. Test 100 worker, controller, lease, store and clock faults.
  4. Require zero lost, duplicate or stale accepts.
  5. Complete cleanup in at most 30 s.
  6. Build once per identity.
  7. Limit the 100k-cell status query 95th-percentile response to at most 2 s.
  8. Require 100 correct generation links out of 100.

<a id="D23c2"></a>

#### D23.c2: Check regression selection and pre-merge latency
- Phases: Start work in P10. Accept this cell in P10.
- Must pass first: D23.c1, D04.c1; seeds not substitutes for natural evidence, D20.c2a, D27.c8.
- Baseline: Use vManager with IMC, Synopsys VSO.ai and Cadence Verisium on the required matched frames.
- Summary: Test selection safety, campaign benefit, drift alarms and pre-merge deadlines against every required comparator. Limit flake to at most 0.1%.
- Rule:
  1. For #25, test selection on 500 failing histories.
  2. Use at least 250 real histories or an audited natural census using the D20.c2a enumeration method and this cell's executed histories.
  3. For population claims, require the adjusted miss upper bound at most 1%.
  4. Retain complete nightly campaigns.
  5. Limit flake to at most 0.1%.
  6. Track its disposition within 24 h.
  7. Flag performance drift greater than 0.5%.
  8. Apply section 3.1 statistical comparisons to verified completion, deadlines, closure effort and valid-campaign cost.
  9. Use the same graph, results, load and history for vManager with IMC.
  10. Permit no hidden mandatory holes.
  11. On unchanged independent nights, require the false-alarm upper bound at most 1% at the local alpha.
  12. Pilot 30 nights, then increase for joint power.
  13. Keep injected-drift sensitivity and no-change false alarms as separate critical endpoints.
  14. Use the exact seven-night D04.c1 control for bootstrap only.
  15. Fix selection cost as the secondary benefit.
  16. Require the adjusted upper total checked-campaign core-hour cost ratio at most .90 against vManager on the required failing-history frame.
  17. Charge selection, complete nightly backstops, retries, misses and verification.
  18. Preserve the adjusted miss upper bound at most 1% and all non-inferiority gates.
  19. A cheaper incomplete campaign cannot pass.
  20. Measure pre-merge latency from pushed change to durable checked gate verdict on the pinned reference farm.
  21. Include queue time, builds, retries and reference checks.
  22. Seal the developer-demand 95th-percentile deadline before outcomes.
  23. Require the stricter of that deadline and 30 minutes at normal and 125 percent load.
  24. Retain complete mandatory scope and nightly backstops.
  25. Require the adjusted 95th-percentile latency ratio at most 1.02 against vManager with IMC.
  26. Incomplete, skipped and inconclusive jobs must not count as timely accepted verdicts.
  27. Compare matched regression selection against both Synopsys VSO.ai and Cadence Verisium.
  28. Pin builds and feature manifests under R08, the shared comparator-matching protocol.
  29. Retain the original selection safety, escaped-failure, cost and benefit gates for each comparator.
  30. Make this regression-selection receipt a co-owner of H20.001.
  31. Limit pre-merge 95th-percentile latency to 10 minutes for documentation and metadata changes.
  32. Use 20 minutes for isolated tool logic changes.
  33. Use 30 minutes for engine, frontend or cross-tool changes.
  34. Apply each bound at normal and 125 percent load, or use the stricter demand deadline.
  35. Classify changes by affected contracts before results.
  36. For mixed changes, use the broadest required test scope and the applicable 30 minute bound.
  37. Seeds must not substitute for natural evidence.

<a id="D23c3"></a>

#### D23.c3: Check requirements exchange and closure
- Phases: Start work in P10. Accept this cell in P10.
- Must pass first: D23.c1, D27.c8, D24.c2 (explanatory context only; it supplies no acceptance evidence).
- Baseline: Use Verdi Planner for closure effort and update and query time.
- Summary: Test exact requirements exchange and Verdi Planner closure behavior through two upgrades. Require zero wrong closures.
- Rule:
  1. For #25, round-trip exact revisions, IDs, links, status, waivers and unknowns through ReqIF and native requirements APIs.
  2. Use 100 independent graphs.
  3. Apply UP2, which maintains results through two independent upgrades.
  4. Make 30 missing, rekeyed and stale-link controls fail completeness.
  5. Export all requirements, tests, proofs and failures for offline review.
  6. Annotations must never alter original evidence.
  7. Pin the Verdi Planner product, version and options under R08, the comparator-matching protocol.
  8. Use at least 100 controls per type for requirement changes, orphan links, incompatible coverage revisions, expired waivers and incomplete closure.
  9. Require zero wrong closures.
  10. Require exact requirement, test, proof and bin revision links.
  11. Compare verified closure effort and update and query time statistically under section 3.1 against Verdi Planner.
  12. Make retention-only receipts fail at least 20 controls.
  13. D24.c2 supplies retention, not feature qualification.

<a id="D23c4"></a>

#### D23.c4: Check simulated entitlement-token admission
- Phases: Start work in P10. Accept this cell in P10.
- Must pass first: D23.c1, D27.c8.
- Baseline: Use the baseline stated in the rule when a comparison applies.
- Summary: Test simulated entitlement-token admission and recovery. Require zero token over-allocation or leaks.
- Rule:
  1. Test expiry, revocation, cancel and retry on 100 independent contention schedules.
  2. Require zero token over-allocation or leaks.
  3. Preserve the native open path and configured choice.
  4. Implement the commercial scheduler adapter and entitlement-token interface from issue #60 with controlled token-service fixtures.
  5. For #25, support optional token limits and explicit token waits.
  6. Report token absence as a scheduler wait, never as a device-under-test failure.
  7. Include token waits and configured token costs in total campaign statistical endpoints under section 3.1.

<a id="D23c90"></a>

#### D23.c90: Check regression infrastructure issue requirements
- Phases: Start work in P10. Accept this cell in P10.
- Must pass first: D23.c1, D27.c2, D30.c6, D27.c2, D27.c8.
- Baseline: Use the baseline stated in the rule when a comparison applies.
- Summary: Test every D23.c90 issue child, including hosted workflows and Kubernetes execution. Require zero false passes.
- Rule:
  1. Apply I90, the complete source-specific issue-child protocol.
  2. For #16, execute pinned hosted CI workflows with retained failure artifacts.
  3. For #25, reconcile immutable job and result generations in the farm and status-query service.
  4. For #41, keep an explicit fast allowlist that leaves new modules slow.
  5. For #53, reject corrupt, stale and cross-policy cache hits.
  6. For #57, reconcile tokens, calls, core-hours and money against independent billing.
  7. For #59, preserve the native desktop contract, isolation and exact replay for cluster jobs.
  8. For #71, match native bundles to signed source and build provenance per host.
  9. For #73, include failed setup, reference and artifact costs in the cold full-tier gate.
  10. For #59, make --executor k8s run regressions, cosim, coverage and formal as Kubernetes Jobs.
  11. Build once per rtl_sha256 with immutable dependency and toolchain keys.
  12. Mark eviction inconclusive.
  13. On retry, retain the failed attempt and lease fencing.
  14. Use at least 100 eviction, build-race and stale-image controls.
  15. Require zero false passes.
  16. Require one accepted artifact generation.
  17. Keep native desktop execution native.
  18. Preserve conflicting original container spans under SR24, the source receipt and import-state protocol.
  19. Before acceptance, consume the source importer's hash-bound, sealed #59 source-resolution record.
  20. A brief quotation without authority or hash must be insufficient.

<a id="D23c5"></a>

#### D23.c5: Check failure grouping
- Phases: Start work in P10. Accept this cell in P10.
- Must pass first: D23.c1, D28.c3, D27.c8.
- Baseline: Use vManager and IMC for verified triage throughput and effort.
- Summary: Test failure grouping accuracy, complete accounting and triage performance. Use at least 1000 independently labeled failures spanning at least 100 natural root causes.
- Rule:
  1. Use at least 1000 independently labeled failures spanning at least 100 natural root causes.
  2. Add injected alias, split and flake controls.
  3. Require exact mandatory same-cause and different-cause constraints.
  4. Require sampled grouping precision and recall lower bounds at least .95 each.
  5. Reconcile every failure once, including unknown and unclustered failures.
  6. At 100k jobs, limit 95th-percentile ingest-to-triage time to at most 60 s.
  7. Compare verified triage throughput and effort against vManager and IMC under section 3.1 statistical margins.
  8. Retain natural versus injected labels.

<a id="D24c2"></a>

#### D24.c2: Check evidence retention and retrieval
- Phases: Start work in P10. Accept this cell in P10.
- Must pass first: D23.c1; D27.c1 (explanatory context only; it supplies no acceptance evidence) provenance, D27.c8.
- Baseline: Use the baseline stated in the rule when a comparison applies.
- Summary: Test evidence retention and exact retrieval and replay under the required retention periods.
- Rule:
  1. Retain manifests for one year.
  2. Retain failed raw data for ninety days.
  3. Retain successful raw data for 30 days.
  4. Retain promoted evidence for support life plus 180 days.
  5. Promote all sealed agent, repair and upgrade test inputs at sealing, before raw expiry.
  6. Require exact two-host retrieval and original-artifact upgrade replay.
  7. Deletion and stale-generation controls cannot accept.
  8. Use D27.c1 only as provenance context.

<a id="D24c8"></a>

#### D24.c8: Choose the regression controller and store
- Phases: Start work in P07. Accept this cell in P10.
- Must pass first: D23.c1, D28.c1, D27.c8.
- Baseline: Use the baseline stated in the rule when a comparison applies.
- Summary: Test controller recovery and the required store redirect decision. Require exactly one accepted generation.
- Rule:
  1. Apply RG27, the regression controller and store method decision.
  2. Test 100 worker, store and controller-loss schedules.
  3. Require exactly one accepted generation.
  4. Require zero lost accepted artifacts.
  5. Require a recovery point objective of 0.
  6. Restore in at most 15 min.
  7. Verify stale leases, duplicate completion, revocation and overlapping-release controls.
  8. After two failed recovery prototypes, redirect from a custom metadata store to transactional PostgreSQL with immutable object storage.
  9. Keep all availability and scale endpoints.

<a id="D25c7"></a>

#### D25.c7: Check agent workflow primitives
- Phases: Start work in P08. Accept this cell in P09.
- Must pass first: D25.c6, D26.c2, D27.c8, D25.c9.
- Baseline: Use qualified shell and leading agent recipes for all four engineering strata.
- Summary: Test safe workflow transactions and engineering benefit against the qualified agent recipes. Require zero unauthorized or wrong acceptance.
- Rule:
  1. Provide receipt-graph planning, affected-obligation discovery, minimal authorized edits, a proof and repair sandbox, checkpoint and resume, and stopping on unknowns.
  2. Record proposal, allowed writes, expected invalidations and independent terminal checks in one typed transaction.
  3. Use at least 100 seeded dependency, permission, false-proof, stale-context and interruption controls.
  4. Require zero unauthorized or wrong acceptance.
  5. Require at least 90% correct next safe steps on sealed cases.
  6. Compare all four engineering strata against qualified shell and leading agent recipes.
  7. Require secondary verified campaign-time ratio at most .75.
  8. Retain other non-inferiority and exact safety gates in the shared campaign receipt.

<a id="D25c9"></a>

#### D25.c9: Choose the agent workflow method
- Phases: Start work in P07. Accept this cell in P08.
- Must pass first: D25.c6, D26.c2, D27.c8, D26.c1 (explanatory context only; it supplies no acceptance evidence), D25.c2 (explanatory context only; it supplies no acceptance evidence).
- Baseline: Use the baseline stated in the rule when a comparison applies.
- Summary: Test workflow transactions, safe resume and authority through attacks and required redirects. Require zero unauthorized writes or wrong terminal acceptance.
- Rule:
  1. Apply AW27, the agent workflow method decision.
  2. Run 100 independently authored crash, stale-context, forbidden-write and forged-proof controls through the transaction machine.
  3. Require zero unauthorized writes or wrong terminal acceptance.
  4. Require deterministic resume.
  5. Require at least 90% correct safe next steps.
  6. Stop automatic commit on identity mismatch.
  7. After two failed prototypes, redirect to smaller explicit independently checked transactions.
  8. Keep agent-only benefit OPEN until original gates pass.
  9. Bind AW27 authorization to the untrusted-content policy explained in D25.c2 and adaptive prompt-injection controls explained in D26.c1.
  10. Replay every attack after tool, model or permission changes.
  11. A forged instruction cannot alter transaction authority.

<a id="D29c5"></a>

#### D29.c5: Check integrated and accessible workspace journeys
- Phases: Start work in P10. Accept this cell in P10.
- Must pass first: D18.c1, D23.c1, D29.c1, D27.c8, D05.c1 (explanatory context only; it supplies no acceptance evidence). D29.c2 runtime receipt.
- Baseline: Use the baseline stated in the rule when a comparison applies.
- Summary: Test generation-correct cross-tool navigation and equivalent accessible information at supported scale. Require zero stale or wrong joins.
- Rule:
  1. Connect requirements to campaigns, tests and proofs, coverage, causes, source and waves, then verified repairs and decisions.
  2. Keep the same generation, unknowns and CLI and MCP links in every view.
  3. Check permissions for offline and moved-host sessions.
  4. Use 100 independently answered journeys.
  5. Require zero stale or wrong joins.
  6. Require at least 95% correct next steps.
  7. Limit 95th-percentile cross-tool navigation to at most 1 s.
  8. Limit 100k-result search to at most 2 s.
  9. Include cancelled, ambiguous and proof-unknown controls.
  10. Use scripts and pinned agents on the same journey.
  11. Require retrieval of wave values and time, driver branches, hierarchy and source, coverage holes and proof-unknown reasons.
  12. Support complete plain-text retrieval through CLI and MCP.
  13. Require exact independently specified R04 answers and status parity across CLI and MCP.
  14. Provide complete equivalent information, stable identity and cancellable paginated search.
  15. Include five tasks per query class and wrong, stale and hidden-information controls.
  16. Use the D29.c2 scripted task matrix for whole journeys.
  17. Permit a textual accessible view.
  18. A picture alt label alone must not qualify.
  19. At the D05.c1 1 million-signal size and D18.c1 100 GB and 1 TB sizes, run scripted text retrieval checks.

<a id="D30c5"></a>

#### D30.c5: Check accelerator and NoC generality
- Phases: Start work in P10. Accept this cell in P10.
- Must pass first: D30.c1, D31.c2, D27.c8.
- Baseline: Use the baseline stated in the rule when a comparison applies.
- Summary: Test complete generic flows and versioned adapters on independently selected accelerator and NoC projects. Require zero false accepts.
- Rule:
  1. Use independent accelerator and NoC projects without CPU, ISA or RVFI contracts.
  2. Complete expected positive and negative build, query, formal, debug, coverage and regression flows.
  3. Require zero false accepts.
  4. Require no generic-code edits.
  5. Support current and previous two minor adapter API versions.
  6. Apply UP2, which maintains results through two independent upgrades.
  7. Require exact capability negotiation and round-trip fields.
  8. Require migration or explicit refusal, with no field loss.
  9. Select at least 2 independent accelerator projects and at least 2 independent NoC projects.
  10. Seal build and function eligibility and a dated census before reveal.
  11. If more than 2 are eligible per class, have a custodian select randomly by independent lineage.
  12. If fewer are eligible, use sealed substitutes under SR24 source-custody rules and section 3.4 substitute rules.
  13. Retain real-target counts and claims.
  14. Make original flows pass on every selected project.

<a id="D30c6"></a>

#### D30.c6: Check historical adapters and API stability
- Phases: Start work in P09. Accept this cell in P09.
- Must pass first: D30.c1, D07.c1, D27.c8.
- Baseline: Use the baseline stated in the rule when a comparison applies.
- Summary: Test version-aware historical execution and adapter stability through two upgrades. Require two adapter implementations with independent ancestry to pass conformance, old-client and migration controls.
- Rule:
  1. For #335, select historical adapters by explicit interface version or audited revision-era map.
  2. Record adapter source hash, version, selection rule and core revision in C1 and C8 run identity.
  3. Seal a real history spanning at least 1 interface change and at least 2 revisions per era.
  4. Make bisect find the independently known first bad revision.
  5. Permit explicit unsupported revision only where no adapter exists.
  6. Make a cold gate build and run both old base and new head with their selected adapters.
  7. Never treat a failed build as a regression pass.
  8. Make 20 wrong-era, ambiguous and stale-identity controls refuse.
  9. Document the backward-compatible-or-version-bump rule through a linked spinal-boom interface proposal.
  10. Check the versioned rule with independent interface fixtures.
  11. Use independent versioned fixtures for tool acceptance without requiring a new core feature.
  12. Publish a versioned adapter and plugin API and ABI contract.
  13. Include schemas, capability negotiation and semantic version rules.
  14. Require a major version and migration tool for breaking changes.
  15. Support the previous two major versions for at least 12 months after deprecation notice.
  16. Require two adapter implementations with independent ancestry to pass conformance, old-client and migration controls.
  17. Apply UP2, which maintains results through two independent upgrades.
  18. Make at least 20 incompatible-layout, removed-field and silent-semantic-change controls refuse or migrate exactly.
  19. A version-mismatch rejection alone cannot close stability.

<a id="D31c2"></a>

#### D31.c2: Implement language bridges and e and SystemVerilog interoperability
- Phases: Start work in P09. Accept this cell in P09.
- Must pass first: D31.c1 then D07.c1 runtime; VHDL bridge prototypes independent under R04 independent requirement-derived expectations, D27.c8, D15.c1 (explanatory context only; no acceptance evidence), D13.c1 (explanatory context only; no acceptance evidence).
- Baseline: Use the baseline stated in the rule when a comparison applies.
- Summary: Test mixed-language integration and typed e and SystemVerilog interoperability against independent event and value answers. Use UP2 to maintain deterministic reset, seed and checkpoint replay through two independent upgrades.
- Rule:
  1. Implement the VHDL and mixed-language bridge and SV, VHDL and SystemC integration.
  2. Require exact independent event answers on unchanged benches.
  3. D07.c1 owns the SV runtime.
  4. Use D13.c1 only as explanatory context for UVM.
  5. Use D15.c1 only as explanatory context for formal SVA.
  6. Permit no circular delegation.
  7. Require the full advertised denominator.
  8. Retain limits for protected interfaces.
  9. Implement the required typed e and SystemVerilog interoperability child against the unchanged boundary on open and Xcelium paths.
  10. Require exact independent events and values.
  11. Permit no race masking or foreign-state loss.
  12. Use UP2 to maintain deterministic reset, seed and checkpoint replay through two independent upgrades.
  13. Measure runtime, cost, resident memory and debugging effort under section 3.1.
  14. Keep this comparison separate from editor productivity.
  15. Run VHDL bridge prototypes independently under R04, which requires requirement-derived expectations, distinct producer and checker authors, and recorded ancestry.

<a id="D31c3"></a>

#### D31.c3: Qualify final digital gate-netlist and SDF replay
- Phases: Start work in P10. Accept this cell in P10.
- Must pass first: D31.c1, D07.c3 negotiation, D27.c8.
- Baseline: Use the baseline stated in the rule when a comparison applies.
- Summary: Test final external gate-netlist and SDF digital replay, including unsupported cases and full annotation coverage. Test 20 supported and 20 unsupported or unknown cell, delay and check cases.
- Rule:
  1. Require the final external gate-netlist and SDF digital replay.
  2. Test 20 supported and 20 unsupported or unknown cell, delay and check cases.
  3. Require exact annotation, timestamp and violation reports.
  4. Refuse unknowns or propagate their taint.
  5. Provide no synthesis, physical delay extraction or signoff claim.
  6. An early interface may be explicitly unadvertised.
  7. This exception narrows only Alpha and Beta.
  8. For full support, require positive cell, delay, timing-check and mixed-language annotation coverage for all relevant H01.030 and H02.023 clauses.
  9. Include unsupported cases after implementation.
  10. Removing advertising cannot close a final COVER child.

<a id="D31c4"></a>

#### D31.c4: Qualify standalone VHDL execution
- Phases: Start work in P10. Accept this cell in P10.
- Must pass first: D31.c2, D27.c8.
- Baseline: Use Xcelium for runtime, cost and resident-memory comparisons.
- Summary: Test standalone VHDL scheduling and execution independently of SV runtime receipts. Require at least 50 valid and 50 invalid controls per semantic family.
- Rule:
  1. Pin the GHDL frontend and kernel bridge version.
  2. Implement all relevant scheduling, delta cycles, signal resolution, inertial and transport delay, processes, protected and shared state, and foreign interfaces.
  3. Require at least 50 valid and 50 invalid controls per semantic family.
  4. Use independent value, event and region answers.
  5. Keep benches unchanged through two independent upgrades.
  6. Measure runtime, cost and resident memory versus Xcelium under section 3.1.
  7. An SV runtime receipt cannot close VHDL.

<a id="D31c5"></a>

#### D31.c5: Qualify mixed SV and VHDL execution
- Phases: Start work in P10. Accept this cell in P10.
- Must pass first: D31.c2, D27.c8.
- Baseline: Use both VCS and Xcelium mixed-language paths.
- Summary: Test mixed SV and VHDL scheduling and boundary behavior against independent events and values. Require at least 50 valid and 50 violating boundary controls per family.
- Rule:
  1. Independently specify time units, region and delta ordering, resolution, and cross-language reset, checkpoint and foreign-state mapping.
  2. Require at least 50 valid and 50 violating boundary controls per family.
  3. Use UP2 to maintain exact independent events and values through two independent upgrades.
  4. Measure runtime, cost and resident memory against both VCS and Xcelium mixed-language paths under section 3.1.
  5. Standalone language receipts cannot close mixed scheduling.

<a id="D31c6"></a>

#### D31.c6: Qualify SystemC co-simulation
- Phases: Start work in P10. Accept this cell in P10.
- Must pass first: D31.c2, D27.c8.
- Baseline: Use both VCS and Xcelium.
- Summary: Test SystemC co-simulation and its SV boundary against independent events and values. Require at least 50 valid and 50 violating controls per family.
- Rule:
  1. Specify independent SystemC time, delta and phase behavior, process notification, TLM transactions and the SV foreign-boundary relation.
  2. Require at least 50 valid and 50 violating controls per family.
  3. Include time rounding, phase mismatch, callbacks, lifetime, checkpoint and reset.
  4. Use UP2 to maintain exact events and values on unchanged benches through two independent upgrades.
  5. Measure runtime, cost and resident memory versus both VCS and Xcelium under section 3.1.
  6. SV-only and VHDL-only receipts must refuse this type.

<a id="D32c2"></a>

#### D32.c2: Qualify engine continuity routes
- Phases: Start work in P10. Accept this cell in P10.
- Must pass first: D07.c1, D15.c2a, D18.c1, D31.c2, D27.c8.
- Baseline: Use the baseline stated in the rule when a comparison applies.
- Summary: Test engine changes, regression packs and upgrade routes. Require zero semantic regressions. Keep upstream and fork routes at most one upstream stable release behind.
- Rule:
  1. If upstream declines integration, name fork CI that tracks EVERY upstream stable release.
  2. Require the fork CI to pass the identical pack.
  3. Label that route FORK-MAINTAINED, never UPSTREAM-INTEGRATED.
  4. Permit no unsupported permanent delta.
  5. Limit UPSTREAM-TRACKING changes in upstream-owned files to 20,000 non-generated, non-test lines.
  6. Count new extension-module lines separately without this ceiling.
  7. Keep that upstream-file delta within the ceiling.
  8. Keep the engine at most one upstream stable release behind.
  9. At either limit, rebase, upstream or reduce the delta before supported promotion.
  10. Never drop functionality.
  11. Require three-release rebase tests, semantic regression tests and a carried-line and time ledger.
  12. Require a visible plan revision for route changes, never a hidden waiver.
  13. Require three consecutive stable-release rebases at most 10 days of scripted execution each.
  14. Require zero semantic regressions.
  15. The fork route has no total-line ceiling.
  16. Treat this fallback as a required tested gate, not a waiver.
  17. Use one of three exclusive continuity routes: UPSTREAM-INTEGRATED or UPSTREAM-TRACKING, FORK-MAINTAINED, or NEW-ENGINE-MAINTAINED.
  18. Apply the upstream-file ceiling to UPSTREAM-INTEGRATED and UPSTREAM-TRACKING.
  19. Permit full SV, UVM and SVA extensions under FORK-MAINTAINED without a 20,000 total-line ceiling.
  20. Retain every rebase, regression and at most one-release lag gate for that fork route.
  21. Use NEW-ENGINE-MAINTAINED for standalone kernels, not forks.
  22. Archive source origin and dependency releases.
  23. No new engine can claim upstream acceptance.
  24. Support large extensions only through a qualified continuity route.
  25. Never reduce features to meet drift limits.
  26. Record changed upstream-owned lines, extension-module lines, carried patches, stable-release lag and elapsed rebase time separately per engine.
  27. For UPSTREAM-INTEGRATED and UPSTREAM-TRACKING, require at most 20,000 upstream-owned lines.
  28. For both routes, require at most one stable release lag.
  29. For these routes, require at most 10 days of scripted execution per rebase for three consecutive stable releases.
  30. FORK-MAINTAINED has no total-line ceiling but must pass the same lag and rebase deadlines.
  31. For NEW-ENGINE-MAINTAINED, report API and format drift.
  32. Pass three upgrade and migration packs.
  33. Crossing a route bound must block promotion and invoke the existing tested continuity redirect without dropping scope.
  34. Use three exclusive route families: the upstream route, the maintained fork route and the maintained new-engine route.
  35. Provide six machine-checked change series across three dependency test fixtures.
  36. Run each modified engine regression pack in CI through three consecutive upstream stable releases.
  37. Test the same upgrade and migration packs on fork and new-engine routes.
  38. Require the identical semantic and performance regression packs.
  39. For new engines, require a public versioned API and format and three consecutive supported releases.
  40. Require a minimum of two substantive machine-checked change series per engine.
  41. Preserve all functionality and technical merge-conflict and rejected-patch evidence.

<a id="D33c7"></a>

#### D33.c7: Qualify natural SMT security integration
- Phases: Start work in P08. Accept this cell in P08.
- Must pass first: D17.c11, D33.c6, D34.c2, D34.c3, D33.c8, D27.c8.
- Baseline: Use the baseline stated in the rule when a comparison applies.
- Summary: Test natural SMT integration and original attack and proof gates for unqualified Security Full. Require all 6 numbered rule items.
- Rule:
  1. Require natural SMT attack and contract integration for unqualified Security Full.
  2. Use the natural scaled SMT receipt.
  3. Include all sibling process, guest, hart and reset-retained contexts, leak activation, mitigations and novel bypasses.
  4. Apply all original digital attack-detection, channel-unit, time and effort comparisons.
  5. Require valid confidentiality and integrity proofs.
  6. No generated-SMT or finite attack receipt replaces natural integration or relational proof.

<a id="D33c9"></a>

#### D33.c9: Check published attack classes
- Phases: Start work in P08. Accept this cell in P08.
- Must pass first: D33.c2, D27.c8.
- Baseline: Use both JasperGold SPV and Radix under the original security bounds.
- Summary: Test exact detection and false-claim controls for published digital attack classes against both security comparators. Require exact detection of 100 percent of covered known bugs.
- Rule:
  1. Seal a corpus from cited published Spectre-v1, Spectre-v2, Spectre-v4, MDS and port-contention classes.
  2. Include cache-timing variants and correct controls.
  3. For each class, define the observation contract, source paper, adaptation and expected leak before running tools.
  4. Require exact detection of 100 percent of covered known bugs.
  5. Require at least 20 independent cases per class.
  6. Require zero false leak claims on correct controls.
  7. Keep a class outside a contract visibly OPEN until its own digital observation contract exists.
  8. Compare JasperGold SPV and Radix under the original security bounds.
  9. These checks do not make analog leakage claims.

<a id="D34c7"></a>

#### D34.c7: Prove quantitative randomized-security composition
- Phases: Start work in P08. Accept this cell in P08.
- Must pass first: D34.c2, D33.c8, D28.c3a, D27.c8.
- Baseline: Use the baseline stated in the rule when a comparison applies.
- Summary: Test adaptive probabilistic composition and independent certificates before exporting bounded-leakage labels. Require zero false accepted composition.
- Rule:
  1. Export RANDOMIZED-BOUNDED-LEAKAGE only with a checked per-history conditional total-variation bound epsilon_i.
  2. Require explicit assumption failure delta and an adaptive composition proof.
  3. For every history, concurrency and retained reset state, require the sum of epsilon_i plus delta at most 1e-6.
  4. Apply that budget over at most 1e6 queries.
  5. With equal allocation and zero delta, require at most 1e-12 per query.
  6. Alternatively, seal a different quantitative budget before data and name it in the label.
  7. That alternative cannot close the default session-total-variation child.
  8. Prove transition-kernel bounds symbolically with independent certificates.
  9. Empirical leakage estimates cannot prove tiny bounds.
  10. Check at least 50 valid probabilistic systems against exact finite distribution calculations.
  11. Check 50 adaptive-history, reset, overbudget and unit-conversion mutants against those calculations.
  12. Require zero false accepted composition.
  13. If history assumptions are missing, export RANDOMIZED-COMPOSITION-UNPROVED.
  14. Under that condition, keep composition OPEN.
  15. Keep deterministic and integrity claims separate.

<a id="D37c4"></a>

#### D37.c4: Check analog-facing digital boundary adapters
- Phases: Start work in P10. Accept this cell in P10.
- Must pass first: D37.c2, D31.c2, D27.c8.
- Baseline: Use the baseline stated in the rule when a comparison applies.
- Summary: Test behavioral and real-number boundary adapters against exact expected digital observations and explicit native limits. Require 30 legal, invalid and missing-model controls per advertised boundary.
- Rule:
  1. Provide behavioral and real-number boundary adapters under #217 for analog-facing clocks, resets and sensors.
  2. State native support and limits explicitly.
  3. Require 30 legal, invalid and missing-model controls per advertised boundary.
  4. Require exact independently expected digital observations and unknowns.
  5. Provide no transistor, PLL or electrical assurance.
  6. Keep unsupported boundaries visible.

<a id="D37c7"></a>

#### D37.c7: Check digital metastability fault injection
- Phases: Start work in P09. Accept this cell in P09.
- Must pass first: D37.c1, D07.c1, D15.c2a, D27.c8.
- Baseline: Use Questa CDC injection and applicable SpyGlass recipes.
- Summary: Test crossing uncertainty with simulation and formal perturbation while retaining explicit timing assumptions and digital-only claims. Use explicit X and concrete 0 and 1 resolution runs to expose optimism.
- Rule:
  1. Under #22, inject clock-domain crossing metastability in simulation and symbolic formal perturbation.
  2. Independently enumerate every synchronizer, handshake, Gray, reset and reconvergent crossing and legal timing window.
  3. Use nondeterministic delay and capture choices to model digital uncertainty.
  4. Use explicit X and concrete 0 and 1 resolution runs to expose optimism.
  5. Seal at least 50 safe and at least 50 activated loss, duplication, reordering and reconvergence controls per family.
  6. Detect each required unsafe loss.
  7. Require safe protocols to preserve declared delivery and conservation under explicit bounded-delay and fairness assumptions.
  8. Replay counterexamples in the original four-state bench.
  9. Require checked formal certificates for unbounded guarantees.
  10. Measure sensitivity, false warnings, checked time and scripted checked time under section 3.1.
  11. Compare against Questa CDC injection and applicable SpyGlass recipes.
  12. Use a digital fault model only, never an analog mean-time-between-failures claim.

<a id="D38c5"></a>

#### D38.c5: Check the LLVM security-contract consumer
- Phases: Start work in P08. Accept this cell in P08.
- Must pass first: D34.c4, D38.c2; independent emitted-stream checker, D27.c8.
- Baseline: Use the baseline stated in the rule when a comparison applies.
- Summary: Test LLVM schedule preservation and transitive invalidation under full security assumptions. Require at least 50 valid and at least 50 independently activated violating schedules per assumption family.
- Rule:
  1. Check the LLVM security-contract consumer.
  2. Require at least 50 valid and at least 50 independently activated violating schedules per assumption family.
  3. Cover operand latency, speculation, memory observation, interrupt and context assumptions.
  4. Use two lowerings and versions.
  5. Apply RP06, which requires independent emitted-instruction decoding and a full finite preservation relation or proof certificate.
  6. Require exact zero false accepts.
  7. Refuse unsupported transformations.
  8. A latency-only contract never authorizes whole-program constant time.
  9. Apply RP07, which requires twenty stale, revoked and mutated-contract controls.
  10. Require those controls to invalidate emitted code, the generated model and every downstream decision.
  11. Require an independent emitted-stream checker.
  12. Apply the complete RP06 emitted-instruction checks and finite preservation relation or proof certificate.
  13. Apply the complete RP07 transitive invalidation rules.

<a id="D38c6"></a>

#### D38.c6: Check the GCC security-contract consumer
- Phases: Start work in P08. Accept this cell in P08.
- Must pass first: D34.c4, D38.c2; independent emitted-stream checker, D27.c8.
- Baseline: Use the baseline stated in the rule when a comparison applies.
- Summary: Test GCC schedule preservation and transitive invalidation under full security assumptions. Require at least 50 valid and at least 50 independently activated violating schedules per assumption family.
- Rule:
  1. Check the GCC security-contract consumer.
  2. Require at least 50 valid and at least 50 independently activated violating schedules per assumption family.
  3. Cover operand latency, speculation, memory observation, interrupt and context assumptions.
  4. Use two lowerings and versions.
  5. Apply RP06, which requires independent emitted-instruction decoding and a full finite preservation relation or proof certificate.
  6. Require exact zero false accepts.
  7. Refuse unsupported transformations.
  8. A latency-only contract never authorizes whole-program constant time.
  9. Apply RP07, which requires twenty stale, revoked and mutated-contract controls.
  10. Require those controls to invalidate emitted code, the generated model and every downstream decision.
  11. Require an independent emitted-stream checker.
  12. Apply the complete RP06 emitted-instruction checks and finite preservation relation or proof certificate.
  13. Apply the complete RP07 transitive invalidation rules.

## M5: Close wide capability and category benefits

Acceptance phases: P11–P12.

<a id="D01c8"></a>

#### D01.c8: Frequency-independent memory timing and qualified cross-ISA counter predictions with explicit unknowns
- Phases: Start work in P11. Accept this cell in P11.
- Must pass first: D01.c3c, D08.c90, D36.c4, D27.c8.
- Baseline: Use independent equations, full RTL and controller-traffic anchors, and the qualified D36.c4 counters.
- Summary: Test frequency-independent memory timing and qualified cross-ISA counter predictions with explicit unknowns. Require latency error at most 5%.
- Rule:
  1. Implement frequency-independent DRAM and NoC timing models.
  2. Freeze published controller and protocol versions.
  3. Freeze fixed-ns service and refresh, bank and rank maps, queueing, routing and arbitration.
  4. Use independent equations and full RTL and controller-traffic anchors at 100 points.
  5. Cover saturation, refresh, row hits, row misses, contention and reset.
  6. Require exact protocol and order.
  7. Require latency error at most 5%.
  8. Require bandwidth error at most 10%.
  9. Reject all wrong-unit, wrong-routing and wrong-refresh controls.
  10. Propagate model uncertainty to every decision.
  11. Configure the required cross-ISA diagnostic child from cited published Zen 5 and M-series parameters.
  12. Expose every unknown range.
  13. Compare with held-out branch, cache, latency and bandwidth microbenchmark counters from the explanatory context in D36.c4.
  14. Per counter family, require median relative error at most 5%.
  15. Per counter family, require 95th-percentile relative error at most 10%.
  16. Require correct bottleneck and intervention-direction lower bound at least .90.
  17. Use at least 30 independent loops per family with powered expansion.
  18. Keep a counter child OPEN if counters are missing.
  19. Time-only output cannot close it.
  20. Never infer internal vendor implementation from a fitted configuration.
  21. Use INSTRUMENTS-COUNTER-SUBSET only as a named narrower class.
  22. Pin Instruments and xctrace counters with independently checked event identity, multiplexing, region of interest and bias under R04 (independent requirement-derived expectations with distinct authors and recorded ancestry).
  23. Permit these counters to close only their enumerated counter children under the same 5% and 10% and direction bounds.
  24. Keep missing families OPEN.
  25. Private kperf and kpc are not required for this subset.
  26. Time-only data still cannot close counters.

<a id="D01c9"></a>

#### D01.c9: Blind transfer from generated wide RTL to natural targets before refitting
- Phases: Start work in P12. Accept this cell in P12.
- Must pass first: D01.c4, D21.c2, D27.c8.
- Baseline: Use independent RTL anchors inherited through D01.c4.
- Summary: Test blind transfer from generated wide RTL to natural targets before refitting. Before any refit, seal predictions for one held-out natural target with at least 6-wide geometry. Require independent target authorship under R04.
- Rule:
  1. Fit generated wide RTL only.
  2. Before any refit, seal predictions for one held-out natural target independently authored under R04 (independent requirement-derived expectations with distinct authors and recorded ancestry) with at least 6-wide geometry.
  3. Consider XiangShan as a candidate.
  4. Apply every pre-refit bound in the explanatory context in D01.c4 by workload and mechanism.
  5. Report misses separately from post-refit results.
  6. Generated success cannot rescue natural failure.
  7. Seal each prediction before refitting.
  8. Apply all original transfer gates separately to both natural lineages.
  9. Label a single passing lineage SINGLE-TARGET-TRANSFER.
  10. A single passing lineage cannot close this cell.

<a id="D01c12"></a>

#### D01.c12: Published-microarchitecture bottleneck replication and blind measured-cycle predictions against qualified production recipes
- Phases: Start work in P12. Accept this cell in P12.
- Must pass first: D01.c8, D04.c2, D27.c8, the sealed schema interface of D27.c3, the explanatory context in D36.c4. D01.c5 runtime receipt.
- Baseline: Use qualified measured-cycle systems and the strongest qualified production timing recipe selected before confirmation.
- Summary: Test blind cycle-prediction median absolute error at most 5% per system and class against measured Zen 5 and M-series anchors.
- Rule:
  1. Seal a sourced Zen 5 bottleneck model and one exact M-series microarchitecture bottleneck model before measurement.
  2. Seal at least 30 held-out interventions per branch and frontend, execution, cache and memory class before measurement.
  3. Pin public evidence and uncertainty.
  4. Require correct bottleneck identity and direction lower bound at least .90 per class.
  5. Require zero wrong-direction controls.
  6. Apply original cycle-error, event-error, cost and effort comparison gates under Section 3.1.
  7. Counter correlation alone cannot pass.
  8. Keep unsupported public details unknown.
  9. Invent no internals.
  10. For the model-quality child, predict measured cycles on each qualified Zen 5 and M-series system from the explanatory context in D36.c4.
  11. Seal at least 30 microbenchmarks per branch, cache, memory and compute family before measurement.
  12. Seal at least 30 full workloads per class before measurement.
  13. On unseen inputs, require 95th-percentile absolute cycle error at most 10% per system and class.
  14. Use adjusted bounds.
  15. Missing measured cycles leaves this child OPEN.
  16. Time-only data cannot close it.
  17. Compare with the strongest qualified production timing recipe under R08 (matched work and independent baseline-selection rules) matching rules at the same error bounds.
  18. Category 1 Full requires both Zen 5 and M-series blind cycle-prediction children in this cell.
  19. Neither time-only results nor local model comparisons can close this condition.
  20. Use the interface contract from D27.c3 to test 20 attempted Full exports with either child missing.
  21. If no production timing recipe qualifies for a system under R08, keep the commercial comparison and Category 1 Full OPEN.
  22. Use absolute cycle bounds only for the named absolute-bound diagnostic label.
  23. They cannot close Full.
  24. Register three production recipe candidates before tuning.
  25. Include independently tuned gem5 O3.
  26. Include a Scarab or Sniper recipe.
  27. Include a pinned published industrial-style model.
  28. Apply the baseline qualification rule in Section 3.
  29. Select the strongest qualified recipe on disjoint accuracy and intervention controls before confirmation.
  30. If no candidate qualifies, keep this comparison OPEN.
  31. Before capture, seal required counter and trace fields separately for branch, frontend, execution, cache and memory classes on each system.
  32. Require cycle, retired-instruction, branch and recovery counts, issue and stall causes, cache-level misses, translation events and memory-service intervals for each relevant class.
  33. Require timestamp, thread, address-space, source-event identity, sampling probability, skid bound, loss count and counter multiplexing scale in each trace record.
  34. Calibrate event semantics and capture bias with at least 30 independent interventions per class.
  35. Require exact deterministic event controls and the D01.c5 estimated-count bounds.
  36. Missing required depth keeps that class OPEN for bottleneck and cycle-model qualification.
  37. Keep time-only and partial-counter diagnostics separately labeled.
  38. Category 1 primary: Require blind cycle-prediction median absolute error at most 5% per system and class against measured Zen 5 and M-series anchors.
  39. Keep measured cycles, performance reports and published results for every held-out workload and intervention hidden from model builders until predictions and model parameters are sealed.
  40. An independent custody service must check publications and access history before admission. A consulted workload becomes training and needs a fresh held-out replacement under R05.
  41. Public microarchitecture descriptions may define the model. They cannot reveal the held-out workload outcomes.

<a id="D04c3"></a>

#### D04.c3: Qualify sampled causal shares and checked-time savings against full-run accounting and inherited advice gates
- Phases: Start work in P11. Accept this cell in P11.
- Must pass first: D04.c2, D08.c2, D03.c3, D03.c1, D20.c1, D27.c8.
- Baseline: Use independent full-run slot accounting and full-run checked time.
- Summary: Test sampled causal shares and checked-time savings against full-run accounting and inherited advice gates. Require adjusted absolute-error upper bound at most 1 percentage point per cause.
- Rule:
  1. Compare sampling-profiler cause shares with independent full-run slot accounting on every D03.c3 path and D20.c1 class.
  2. Require adjusted absolute-error upper bound at most 1 percentage point per cause.
  3. Require delta-attribution uncertainty at most the preregistered smallest useful effect in the endpoint units divided by 4.
  4. Require exact mandatory rare-event controls.
  5. Require 30 alias, cancellation and missing-phase controls to refuse.
  6. Apply D03.c3 to sampled advice.
  7. Require sampled total checked time upper workstation-to-baseline ratio at most .90.
  8. Keep all accuracy endpoints non-inferior under Section 3.1.

<a id="D06c3"></a>

#### D06.c3: Complete checked-change productivity, review effort and merge tails through two upgrades
- Phases: Start work in P11. Accept this cell in P11.
- Must pass first: D06.c1, D06.c2; D29.c1 task qualification, D05.c2, D27.c8. D05.c2a runtime receipt; D05.c2d runtime receipt.
- Baseline: Use the D05.c2 baseline family.
- Summary: Test the machine capability and exact correctness of complete checked-change productivity, review effort and merge tails through two upgrades. Require zero wrong accepted results.
- Rule:
  1. Measure the complete path from a fresh specified change to independently checked merged RTL under R04 (independent requirement-derived expectations with distinct authors and recorded ancestry).
  2. Include rejected and stopped work, review and generator repair.
  3. Over six months, use at least 30 scripted changes per language as a variance pilot.
  4. Run powered scripted change campaigns through two independent upgrades.
  5. Compare correct merged changes per allocated core-hour under Section 3.1.
  6. Compare scripted checked time.
  7. Compare 95th-percentile correct-merge time.
  8. Use D05.c2 baselines.
  9. Require zero wrong accepted merges.
  10. Use every applicable baseline from the complete D05.c2 family, D05.c2a through D05.c2d.

<a id="D06c4"></a>

#### D06.c4: Qualify RTL productivity using every language-specific secondary effort endpoint and all inherited correctness gates
- Phases: Start work in P12. Accept this cell in P12.
- Must pass first: D06.c3, D05.c2a, D27.c8, D06.c7, D05.c3, D06.c9.
- Baseline: Use every D05.c2a baseline and the language-specific native and matched-output comparators specified below.
- Summary: Test checked complete-answer throughput lower ratio at least 1.10 against each Sigasi, DVT and required native-generator recipe in every language child.
- Rule:
  1. Measure generator HDL productivity against its named native editor flows.
  2. Do not infer end-to-end superiority over commercial SV design from this receipt.
  3. Keep independently verified changes per allocated core-hour ratio at least 1.10 as a secondary measure in every language and project stratum.
  4. Compare against each D05.c2a baseline.
  5. Require non-inferior scripted recovery and checking time ratio at most 1.15.
  6. Require completion-tail ratio at most 1.20.
  7. Justify task budgets under Section 3.1.
  8. Count failed and rejected work and two upgrades.
  9. Permit non-inferior-only releases to say NONINFERIOR at the printed margins.
  10. Require this cell for the full productivity-benefit claim.
  11. Create a separate required matched-output child for generator-aware editing versus Sigasi and DVT.
  12. Use identical emitted SV output and independently checked change requirements under R04 (independent requirement-derived expectations with distinct authors and recorded ancestry).
  13. Apply the same help and review noninferiority and exact wrong-merge gates.
  14. Retain native-editor comparisons.
  15. Keep matched-output comparison as a required language child.
  16. Keep generic JVM and editor comparisons as required secondary evidence.
  17. They cannot substitute.
  18. Use D05.c3 and D06.c9 native-generator tasks for Spinal and Chisel.
  19. Select those recipes on disjoint controls.
  20. Never compare a generator author only on emitted SV.
  21. Require each language child to pass.
  22. Keep other benefit labels in these rows secondary.
  23. Keep all exact and non-inferior gates required.
  24. Permit no averaging across language children.
  25. Do not use a passing language child to close a failed language child.
  26. Keep the change-rate measure in rule 3 secondary.
  27. Run scripts or pinned agents on the same sealed change requirements and matched outputs.
  28. Retain all language-specific native recipes and both Sigasi and DVT comparisons.
  29. Require zero wrong accepted merges.
  30. Category 3 primary: Require checked complete-answer throughput lower ratio at least 1.10 against each Sigasi, DVT and required native-generator recipe in every language child.
  31. Require secondary adjusted upper checked-change-time ratio at most 0.90 against each required comparator in every language child.

<a id="D06c7"></a>

#### D06.c7: SV and VHDL task effort and lint-repair benefit against every required editor and lint comparator
- Phases: Start work in P11. Accept this cell in P11.
- Must pass first: D06.c2, D05.c2c, D29.c2, D27.c8.
- Baseline: Use both Sigasi and DVT, plus SpyGlass and Questa Lint for the lint workflow.
- Summary: Test SV and VHDL task effort and lint-repair benefit against every required editor and lint comparator. Require machine-latency ratio at most 1.02.
- Rule:
  1. Compare SV and VHDL productivity against BOTH Sigasi and DVT.
  2. Use complete design-entry, refactor, repair and testbench tasks on independently sealed real projects.
  3. Require secondary verified complete-task scripted checked-time upper ratio at most .90.
  4. Require non-inferior completion with margin .005.
  5. Require machine-latency ratio at most 1.02.
  6. Require effort-tail ratio at most 1.20.
  7. Require zero wrong edits.
  8. Compare lint setup and fix workflows against SpyGlass and Questa Lint.
  9. Require secondary verified scripted checked-time ratio at most .90 for that comparison.
  10. Permit no missed mandatory violations.
  11. Count all setup, reviews and failed work.

<a id="D06c8"></a>

#### D06.c8: Semantic PR annotations, source identities and review effort through rebases and upgrades
- Phases: Start work in P11. Accept this cell in P11.
- Must pass first: D06.c5, D29.c2, D27.c8.
- Baseline: Use applicable Sigasi and DVT review flows.
- Summary: Test semantic PR annotations, source identities and scripted review time through rebases and upgrades. Require exact annotations through rebase and two upgrades.
- Rule:
  1. Integrate semantic review with PRs.
  2. Give changed-state, port, behavior, lint and proof deltas stable source IDs and inline annotations.
  3. Use 100 sealed PRs per language in the fixed language axis.
  4. Use independently known deltas.
  5. Require exact annotations through rebase and two upgrades.
  6. Require zero stale or wrong-subject joins through those changes.
  7. Compare scripted review time, verified completion and tails against applicable Sigasi and DVT review flows under Section 3.1.

<a id="D06c9"></a>

#### D06.c9: Generator feedback latency, correctness and sealed edit locality at million-signal scale
- Phases: Start work in P11. Accept this cell in P11.
- Must pass first: D06.c2, D05.c1, D27.c8, D06.c11.
- Baseline: Use qualified Sigasi and DVT generator workflows.
- Summary: Test generator feedback latency, correctness and sealed edit locality at million-signal scale. Require Scala incremental compilation 95th-percentile at most 10 s.
- Rule:
  1. Create separate Spinal and Chisel incremental-generator-feedback children at at least 1 million elaborated signals.
  2. Freeze at least 100 edits per language across parameter, type, hierarchy and datapath families.
  3. Measure source edit to correct diagnostic and full source-to-RTL join.
  4. Require Scala incremental compilation 95th-percentile at most 10 s.
  5. Require elaboration 95th-percentile at most 20 s.
  6. Require total feedback time 95th-percentile at most 30 s.
  7. Report cold compilation and elaboration separately.
  8. Count failed and unsupported edits.
  9. Require zero stale joins.
  10. Compare completion, effort and latency against qualified Sigasi and DVT generator workflows under Section 3.1.
  11. Seal edit locality before outcomes using the checked incremental elaboration method IE27 dependency closure.
  12. For local type and width edits, require total source-edit-to-correct-feedback 95th-percentile at most 2 seconds, including joins.
  13. Keep original compilation, elaboration and total bounds for full-closure changes.
  14. Use the full closure for unknown locality.
  15. Do not relabel an edit with unknown locality as local after measurement.

<a id="D06c10"></a>

#### D06.c10: Authoring support for each required verification framework separately from runtime success
- Phases: Start work in P11. Accept this cell in P11.
- Must pass first: D05.c1, D06.c2, D29.c2, the interface contract from D13.c2, D27.c8.
- Baseline: Use Sigasi on identical authoring tasks.
- Summary: Test authoring support for each required verification framework separately from runtime success. Require zero wrong or stale joins.
- Rule:
  1. Create separate authoring-framework children for UVM, OSVVM, UVVM, VUnit and cocotb.
  2. Per framework, use at least 50 valid controls.
  3. Per framework, use at least 50 wrong-subject and semantic controls.
  4. Cover bench creation, completion, navigation, refactoring, diagnostics and source-to-generated-test joins.
  5. Require zero wrong or stale joins.
  6. Require zero accepted invalid edits.
  7. Compare verified completion with margin .005 versus Sigasi on identical tasks under Section 3.1.
  8. Compare machine time with margin 1.02.
  9. Compare tails with margin 1.20.
  10. Successful runtime execution cannot serve as editor evidence.
  11. Keep runtime receipts separate.
  12. Require all CPU-REQUIRED feature children for the Qualified CPU tier.
  13. Keep CPU-LOW-RELEVANCE feature children visible as OPEN until their own receipts pass.
  14. Require those children for a whole-vendor feature claim.
  15. Apply V26 independent task witnesses before results to each feature, including PSS and e-language tasks.
  16. Engine limits or failed controls cannot justify a low-relevance label.

<a id="D06c12"></a>

#### D06.c12: Emacs Eglot interoperability, feedback latency and safe semantic answers through two upgrades
- Phases: Start work in P12. Accept this cell in P12.
- Must pass first: D06.c9, D05.c1, D27.c8, D05.c6.
- Baseline: Use independent expected source locations and diagnostics.
- Summary: Test emacs Eglot interoperability, feedback latency and safe semantic answers through two upgrades. Require zero stale joins.
- Rule:
  1. Implement non-VS Code editor interoperability.
  2. Pin an Emacs Eglot LSP client and server versions.
  3. Repeat at least 100 navigation, diagnostic, rename and stale-generation controls per supported language, including Spinal and Chisel.
  4. Require identical source locations and diagnostics to independent expected results.
  5. Require zero stale joins.
  6. Require zero unsafe edits.
  7. Require local edit feedback 95th-percentile at most 2 seconds.
  8. Keep the 30 second bound for full-closure generator edits.
  9. Repeat through two independent upgrades.
  10. Require the semantic-index, language-server and elaboration-debug method decision in the method designs in protocols.md before this runtime result can close.

<a id="D06c13"></a>

#### D06.c13: Matched cross-language task effort and correctness without replacing native-language secondary gates
- Phases: Start work in P12. Accept this cell in P12.
- Must pass first: D06.c7, D05.c3, D06.c9, D27.c8.
- Baseline: Use Sigasi and DVT separately for the matched SystemVerilog flow.
- Summary: Test matched cross-language task effort and correctness without replacing native-language secondary gates. Require verified scripted checked-time upper ratio at most 0.90.
- Rule:
  1. Give Spinal, Chisel and SystemVerilog authors the same sealed behavioral requirement and change task.
  2. Use Sigasi and DVT separately for the SystemVerilog flow.
  3. Match functional outputs.
  4. Complete independent correctness checks.
  5. Use at least 30 independent tasks per language and generation before powered confirmation.
  6. Require verified scripted checked-time upper ratio at most 0.90.
  7. Require scripted recovery and checking time ratio at most 1.15.
  8. Require completion-tail ratio at most 1.20.
  9. Require zero wrong accepted changes.
  10. Include failed work and two upgrades.
  11. Report a separate cross-language label.
  12. This label cannot replace any native-language secondary child.

<a id="D07c2"></a>

#### D07.c2: Checked simulation capacity, deadlines, builds and visibility in every required design and state stratum
- Phases: Start work in P11. Accept this cell in P11.
- Must pass first: D07.c1, D07.c4, D11.c1, D13.c2 for UVM benches; D35.c2a demand, D27.c8.
- Baseline: Use the D07.c4 pinned generation and both VCS and Xcelium on matched hosts and useful work.
- Summary: Test checked simulation capacity, deadlines, builds and visibility in every required design and state stratum. Require at least 1.5 times checked work per core-second versus the exact generation pinned in the D07.c4 selection receipt.
- Rule:
  1. Accept simulation capacity only when every design and state stratum meets its checked-rate floor and all supporting gates.
  2. Use actual unchanged CPU benches for scalar, large-OoO and six-wide-coherent designs in both two-state and four-state modes.
  3. On a 16-core, 64-GiB host, require two-state checked sequential rate at least 100 kHz for scalar designs.
  4. On that host, require two-state checked sequential rate at least 20 kHz for large out-of-order designs.
  5. On that host, require two-state checked sequential rate at least 10 kHz for six-wide coherent designs.
  6. On the same host, require four-state checked sequential rate at least 20 kHz for scalar designs.
  7. On that host, require four-state checked sequential rate at least 4 kHz for large out-of-order designs.
  8. On that host, require four-state checked sequential rate at least 2 kHz for six-wide coherent designs.
  9. Activate X, Z and region controls.
  10. Check each cycle-rate floor in cycles per second. Separately check the D35.c2a demand-census retirement rate in checked retirements per second. Both checks must pass.
  11. Include capture, reference, cold builds, resident memory and sequential 1 billion and 10 billion chains.
  12. Require at least 1.5 times checked work per core-second versus the exact generation pinned in the D07.c4 selection receipt.
  13. Use that receipt's source, build and options generation.
  14. Compare checked rate, 95th-percentile and 99th-percentile completion, success and total cost against VCS and Xcelium under Section 3.1.
  15. Add manycore8 and manycore16 in both state modes.
  16. Include shared fabric, coherence, DMA and OS traffic with the cores.
  17. For 8 cores, require two-state checked cycle rate at least 5 kHz.
  18. For 16 cores, require two-state checked cycle rate at least 2 kHz.
  19. For 8 cores, require four-state checked cycle rate at least 1 kHz.
  20. For 16 cores, require four-state checked cycle rate at least 0.4 kHz.
  21. Keep the cycle-rate floors separate from the demand-derived checked-retirement-rate requirement.
  22. Use the same comparison endpoints and both commercial comparators on identical hosts and useful work.
  23. Apply Section 3.4 to substitute targets with the generated-manycore capacity label.
  24. Make no claim of a natural production chip from substitutes.
  25. Regardless of census, complete each 1 billion checked-retirement chain in at most 48 h, including capture and reference.
  26. Complete each 10 billion chain in at most 480 h on the same basis.
  27. Per stratum, check the stated cycle-rate floor. Separately require the maximum checked-retirement rate implied by the fallback deadlines and D35.c2a demand.
  28. Include mandatory strata for eight-wide designs with at least 600 ROB entries and ten-wide designs with at least 1000 ROB entries.
  29. Require scheduler capacity at least 256 entries in each width.
  30. Require active memory and coherence contention in each width.
  31. Apply every local gate separately to each width in both state modes against VCS and Xcelium.
  32. For the eight-wide stratum, require checked two-state cycle rate at least 8 kHz.
  33. For the ten-wide stratum, require checked two-state cycle rate at least 5 kHz.
  34. For the eight-wide stratum, require checked four-state cycle rate at least 1.6 kHz.
  35. For the ten-wide stratum, require checked four-state cycle rate at least 1 kHz.
  36. Apply demand and retirement deadlines to a separate checked-retirement-rate check. Do not compare retirements per second with cycles per second.
  37. For both widths, require cold-build 95th-percentile time at most 30 minutes.
  38. Require incremental build time at most 120 seconds.
  39. Require parameter-rebuild time at most 5 minutes.
  40. Retain complete debug visibility.
  41. Require exact trace joins in debug tests.
  42. No smaller width can close these children.
  43. Add a generated SoC stratum with at least 32 active processor instances, coherent fabric, DMA and interrupt controllers.
  44. Require at least 100 million live state bits before optimization.
  45. Independently verify the state-bit census and functional traffic.
  46. Padding and inactive replicas do not count.
  47. Test both state modes on unchanged useful work.
  48. Require at least 0.5 kHz in two-state mode.
  49. Require at least 0.1 kHz in four-state mode.
  50. Preserve every applicable build, visibility, reference, deadline and vendor-comparison gate.
  51. Label this generated SoC capacity.
  52. Keep natural transfer separate.

<a id="D07c5"></a>

#### D07.c5: Cold, incremental and parameter-build deadlines against both required simulators with unchanged instrumentation
- Phases: Start work in P11. Accept this cell in P11.
- Must pass first: D07.c1, D13.c2, D27.c8, the interface contract from D07.c2.
- Baseline: Use VCS and Xcelium with identical instrumentation.
- Summary: Test cold, incremental and parameter-build deadlines against both required simulators with unchanged instrumentation. Require cold-build 95th-percentile at most 30 min.
- Rule:
  1. Cold-build unchanged six-wide-coherent RTL with the complete reference, capture and UVM harness on the reference 16-core, 64-GiB host.
  2. Require cold-build 95th-percentile at most 30 min.
  3. Require single-file RTL incremental-rebuild 95th-percentile at most 120 s.
  4. Require parameter rebuild at most 5 min.
  5. Use at least 30 independent build tasks before powered tail studies.
  6. Permit no warmed cold cache.
  7. For cold build, compare against VCS and Xcelium under Section 3.1 with ratios at most 1.02.
  8. For incremental rebuild, apply the same comparisons and ratio bounds.
  9. For parameter rebuild, apply the same comparisons and ratio bounds.
  10. Use identical instrumentation.
  11. Include failed builds.
  12. Apply the complete mandatory width-stratum contract in D07.c2.
  13. Include both state modes, both vendors, rate floors, build limits and debug visibility.
  14. No smaller width can close these children.
  15. Apply the vendor comparison to cold build, incremental rebuild and parameter rebuild separately.

<a id="D07c6"></a>

#### D07.c6: Qualify simulation-rate superiority and all other comparison bounds in every required stratum
- Phases: Start work in P12. Accept this cell in P12.
- Must pass first: D07.c2, D27.c8, the interface contract from D07.c2.
- Baseline: Use both VCS and Xcelium in every required stratum.
- Summary: Test adjusted checked-rate lower ratio at least 1.10 against both VCS and Xcelium in every design and state stratum.
- Rule:
  1. Keep all other endpoints non-inferior under Section 3.1.
  2. Require total-cost ratio at most 1.02.
  3. Require time ratio at most 1.02.
  4. Require resident-memory ratio at most 1.02.
  5. Require capacity reciprocal loss at most 1.05.
  6. Use completion margin .005.
  7. Apply the proper Section 3.1 row to tails.
  8. Keep demand floors and semantics mandatory.
  9. Label a result that passes only D07.c2 NONINFERIOR, never an exact match.
  10. Require D07.c6 for the full benefit tier.
  11. Apply the complete mandatory width-stratum contract in D07.c2.
  12. Include both state modes, both vendors, rate floors, build limits and debug visibility.
  13. No smaller width can close these children.
  14. Include the generated SoC stratum from the simulation capacity contract as mandatory here.
  15. Apply the same superiority and noninferiority gates separately in both state modes against both vendors.
  16. Category 4 primary: Require adjusted checked-rate lower ratio at least 1.10 against both VCS and Xcelium in every design and state stratum.

<a id="D07c15"></a>

#### D07.c15: Single-host scaling and exact simulation semantics on each required wide design and state mode
- Phases: Start work in P12. Accept this cell in P12.
- Must pass first: D07.c2, D07.c4, D27.c8.
- Baseline: Use one thread on the same host and simulator generation, plus VCS and Xcelium under R08 (matched work and independent baseline-selection rules) matching rules.
- Summary: Test single-host scaling and exact simulation semantics on each required wide design and state mode. On one host, use unchanged six-wide coherent designs, eight-wide designs with at least 600 ROB entries and ten-wide designs with at least 1000 ROB entries.
- Rule:
  1. On one host, use unchanged six-wide coherent designs, eight-wide designs with at least 600 ROB entries and ten-wide designs with at least 1000 ROB entries.
  2. Pin 16, 32 and 64 physical worker threads with fixed memory and NUMA policy.
  3. Compare against one thread on the same host and simulator generation.
  4. For 16 worker threads, require checked-rate ratio lower bound at least 4 in each state mode.
  5. For 32 worker threads, require checked-rate ratio lower bound at least 6 in each state mode.
  6. For 64 worker threads, require checked-rate ratio lower bound at least 8 in each state mode.
  7. Include scheduling, capture, reference and failed work.
  8. Outputs, event regions, X and Z behavior and trace ends must match exactly.
  9. Compare checked rate and total cost against VCS and Xcelium under R08 and section 3.1.
  10. Permit GPU and fine-grained scheduling methods subject to all these gates.
  11. A restricted distributed label cannot close this single-host child.

<a id="D08c3"></a>

#### D08.c3: Qualify synchronization-aware multithreaded sampling against complete RTL execution and qualified sampled recipes
- Phases: Start work in P12. Accept this cell in P12.
- Must pass first: D08.c2, D01.c3c, D07.c2, D20.c4, D27.c8.
- Baseline: Use full multi-hart RTL execution and the strongest qualified synchronization-aware sampled recipe.
- Summary: Test synchronization-aware multithreaded sampling against complete RTL execution and qualified sampled recipes. Require at least 20 held-out full multi-hart RTL anchors per size and class.
- Rule:
  1. Implement multithreaded and multicore sampled simulation.
  2. Use SMARTS statistical sampling and synchronization-aware SimPoint region selection with LoopPoint or BarrierPoint style global-progress regions.
  3. Seal independent thread progress vectors, barrier and lock epochs, shared cache and coherence state before outcomes.
  4. Seal scheduler and device state, region weights and confidence estimators before outcomes.
  5. Cover 8, 16, 32 and 64 harts plus four-thread and eight-thread SMT.
  6. Include shared-memory, lock-heavy, barrier-heavy and asynchronous workloads.
  7. Require at least 20 held-out full multi-hart RTL anchors per size and class.
  8. Compare with full execution and the strongest qualified synchronization-aware sampled recipe selected on disjoint controls.
  9. Require total-cycle error at most 2 percent per class.
  10. Require synchronization-wait and contention error at most 5 percent.
  11. Apply original weight and warmup bounds.
  12. Require exact outputs and ordering.
  13. Double warmup repeatedly until drift is at most 1 percent.
  14. Keep the cell OPEN if this fails by 1 billion instructions or 24 hours.
  15. Require adjusted checked total-job cost ratio at most .90 against full execution.
  16. Require sampled-baseline error ratio at most 1.02.
  17. Include 100 phase-aliasing, barrier-misalignment, lock-handoff, erased-difference and state-omission controls per shape.
  18. Require all of them to fail qualification.
  19. Require workload-anchor consumers to use this typed receipt for multithreaded sampling.
  20. Functional work never counts as RTL.

<a id="D11c2"></a>

#### D11.c2: Qualify full lockstep checking and reference performance
- Phases: Start work in P11. Accept this cell in P11.
- Must pass first: D11.c1, D08.c2, D35.c2a; sealed demand floor, not completed simulator compare, D27.c8.
- Baseline: Unchecked execution and qualified ImperasDV full lockstep checking.
- Summary: Test the qualification of full lockstep checking and reference performance. Require an upper checked-to-unchecked time ratio at most 2.0.
- Rule:
  1. Run full lockstep OS and application chains with at least 1 billion checked retirements.
  2. Require an upper checked-to-unchecked time ratio at most 2.0.
  3. Require a resident-memory ratio at most 1.5.
  4. Keep the same trace obligations.
  5. Measure reference rates separately for scalar, wide, floating-point, vector and hypervisor execution.
  6. Each rate must be at least the maximum of effective D35.c2a retirement demand and 1 billion divided by deadline seconds.
  7. Measure each rate end to end, including transport.
  8. For sampling, execute intervening transitions or use a validated full restore.
  9. Detect erased differences.
  10. Without real saving keep full checking.
  11. Test two model upgrades and a fresh reference-defect corpus.
  12. Independently activate at least 100 sampling and restore differences inside skipped windows per state family.
  13. Include differences erased before the next sample.
  14. Detect all differences with the exact field and transition, or disable sampling for that family.
  15. Reject a restore that omits hidden memory, device or RNG state.
  16. Add ImperasDV as a required matched full-lockstep comparator.
  17. Require the fixed adjusted upper checked total-time ratio against ImperasDV to be at most .90.
  18. Use identical complete-state checks.
  19. Use identical erased-difference checks.
  20. Retain the absolute checked versus unchecked limit of 2.0 and all original bounds.

<a id="D11c8"></a>

#### D11.c8: Qualify a fast independent reference lineage
- Phases: Start work in P12. Accept this cell in P12.
- Must pass first: D11.c2, D27.c8.
- Baseline: The rate, overhead and resident-memory bounds described by D11.c2 as explanatory context only.
- Summary: Qualify a fast independent reference with no Sail-derived or Spike-derived executable semantics in every advertised stratum.
- Rule:
  1. It must meet every rate, overhead, resident-memory and erased-difference control described by D11.c2 as explanatory context only.
  2. Keep at least 1 billion checked chains and two model upgrades.
  3. Missing fast independent lineage blocks this receipt.
  4. Require separate scalar, wide, floating-point, vector, hypervisor and concurrent children for every advertised release stratum.
  5. Identify incomplete children as SINGLE-LINEAGE.
  6. Require that scalar success cannot close the conjunction.
  7. Before construction select the independently authored reference method in the method designs in protocols.md.
  8. Seal its ancestry target.
  9. Forbid Sail-derived executable semantics.
  10. Forbid Spike-derived executable semantics.
  11. Allow source review of architectural text.
  12. Record that review.
  13. Require its method decision and ancestry audit before any fast-reference qualification.
  14. Keep later oracle ancestry checks mandatory.

<a id="D12c3"></a>

#### D12.c3: Qualify concurrent reference correctness and capacity
- Phases: Start work in P10. Accept this cell in P12.
- Must pass first: D12.c1, D08.c1; independent memory-order specification, not DUT serialization, D35.c2a, D27.c8, D07.c2.
- Baseline: D35.c2a demand rate and the matched effective D07.c2 manycore producer rate.
- Summary: Test the qualification of concurrent reference correctness and capacity. Require zero wrong verdicts.
- Rule:
  1. Provide the concurrent reference service at 2, 4, 8 harts, and every larger advertised size.
  2. For each child, check at least 1 billion retired instructions.
  3. For each child, check at least 100 million memory events.
  4. Include up to 4096 outstanding events per hart.
  5. Inputs must include ambiguous allowed outcomes, long legal histories, dense read-from candidates, cyclic forbidden outcomes and checkpoint restores.
  6. Do not reject a legal serialization because you selected another legal serialization.
  7. Use independent bounded exhaustive graph truth and full-history checks.
  8. Test at least 100 activated forbidden controls per shape.
  9. Test 100 long legal controls per shape.
  10. Require zero wrong verdicts.
  11. Use a host with 16 cores and 64 GiB of memory.
  12. Require a checked retirement rate at least the maximum of 20 thousand retirements per second and the D35.c2a demand rate.
  13. Require resident memory at most 48 GiB.
  14. Require the 95th-percentile completion time for a 1 billion-history campaign to be at most the minimum of 24 h and the demand deadline.
  15. Require that restore retains order frontier and read-from alternatives, pending devices and checkpoints, with exact suffix agreement.
  16. Report memory growth and ambiguity curves.
  17. Require that resource exhaustion gives inconclusive.
  18. Require checked retirement throughput at least the effective end-to-end D07.c2 manycore retirement rate for the identical topology, state semantics, host allocation and workload.
  19. Use the maximum of this producer rate and both original floor terms.
  20. Concurrent producer-consumer runs must show no unbounded queue growth during the full 1 billion-history campaign.
  21. A producer-only or scalar rate cannot close this child.

<a id="D14c5"></a>

#### D14.c5: Compare industrial stimulus and AI coverage closure
- Phases: Start work in P11. Accept this cell in P11.
- Must pass first: D14.c2, D14.c4, D13.c2, D27.c8, D14.c9, D14.c7 as explanatory context only.
- Baseline: Breker, Valtrix STING, constrained-random UVM on VCS and Xcelium, Synopsys VSO.ai, Cadence Verisium and Xcelium ML, riscv-dv and Force-RISCV.
- Summary: Test checked new obligations per total core-hour lower ratio at least 1.10 against every strongest qualified industrial stimulus recipe under CC27.
- Rule:
  1. Compare industrial stimulus against independently qualified Breker AND Valtrix STING, plus a VCS and Xcelium constrained-random UVM flow using equal scripted tuning.
  2. For each complex unit class use the same requirements, mandatory closure, activated faults and at least 100 natural real-root-cause frame from D14.c4.
  3. Require the secondary adjusted total checked closure-time ratio upper bound at most .90 against EACH comparator.
  4. Require a scripted checked-time noninferiority ratio at most 1.15.
  5. Require a tail ratio at most 1.20.
  6. Require a sampled real-defect sensitivity noninferiority margin of .005.
  7. Block acceptance on any mandatory fault miss.
  8. Require that all failed generation and solving costs count.
  9. Freeze separate whole relevant feature frames for Breker scenario capabilities and STING ISA capabilities.
  10. Keep missing features required.
  11. Do not pool them silently.
  12. Full-release stimulus must require this superiority receipt and the full relevant PSS generation and inventory gates, not only open-generator yield.
  13. Additionally include the AI closure AND comparators Synopsys VSO.ai and Cadence Verisium and Xcelium ML.
  14. Each uses the entire relevant feature frame, equal training and tuning and held-out drift and cold-start tasks.
  15. Apply all existing superiority controls.
  16. Apply all existing noninferiority controls.
  17. Apply all other required controls.
  18. Require separate natural AND commissioned superiority receipts, with the original benefit and all non-inferior gates on each root-cause stratum.
  19. Print both in the headline.
  20. Require that commissioned success cannot rescue natural failure or a small natural frame.
  21. Freeze riscv-dv and Force-RISCV as additional required open floor comparators, with versions, full applicable capability frames and equal tuning budgets.
  22. Apply the original .90 checked closure-time secondary and all effort, tail, natural and commissioned sensitivity gates separately against each.
  23. Missing open-generator features remain explicit.
  24. Require that their smaller frame cannot reduce the vendor frame.
  25. Print full PSS OPEN in the release label until D14.c7 closes at P12.
  26. This coverage-closure benefit receipt cannot close full PSS.
  27. Create a separate required AI-closure comparison child for each VSO.ai and Verisium flow.
  28. Keep the original comparisons above.
  29. Use two separate training frames: cold start with no task-specific examples, and equal supplied training with identical independent examples, labels and total tuning budgets.
  30. Freeze vendor pretrained state.
  31. Document inaccessible training ancestry.
  32. Hold out workload families and future revisions.
  33. Apply all existing closure-time, effort, tail, natural and commissioned gates to each frame.
  34. If you cannot equalize prior data, label the native pretrained product result separately.
  35. In that case, keep the matched-training claim OPEN.
  36. Never describe hidden vendor pretraining as matched.
  37. Accept only the coverage-closure benefit at P11.
  38. Keep full PSS OPEN until D14.c7 closes at P12.
  39. Category 7 primary: Require checked new obligations per total core-hour lower ratio at least 1.10 against every strongest qualified industrial stimulus recipe under CC27.

<a id="D14c7"></a>

#### D14.c7: Qualify complete PSS scenario generation
- Phases: Start work in P12. Accept this cell in P12.
- Must pass first: D14.c3, D14.c5, D13.c2, D27.c8.
- Baseline: The whole relevant Breker feature frame.
- Summary: Test the qualification of complete PSS scenario generation. Run at least 50 legal, illegal and boundary controls per family.
- Rule:
  1. Implement the complete relevant PSS DSL and C++ scenario-generation path for actions, activity control, constraints, resources and pools, state and data flow, scheduling and concurrency, coverage and target-code realization.
  2. Use an independent standard-clause inventory.
  3. Run at least 50 legal, illegal and boundary controls per family.
  4. Require exact semantics for every feature, with no unsupported relevant clause.
  5. Generate synchronized multihart C and SV and UVM with checked expected outcomes and replay.
  6. Use the statistical comparison in section 3.1 for all-cost closure time and effort and sensitivity versus Breker whole relevant feature frame.
  7. Require the secondary closure-time ratio at most .90.
  8. Require all other statistical endpoints to be noninferior.
  9. Require exact mandatory-fault results.
  10. Missing features block whole-scope label.

<a id="D15c12"></a>

#### D15.c12: Compare solved counts on vendor-unsolved properties
- Phases: Start work in P11. Accept this cell in P11.
- Must pass first: D15.c7p1, D15.c7p2, D15.c7p3, D15.c7p4, D15.c7p5, D15.c7p6, D15.c7p7, D15.c7p8, D15.c7p9, D15.c7p10, D15.c11, D27.c8.
- Baseline: JasperGold and VC Formal on the vendor-unsolved property frame.
- Summary: Test the comparison of solved counts on vendor-unsolved properties. Seal a vendor-unsolved property frame on disjoint qualification tasks for JasperGold and VC Formal with a budget of 8 hours and 64 GiB per property.
- Rule:
  1. Seal a vendor-unsolved property frame on disjoint qualification tasks for JasperGold and VC Formal with a budget of 8 hours and 64 GiB per property.
  2. On fresh confirmation properties in that frame, require a positive adjusted lower difference in checked solved count against EACH vendor at the same budget.
  3. Keep every timeout, unknown and certificate failure in the denominator.
  4. Every promoted proof requires an independently checked certificate.
  5. Publish a required secondary superiority label.
  6. This cannot replace the fixed grid-time primary or exact proof obligations.

<a id="D18c8"></a>

#### D18.c8: Check UVM runtime debug
- Phases: Start work in P11. Accept this cell in P11.
- Must pass first: D18.c9, D13.c2, D27.c8.
- Baseline: Applicable Verdi, Verisium Debug and SimVision facilities.
- Summary: Test the correctness of UVM runtime debug. Require at least 50 valid and 50 invalid controls per family against H05.015 in Verdi and H22.001 in Verisium Debug.
- Rule:
  1. For UVM runtime debug, inspect dynamic objects and lifetime, inheritance, sequence arbitration, phases and objections, factory and configuration resolution and changed handles after restore.
  2. Require at least 50 valid and 50 invalid or stale cases per family with independently specified under the independence protocol R04 answers on unchanged full UVM benches.
  3. Require zero stale and lifetime errors through UP2, the two-upgrade protocol.
  4. Use the statistical comparison in section 3.1 for correct completion, debug time, effort and tails versus applicable Verdi AND Verisium Debug AND SimVision.
  5. Require that assertion or transport-only receipts cannot close this child.
  6. Compare H05.015 against Verdi UVM class, object and sequence inspection.
  7. Compare H22.001 runtime object-to-source and transaction joins against Verisium Debug.
  8. Seal independently enumerated runtime inspection features before confirmation.

<a id="D19c2"></a>

#### D19.c2: Qualify correct repair and vendor comparison
- Phases: Start work in P11. Accept this cell in P11.
- Must pass first: D19.c1; D24.c2 retention, D27.c8.
- Baseline: Verdi in every stratum through two upgrades.
- Summary: Test the qualification of correct repair and vendor comparison. Require zero accepted wrong repairs.
- Rule:
  1. Every attempt starts from original promoted artifact.
  2. Include transfer, instrumentation, rebuild, help, failed proposals and independent repair validation.
  3. Require zero accepted wrong repairs.
  4. Require adjusted correct-repair lower bound at least 0.90 for population claims.
  5. Use the statistical comparison in section 3.1 for correct completion, 95th-percentile time and total scripted checked repair time against Verdi in every stratum.
  6. Maintain these results through UP2, the two-independent-upgrade protocol.
  7. Abstain on an unobservable cause.
  8. Report it as not repaired.
  9. For census-limited closure, require an observed correct-repair fraction at least 0.90.
  10. For that closure, require direct finite-frame time and effort comparisons under the same margins.
  11. Report measurement uncertainty and effective power.
  12. Do not claim the population lower bound without evidence.

<a id="D19c3"></a>

#### D19.c3: Qualify commissioned defect repair
- Phases: Start work in P12. Accept this cell in P12.
- Must pass first: D19.c2, D27.c8. D19.c1 runtime receipt.
- Baseline: Use the baseline stated in the rule when a comparison applies.
- Summary: Test the qualification of commissioned defect repair.
- Rule:
  1. Label COMMISSIONED-DEFECT-REPAIR.
  2. Never label this result as natural-root-cause sensitivity.
  3. Retain original RTL and every failed attempt.
  4. Missing natural frame leaves that separate c1 and c2 natural claim OPEN, without blocking this commissioned tool capability.
  5. Use at least 100 separately generated tool-blind root causes per D19.c1 stratum.
  6. Require real repair validation and all D19.c2 thresholds.

<a id="D19c4"></a>

#### D19.c4: Qualify repair benefit against all three vendors
- Phases: Start work in P12. Accept this cell in P12.
- Must pass first: D19.c2, D27.c8, D18.c1. D19.c1 runtime receipt.
- Baseline: Verdi, Verisium Debug and SimVision, separately.
- Summary: Test checked complete-answer throughput lower ratio at least 1.10 against each Verdi, Verisium Debug and SimVision in every required root-cause stratum.
- Rule:
  1. Require prospective repair benefit for each major D19.c1 root-cause stratum against EACH Verdi, Verisium Debug and SimVision.
  2. Require a completion noninferiority margin of .005.
  3. Require the nonprimary total-time ratio for machine components at most 1.02.
  4. Require a scripted recovery-time ratio at most 1.15.
  5. Use independent task budgets.
  6. Require zero wrong repairs.
  7. Report separate receipts for natural and commissioned cohorts.
  8. Allow no pooled rescue.
  9. Apply RL24, the release-label protocol, to print separate natural and commissioned repair-benefit status in every category headline.
  10. Require that commissioned-only superiority cannot be exported as natural repair benefit.
  11. Require natural strata to pass separately.
  12. Require commissioned strata to pass separately.
  13. Use pinned scripted or agent runs and charge all failed attempts and checking time.
  14. Require secondary adjusted upper checked-result-time ratio at most 0.90 against each Verdi, Verisium Debug and SimVision in every required root-cause stratum.
  15. Category 10 primary: Require checked complete-answer throughput lower ratio at least 1.10 against each Verdi, Verisium Debug and SimVision in every required root-cause stratum.

<a id="D20c2b"></a>

#### D20.c2b: Execute and qualify the complete workload corpus
- Phases: Start work in P12. Accept this cell in P12.
- Must pass first: D20.c2a, D21.c1, D21.c2, D20.c4, D27.c8.
- Baseline: Use the baseline stated in the rule when a comparison applies.
- Summary: Test workload representativeness against the sealed behavior inventory. Keep the independent-family count as a required capacity measure.
- Rule:
  1. For the executed corpus receipt, execute EVERY eligible member of the sealed finite frame with at least 2 full inputs, two independent execution copies and full output and order and trace-end checks.
  2. Initial anchors must consume D21.c1.
  3. Require that all confirmation members consume D21.c2.
  4. Record all failed ports without deleting them.
  5. Require zero unaccounted members.
  6. Count, finite-performance, census and population claims must require this receipt, not the early frame method.
  7. Retain 225 and 899 independent families per class as required population ambition.
  8. If the dated complete natural universe is smaller, close only the finite route in 3.4, with exact deficit and generated supplement labeled separately.
  9. Apply every sub-stratum family and input and calibration requirement in D20.c4.
  10. Report bias, precision, power and MDE and ancestry.
  11. This receipt accepts unsampled full anchors only.
  12. It must reject substituted sampled anchors.
  13. Use the separate child for sampled corpus acceptance.
  14. When deployment weights are unavailable, publish the supported Qualified headline as QUALIFIED-EQUAL-CLASS.
  15. Give each of the seven classes weight one seventh.
  16. Retain all class floors, missing mass and response-transfer gates.
  17. Do not describe equal-class results as deployment performance.
  18. Category 11 primary: Require an adjusted upper bound of at most 5% for unrepresented behavior weight in every workload class against the sealed D20.c4 behavior inventory, using executed and calibrated full anchors.
  19. Compute unrepresented behavior weight as the D20.c4 debt weight. Include missing operators, scalar fallback, unsupported shapes and unqualified useful-work mappings. Freeze behavior weights and the inventory before corpus selection.
  20. Use equal-family weights and, when qualified, deployment weights as separate frames. Check every required sub-stratum with full anchors and calibrated families. Family count alone cannot establish representativeness.
  21. Keep the 899-family population requirement and the finite-route deficit rules. Do not turn a small census or a generated supplement into population representativeness.

<a id="D21c2"></a>

#### D21.c2: Check detailed RTL anchors and hybrid execution
- Phases: Start work in P11. Accept this cell in P11.
- Must pass first: D21.c1, D08.c2 for hybrid claims, D20.c1, D27.c8.
- Baseline: Complete detailed RTL anchors are the references for hybrid paths.
- Summary: Test complete RTL anchors and hybrid accuracy for every required workload phase and service load. Require at least 20 independent complete-anchor episodes for each such phase and load.
- Rule:
  1. Provide complete detailed RTL anchors for each D20.c1 confirmation family.
  2. Keep failed ports marked missing.
  3. Use existing capable targets.
  4. Check Linux boot plus 1M userspace instructions, 20 platform tests and four-hour kernel and guest stress.
  5. Check 20 timer, trap, context and device sequences each for RTOS and SBI, including 10 recovery controls.
  6. Include startup, steady operation, GC, JIT, I/O and tails at three service loads with background work.
  7. Use 1,000 lawful traces that preserve provenance, output and order.
  8. These traces must add no families.
  9. Validate hybrid paths against complete anchors.
  10. For each applicable phase at each service load, require exact output, order and trace end.
  11. Require at least 20 independent complete-anchor episodes for each such phase and load.
  12. Limit hybrid median timing error to at most 2%.
  13. Limit hybrid 95th-percentile timing error to at most 5%.
  14. Limit hybrid throughput error to at most 2%.
  15. For claims about the minimum relevant effect (effect_min), require bias plus uncertainty at most effect_min divided by 2.
  16. Make at least 20 missing-phase and time-boundary mutants fail.
  17. Keep unobserved applicable phases OPEN.

<a id="D22c2"></a>

#### D22.c2: Check missing deployment weight and transport
- Phases: Start work in P12. Accept this cell in P12.
- Must pass first: D22.c1, D21.c2, D27.c8.
- Baseline: Use the baseline stated in the rule when a comparison applies.
- Summary: Test missing measured weight, selection sensitivity and fresh deployment transport. Limit the upper missing measured weight to at most 5% per class, per organisation and combined.
- Rule:
  1. Use a later complete window for each organisation.
  2. Limit the upper missing measured weight to at most 5% per class, per organisation and combined.
  3. Require worst-case selection and bias plus uncertainty at most half the minimum relevant effect (effect_min).
  4. Include inclusion-odds sensitivity from 1 divided by 2 to 2 and plausible absent strata.
  5. For each cache by translation by speculation interaction, require two independent natural families with complete anchors.
  6. Residual debt cannot reverse effect_min.
  7. Unknown sensitivity must forbid a broad claim.
  8. Detect all hidden missing episodes and rank reversals in controlled records.
  9. Require exact weights.
  10. Use fresh independently sampled controlled deployment records for transport-calculator tests.
  11. Controlled data must never claim real adoption or all-user representation.
  12. Test weighting and transport on independently specified controlled records.
  13. Keep conclusions conditional on the supplied sampling model.

<a id="D24c1"></a>

#### D24.c1: Check farm availability and recovery
- Phases: Start work in P10. Accept this cell in P11.
- Must pass first: D23.c1, R04 (independent requirement-derived expectations and separate producer and checker implementation ancestry) expected coverage inventory, D35.c2a, D27.c8, D24.c8, D14.c1 (explanatory context only; it supplies no acceptance evidence), D12.c3 (explanatory context only; it supplies no acceptance evidence).
- Baseline: Use vManager and IMC for matched cost, completion, deadline and recovery comparisons.
- Summary: Test six-month farm availability, service-class deadlines and recovery under the required loads. Require availability at least 99.9% for six months, including controller, store, worker, reference-service and reconnect failures.
- Rule:
  1. For #25, run six months of real heterogeneous complete jobs.
  2. Include two overlapping releases, global invalidation, controller and store loss, and reconnect storms.
  3. Permit labeled controlled offered load from archived or commissioned jobs.
  4. Require availability at least 99.9%.
  5. Require accepted-generation recovery point objective of 0.
  6. Limit recovery time objective RTO to at most 15 min.
  7. Seal per-class 99th-percentile queue and completion deadlines from an independent demand census before tuning.
  8. At occupancy at most 70%, limit wait to at most 2 times the reservation.
  9. At 100%, 125% and 150% offered load, provide explicit refusals and queue policy.
  10. Recover deadlines at most 1 h after normal load returns.
  11. Compare cost, completion, deadlines and recovery against vManager and IMC statistically under section 3.1.
  12. Service open coverage holes correctly without the complete D14.c1 prerequisite.
  13. Register a separate concurrent-order-checking service class using the sealed schema interface from D12.c3.
  14. Report the service class demand, rate, resident memory and deadlines separately from aggregate simulation throughput.
  15. Measure availability per critical service class and in aggregate every minute for the six-month window.
  16. Calculate availability as successful checked end-to-end probe transactions divided by all eligible scheduled transactions.
  17. Each probe must admit a fixed reference job.
  18. Each probe must execute on a worker.
  19. Each probe must check its output against the independently specified R04 expected output.
  20. Each probe must commit artifacts.
  21. Each probe must retrieve the accepted generation before the class deadline.
  22. Seal load eligibility, class weights and windows before tuning.
  23. Include 0–70% declared capacity and scheduled load tests in load eligibility.
  24. Keep planned maintenance in the denominator.
  25. Make partial class outages fail that class.
  26. The aggregate cannot mask a class outage.
  27. Start an outage at the first failed transaction.
  28. End it only after three consecutive successful probes.
  29. Charge intervening minutes as unavailable.
  30. A responsive API with a dead worker, reference service or artifact store must count as unavailable for each blocked class.
  31. Report raw per-class counts and durations.
  32. Require both availability ratios at least .999, with no discarded failures.

<a id="D24c3"></a>

#### D24.c3: Check physical RTL scale and efficiency
- Phases: Start work in P11. Accept this cell in P12.
- Must pass first: D24.c1, D26.c1, D28.c2; distributed nodes cannot replace single-job gates, D27.c8.
- Baseline: Use the baseline stated in the rule when a comparison applies.
- Summary: Test measured RTL throughput, adjacent-stage efficiency, costs and result trust across all scale stages. Require all three daily retirement floors at every listed node stage, including the 1 trillion floor.
- Rule:
  1. Use actual stages of 8, 16, 32, 64, 128, 256 and 512 sixteen-core nodes.
  2. Require at least 10B, 100B and 1T physically executed state- and output-checked RTL retirements per day at the registered mix.
  3. For each adjacent pair, require adjacent-stage efficiency at least .80.
  4. Define stage efficiency as the checked-rate ratio divided by the node-count ratio, with the later stage in each numerator.
  5. Also require efficiency from 8 to 512 nodes at least .80.
  6. Include reference, cold build, storage, scheduling, failed work and retries in rate under the same registered mix.
  7. Measure intermediate rates and costs, with no interpolation.
  8. Include at least 20% wide and large work and at least 20% memory and system work.
  9. Publish their overlap.
  10. Keep proof, fuzz and simulation billed hours separate.
  11. Count no sampled or functional work as RTL.
  12. Independently measure RAM packing, references, cold builds, failures, artifacts and all cost.
  13. Use signed workers, lease fencing, quotas and admission controls.
  14. Test malicious-result substitution.
  15. Quarantine untrusted results until independent rerun and certificate checks complete.
  16. Distributed nodes cannot replace single-job gates.
  17. Require all three daily retirement floors at every listed node stage, including the 1 trillion floor.

<a id="D24c4"></a>

#### D24.c4: Check mixed-work scheduling
- Phases: Start work in P11. Accept this cell in P12.
- Must pass first: D24.c1, D35.c2a, D27.c8.
- Baseline: Use the baseline stated in the rule when a comparison applies.
- Summary: Test scheduling deadlines, preemption and bounded blocking for every admitted class. Use at least 100 independent adversarial arrival and resource traces per class for mixed proof, simulation and reference scheduling.
- Rule:
  1. Use at least 100 independent adversarial arrival and resource traces per class for mixed proof, simulation and reference scheduling.
  2. Test 70%, 100%, 125% and 150% offered loads.
  3. Allow no runnable admitted class to starve beyond its frozen deadline.
  4. On high-priority arrival, preempt or checkpoint a preemptible low-priority job within 30 s.
  5. For nonpreemptible reservations, register bounded blocking at most 5 min or refuse explicitly.
  6. Test priority inversion, lock-holder loss and GPU and large-RAM reservations separately.
  7. Deadline misses cannot hide in aggregate averages.

<a id="D24c5"></a>

#### D24.c5: Check sustained farm efficiency
- Phases: Start work in P11. Accept this cell in P12.
- Must pass first: D24.c1, D23.c2, D27.c8.
- Baseline: Use vManager and IMC, Synopsys VC Execution Manager and Verdi Planner.
- Summary: Test sustained allocated-core-cost benefit and all other gates against the required campaign managers. Require other endpoints to be non-inferior under section 3.1 with frozen budgets.
- Rule:
  1. Require the adjusted upper total checked-campaign allocated-core-cost ratio at most .90 against vManager and IMC.
  2. Apply this bound to the registered mix and each critical proof, simulation and reference class.
  3. Use equal deadlines and identical closure obligations.
  4. Require other endpoints to be non-inferior under section 3.1 with frozen budgets.
  5. Require exact availability and recovery controls.
  6. Include scheduler, storage, failure and replay overhead.
  7. Also compare matched checked-campaign planning and execution against both Synopsys VC Execution Manager and Verdi Planner.
  8. Apply R08, the comparator-matching protocol, to whole relevant feature frames.
  9. Retain all existing metric and benefit gates.

<a id="D24c6"></a>

#### D24.c6: Check fair admission and accounting
- Phases: Start work in P11. Accept this cell in P12.
- Must pass first: D24.c1, D23.c1, D27.c8.
- Baseline: Use vManager and VC Execution Manager.
- Summary: Test per-user and per-project scheduling, quotas, leases and exact retry accounting. Test at least 100 independent overload, priority, starvation, quota and lease-loss cases.
- Rule:
  1. Provide fair scheduling, reservations and quota enforcement per user and project through the farm, CLI and MCP.
  2. Test at least 100 independent overload, priority, starvation, quota and lease-loss cases.
  3. Require exact expected admission and accounting.
  4. Permit no starvation.
  5. Recover leases in at most 30 s.
  6. Bill each physical retry attempt once.
  7. Never duplicate accepted work.
  8. Compare queue, completion and cost against both vManager and VC Execution Manager under section 3.1 statistical rules.
  9. A ReqIF receipt cannot close scheduling.

<a id="D24c7"></a>

#### D24.c7: Check tenant authority
- Phases: Start work in P11. Accept this cell in P12.
- Must pass first: D24.c1, D26.c2, D27.c8.
- Baseline: Use the baseline stated in the rule when a comparison applies.
- Summary: Test tenant roles, access controls and accounting across every service path. Require zero unauthorized reads or actions.
- Rule:
  1. Use versioned user and project roles for read, visibility, submit, cancel, quotas and publication.
  2. Apply them through the farm, CLI and MCP.
  3. Test at least 100 denied-read, cross-user-cancel, quota-exhaustion, revoked-credential, lease-recovery and retry-accounting controls per path.
  4. Require zero unauthorized reads or actions.
  5. Require exact quota and accounting results.
  6. No retention receipt can establish tenant isolation.
  7. Require an independent expected access matrix.
  8. Require positive controls.
  9. Require two upgrades.

<a id="D25c5"></a>

#### D25.c5: Check surface parity and shared agent campaigns
- Phases: Start work in P11. Accept this cell in P11.
- Must pass first: D25.c2, D29.c5, D27.c8.
- Baseline: Use the strongest qualified single-agent and scripted recipes.
- Summary: Test complete CLI and MCP parity and the required multi-agent campaign benefit. Require zero missing information or extra authority.
- Rule:
  1. Map every required action, query, status, subscription and export to CLI and MCP.
  2. Keep the same permissions, generation, cancellation and evidence.
  3. Independently enumerate 100% of features.
  4. Run matched positive, denied, stale and unknown cases for each feature.
  5. Require zero missing information or extra authority.
  6. A missing CLI or MCP capability must block its capability advertisement and full release.
  7. Require long-campaign strata with 2, 5 and 10 agents sharing one sealed campaign through failures and two upgrades.
  8. Require zero duplicate or conflicting accepted actions.
  9. Retain rejected attempts and all coordination costs.
  10. Against strongest qualified single-agent and scripted recipes, require verified campaign-time upper ratio at most .90.
  11. Require machine cost ratio at most 1.02.
  12. Require sampled quality non-inferiority with margin .005.
  13. Use independent action and outcome adjudication.

<a id="D25c10"></a>

#### D25.c10: Check human evidence views
- Phases: Start work in P12. Accept this cell in P12.
- Must pass first: D25.c5, D27.c8.
- Baseline: Use the baseline stated in the rule when a comparison applies.
- Summary: Test complete human-readable evidence views for every CLI and MCP operation. Require 100 percent bidirectional parity.
- Rule:
  1. Enumerate every CLI and MCP operation and its result schema.
  2. Provide a human-readable evidence view for each operation.
  3. Keep the same identities, authority, errors, trust state and complete receipt links.
  4. Require exact bidirectional parity of 100 percent.
  5. For each operation family, use an independent checker implementation to reproduce accept or refuse decisions for at least 20 positive and 20 negative cases without hidden agent state.
  6. Missing views must block publication of that operation.

<a id="D28c5"></a>

#### D28.c5: Audit field escapes
- Phases: Start work in P11. Accept this cell in P11.
- Must pass first: D28.c3, D27.c2, D23.c2, D27.c8.
- Baseline: Use the baseline stated in the rule when a comparison applies.
- Summary: Test every retained accepted verdict, later defects and separately labeled finite and population escape rates. Require zero mandatory soundness escapes.
- Rule:
  1. At every release, use every accepted verdict in the dated retained release frame as the denominator.
  2. Independently adjudicate later natural defect discoveries.
  3. Retract wrong accepts.
  4. Invalidate dependents.
  5. Count all found wrong accepts in the escape numerator.
  6. Count unresolved cases as adverse.
  7. Require complete natural-frame finite escape rate at most .01.
  8. Require zero mandatory soundness escapes.
  9. Keep powered population upper bound at most .01 as a separate tier.
  10. Use its actual local alpha and follow-up censoring model.
  11. Do not treat zero observed escapes as proof of no escape.
  12. For incomplete or small natural frames, supplement a separately labeled tool-audit receipt with section 3.4 commissioned histories.
  13. Never claim natural incidence from seeds.
  14. Require two independently R04-authored retrospective audits to reconcile identities and counts exactly.
  15. Make all planted delayed discoveries revoke affected receipts.
  16. For each exact-oracle family, publish audited field escapes divided by independently audited field decisions in the release label vector.
  17. Include counts, exposure interval, unknown cases and uncertainty.
  18. Audit all severe escapes.
  19. Treat zero observed escapes as a finite observation, never an analytic correctness bound.
  20. Reopen affected exact judgments for shared ancestry.
  21. Category 14 primary: Require zero mandatory soundness escapes and a complete natural-frame finite escape rate of at most .01 against two independent retrospective verdict audits. Keep the powered population upper bound of at most .01 separate.

<a id="D30c7"></a>

#### D30.c7: Check existing-silicon test adapters
- Phases: Start work in P11. Accept this cell in P11.
- Must pass first: D30.c1, D09.c1, D37.c6 (sealed independently specified schema interface only; it supplies no runtime result), D27.c8.
- Baseline: Use the qualified native target runner for verified completion, run and setup time, and total cost.
- Summary: Test portable execution, independent output verification and exact refusal across two existing-silicon interfaces. Require zero wrong accepts.
- Rule:
  1. Pin program, input and image identity, target firmware and observation limits.
  2. Expose deploy, reset, run, timeout, cancel and partial-result status.
  3. Independently check completion and software outputs.
  4. Keep missing observations unknown.
  5. Test two distinct existing-silicon interfaces.
  6. Use one OS process and SSH interface.
  7. Use one bare-metal debug and probe interface.
  8. Use at least 100 wrong-image, truncated-result, disconnect, timeout and cancel controls per interface.
  9. Require zero wrong accepts.
  10. Require exact replayed outputs on at least 100 programs.
  11. Compare verified completion, run and setup time, and total cost against the qualified native target runner under section 3.1 statistical rules.
  12. Use test-access metadata only as a sealed schema interface dependency from D37.c6 where used.
  13. This cell must not require a new core.

<a id="D32c7"></a>

#### D32.c7: Qualify tool code and executable documentation
- Phases: Start work in P11. Accept this cell in P11.
- Must pass first: D32.c1, D28.c3f, D27.c8.
- Baseline: Use the baseline stated in the rule when a comparison applies.
- Summary: Test tool tests, security, rebuilds and separate native execution coverage for all shipped command examples. Require at least 90% changed executable-line coverage.
- Rule:
  1. Require unit, integration and property tests for each public contract and error path of every shipped tool.
  2. Require at least 90% changed executable-line coverage.
  3. Require at least 80% branch coverage.
  4. Require 100% coverage of mandatory verdict and authority branches.
  5. Require at least 70% activated non-equivalent mutation kill rate overall.
  6. Require 100% kill rate for mandatory trust and authority mutants.
  7. Keep unknown equivalents open.
  8. Fuzz every untrusted parser, schema and archive boundary for at least 24 CPU-hours per release.
  9. Use at least 1M valid and invalid inputs per parser.
  10. Retain crashes.
  11. Require zero unresolved exploitable or verdict-changing defects.
  12. Run static analysis and dependency scans on every change.
  13. Require zero unresolved critical or high findings.
  14. Reproduce seeded injection, overflow, path and serialization faults.
  15. Apply critical dependency security updates within 48 h.
  16. Apply high dependency security updates within 7 days.
  17. Require qualified replacements for unsupported dependencies.
  18. Require two independent clean rebuilds per host and release.
  19. Report coverage exceptions without closing missing mandatory paths.
  20. Inventory every command example in shipped documentation.
  21. Run 100 percent of applicable examples in isolated native CI on each stated host and version.
  22. Use UP2 to maintain these results through two independent upgrades.
  23. Check expected exit, output, receipt and cleanup.
  24. An unexecuted example cannot count as executed.
  25. Test 20 stale-command and misleading-output mutants.
  26. Require all mutants to fail.
  27. Keep documentation coverage separate from code coverage.

<a id="D35c2b"></a>

#### D35.c2b: Qualify decision-service capacity and deadlines
- Phases: Start work in P11. Accept this cell in P12.
- Must pass first: D35.c2a, D35.c1, D24.c1, D27.c8.
- Baseline: Use the baseline stated in the rule when a comparison applies.
- Summary: Test complete service jobs and overload recovery under independent RTL audits. Require idea-to-checked-model 95th-percentile time at most the minimum of 2 h and the demand deadline.
- Rule:
  1. Run all D35.c2a service jobs in three 30-day windows across three generations and two compilers.
  2. Independently audit the top five and at least 10% stratified rejects with RTL.
  3. Raise the RTL count as needed.
  4. Require idea-to-checked-model 95th-percentile time at most the minimum of 2 h and the demand deadline.
  5. Require model-to-complete-RTL 95th-percentile time at most the minimum of 48 h and the demand deadline.
  6. At 125% and 150% load, explicitly refuse or queue jobs.
  7. Recover normal deadlines within 1 h.
  8. Never treat service counts as correctness counts.

<a id="D35c3"></a>

#### D35.c3: Qualify direct-input machine decision screening
- Phases: Start work in P12. Accept this cell in P12.
- Must pass first: D02.c2, D21.c2, D28.c3, D33.c1 (explanatory context only; no acceptance evidence) and D34.c1 (explanatory context only; no acceptance evidence) applicable admission receipts, D33.c1, D34.c3, D27.c8. D35.c1 runtime receipt.
- Baseline: Use the strongest qualified gem5, performance-monitoring-unit and native simulation-debug-campaign chain, including a production micro-operation recipe if available.
- Summary: Test adjusted allocated-core-hour cost per checked retained decision upper ratio at most 0.90 against each required pinned gem5, PMU, native simulation and debug recipe.
- Rule:
  1. Accept only the named direct-input machine screening frame here.
  2. Keep the direct-input and proxy comparison receipts separate.
  3. Use prospective hidden predictor, issue, memory and hierarchy changes with natural full inputs.
  4. Use three structural generations and two compilers.
  5. Use at least 30 decision clusters per mechanism for the pilot, then expand for powered confirmation.
  6. Seal prediction and selection before independent RTL.
  7. Require adjusted correct-resolution lower bound at least .90.
  8. Require zero false accepted gains.
  9. Retain all finite known winners.
  10. Verify retained decisions and complete cost logs in the machine receipt.
  11. Require nonprimary time and cost non-inferiority under section 3.1.
  12. Require sampled resolution and winner non-inferiority with margin .005.
  13. Compare with the strongest qualified gem5, performance-monitoring-unit and native simulation-debug-campaign chain.
  14. R04 requires independent requirement-derived expectations and recorded producer and checker ancestry.
  15. Include a production micro-operation recipe if available.
  16. Historical D35.c1 gain cannot replace this result.
  17. Include wide8-rob600 and wide10-rob1000 decision axes with all original mechanisms, generations and absolute uncertainty gates.
  18. Require 95th-percentile time as a non-inferiority endpoint.
  19. Permit its optional superiority label only with a separate budget.
  20. It cannot rescue a failed Category 19 cost primary.
  21. Keep every other local benefit measure in this category secondary.
  22. Cover direct open-suite inputs only.
  23. Refuse proxy advice.
  24. Use a separate acceptance child for the proxy route.
  25. Permit a separate Machine-screened for the named frame label to state only direct open-suite resolution and retained-winner correctness for this exact P12 frame.
  26. It cannot claim proxy transport or machine-cost superiority without the matching comparison receipts.
  27. Human productivity remains an owner task.
  28. Use D33.c1 and D34.c1 as explanatory context for applicable admission receipts.
  29. Run scripts or pinned agents under identical task and tuning budgets.
  30. Charge rejected alternatives, late winners, reference checks and security checks.
  31. Category 19 primary: Require adjusted allocated-core-hour cost per checked retained decision upper ratio at most 0.90 against each required pinned gem5, PMU, native simulation and debug recipe.

## M6: Prove scale and complete the design loop

Acceptance phases: P13–P15.

<a id="D01c11"></a>

#### D01.c11: Natural high-end transfer separately for every required geometry class and lineage
- Phases: Start work in P13. Accept this cell in P13.
- Must pass first: D01.c1, D01.c9, D01.c3, D27.c8. D01.c3a runtime receipt; D01.c3b runtime receipt; D01.c3c runtime receipt.
- Baseline: Use the baseline stated in the rule when a comparison applies.
- Summary: Test natural high-end transfer separately for every required geometry class and lineage. Use a build and geometry census to select two unrelated natural lineages in EACH geometry class.
- Rule:
  1. Use a build and geometry census to select two unrelated natural lineages in EACH geometry class.
  2. For the first class, require dispatch and retirement width at least 8.
  3. For the first class, require at least 600 ROB entries.
  4. For the second class, require dispatch and retirement width at least 10.
  5. For the second class, require at least 1000 ROB entries.
  6. Seal predictions before refitting.
  7. Apply all original model cycle-error, event-error, intervention-direction, fidelity, cost and effort gates separately per class and lineage.
  8. No generated or smaller target can close these children.
  9. Retain smaller and generated tiers with their own labels.
  10. Apply D01.c3a, D01.c3b and D01.c3c as the complete D01.c3 family.

<a id="D01c14"></a>

#### D01.c14: Qualify partitioned full-system anchors using the exact distributed feasibility receipt
- Phases: Start work in P14. Accept this cell in P14.
- Must pass first: D01.c3c, D07.c14, D27.c8.
- Baseline: Use the baseline stated in the rule when a comparison applies.
- Summary: Test partitioned full-system anchors using the exact distributed feasibility receipt. Execute every sealed point for each of 8, 16, 32 and 64 harts. Require at least 20 points per size.
- Rule:
  1. Apply every topology, coherence, device, traffic, functional retirement, count, trace-end, suffix, wall-time and core-hour gate of D01.c3c to partitioned anchor production.
  2. Require the D07.c14 feasibility receipt for the exact partition and traffic frame before use.
  3. Execute all at least 20 points for each of 8, 16, 32 and 64 harts.
  4. Test 20 positive partitions.
  5. Test 20 missing or mismatched feasibility receipts.
  6. Missing receipts must refuse partitioned anchors.
  7. A smaller hart count cannot replace a full-system anchor.

<a id="D02c4"></a>

#### D02.c4: Qualify proxy architecture advice only within a valid response-transfer receipt and all inherited model bounds
- Phases: Start work in P15. Accept this cell in P15.
- Must pass first: D02.c2, D20.c9, D27.c8.
- Baseline: Use independent RTL anchors and all inherited D02.c2 comparison bounds.
- Summary: Test proxy architecture advice only within a valid response-transfer receipt and all inherited model bounds. Test at least 20 positive in-range recommendations against independent RTL anchors and 20 missing, stale or out-of-range receipts.
- Rule:
  1. Apply every prediction interval, fidelity, direction, effort and cost bound of D02.c2 to proxy advice.
  2. Consume the exact D20.c9 response-transfer receipt for the architecture, intervention and workload frame.
  3. Test at least 20 positive in-range recommendations against independent RTL anchors and 20 missing, stale or out-of-range receipts.
  4. All valid controls must produce correct advice.
  5. All invalid controls must refuse advice.
  6. A matched calibration summary cannot authorize transport.
  7. Without the receipt, refuse advice.
  8. Source-only receipts must also fail.

<a id="D06c14"></a>

#### D06.c14: Refactor generated RTL across generator versions
- Phases: Start work in P12. Accept this cell in P13.
- Must pass first: D06.c12, D05.c6, D27.c8.
- Baseline: Use Sigasi and DVT review workflows on identical generated hierarchies.
- Summary: Test generated-RTL hierarchy refactoring across generator versions. Require zero unsafe edits or stale review annotations across 100 changes per language.
- Rule:
  1. Test at least 100 hierarchy changes per language across two generator upgrades on three independent lineages.
  2. Include split, merge, rename, parameter and duplicate-name transformations.
  3. Require exact source and generated identity joins.
  4. Require zero unsafe edits or stale review annotations.
  5. Prove semantic preservation for accepted refactorings.
  6. Refuse ambiguous mappings.
  7. Require verified scripted review-time upper ratio at most .90 against both qualified workflows.
  8. Keep all original editor correctness and latency gates.

<a id="D07c7"></a>

#### D07.c7: Exact distributed execution, checked-rate benefit and partitionability-specific scaling for one large design
- Phases: Start work in P13. Accept this cell in P14.
- Must pass first: D07.c6, D08.c1, D27.c8, D07.c14.
- Baseline: Use single-host execution and the best qualified VCS and Xcelium distributed recipes where offered.
- Summary: Test exact distributed execution, checked-rate benefit and partitionability-specific scaling for one large design. Require exact event, region, state and output equivalence to single-host execution on unchanged four-state and UVM benches.
- Rule:
  1. Distribute ONE large design over 1, 2, 4 and 8 hosts.
  2. Implement a partition scheduler, cross-host event synchronization and deterministic checkpoints.
  3. Require exact event, region, state and output equivalence to single-host execution on unchanged four-state and UVM benches.
  4. Include delay, X-resolution and rollback controls.
  5. Require secondary checked-rate lower workstation-to-baseline ratio at least 1.10 at 8 versus 1 host.
  6. Report every scaling point.
  7. Require non-inferior total core-cost ratio at most 1.02 versus the best qualified distributed VCS and Xcelium recipes where offered.
  8. Document any missing vendor distributed mode before benchmark design.
  9. Still require independent exact controls for candidate distributed functionality.
  10. Use the strongest lawful vendor execution recipe for whole-scope comparison, not a nonexistent mode.
  11. On independently classified partitionable designs, require checked-rate lower bound at least 3 times at eight hosts.
  12. On independently classified partitionable designs, require scaling efficiency at least .375.
  13. Publish 1, 2, 4 and 8-host curves including synchronization and capture.
  14. Qualification cannot reclassify a slow design after results.
  15. Require the six-wide-coherent stratum for feasibility testing.
  16. Use D07.c14 to decide its partitionability before confirmation.
  17. Keep the at least 3 times endpoint required on designs certified partitionable by that receipt.
  18. Permit only the explicit restricted scaling label from a certificate of infeasibility.
  19. Never use that certificate for a passing six-wide scaling claim of at least 3 times.
  20. Seal its cut and traffic inventory before benchmark construction.
  21. Keep this child OPEN after failed scaling of at least 3 times.
  22. Reclassification cannot rescue it.

<a id="D07c8"></a>

#### D07.c8: Complete debug visibility and selective-capture costs against both required simulators
- Phases: Start work in P13. Accept this cell in P13.
- Must pass first: D07.c6, D18.c1, D27.c8, the interface contract from D07.c2.
- Baseline: Use VCS and Xcelium at identical visibility with complete source joins.
- Summary: Test complete debug visibility and selective-capture costs against both required simulators. Compare elapsed time, resident memory and storage under Section 3.1 with ratios at most 1.02.
- Rule:
  1. Create separate full-visibility and selective-capture children per design and state stratum for debug-ready simulation.
  2. Compare dump-on and dump-off time with VCS and Xcelium at identical signal and event visibility.
  3. Compare bytes per event with both vendors at the same visibility.
  4. Require complete source joins.
  5. Compare elapsed time, resident memory and storage under Section 3.1 with ratios at most 1.02.
  6. Require exact trace equality after canonical encoding.
  7. Loss of visibility cannot buy speed.
  8. Apply the complete mandatory width-stratum contract in D07.c2.
  9. Include both state modes, both vendors, rate floors, build limits and debug visibility.
  10. No smaller width can close these children.

<a id="D07c14"></a>

#### D07.c14: Qualify distributed simulation feasibility before benefit claims and retain exact evidence for any restricted label
- Phases: Start work in P10. Accept this cell in P13.
- Must pass first: D07.c9, D07.c6, D08.c1, D27.c8.
- Baseline: Use the baseline stated in the rule when a comparison applies.
- Summary: Test distributed simulation feasibility before benefit claims and retain exact evidence for any restricted label.
- Rule:
  1. Decide distributed simulation method DS27 feasibility before distributed benefit.
  2. Use the sealed one-six-wide-core four-state and UVM cut on disjoint controls.
  3. At 1, 2, 4 and 8 hosts, measure cut events per cycle and message bytes.
  4. Measure independent-cone work and minimum lookahead.
  5. Measure synchronization and rollback costs.
  6. Use a pessimistic execution-time prediction from measured compute, cut traffic and serial latency.
  7. Require that prediction to permit at least 3 times speedup at eight hosts with at least 20% slack.
  8. Separately derive an optimistic execution-time lower bound.
  9. Only an upper speedup bound below 3 times can certify infeasibility.
  10. Label unresolved bounds FEASIBILITY-UNRESOLVED, never infeasible.
  11. Seal equations, bounds and cut.
  12. For an infeasible conservative cut, redirect to coarser temporal batching or optimistic PDES with exact rollback and foreign-state logs.
  13. After two failures, publish SINGLE-DESIGN-SCALING-INFEASIBLE only with the proved optimistic bound.
  14. Otherwise publish FEASIBILITY-UNRESOLVED.
  15. Keep single-core scaling at least 3 times OPEN.
  16. Continue distributed capability on independently partitionable designs and independent-job scale.
  17. Reclassification after outcomes cannot rescue any failed child.

<a id="D08c4"></a>

#### D08.c4: Qualify hybrid functional fast-forward and RTL windows using exact transfers, full anchors and total checked throughput
- Phases: Start work in P12. Accept this cell in P13.
- Must pass first: D08.c3, D08.c1, D01.c2, D27.c8.
- Baseline: Use full RTL anchors and full RTL execution, plus VCS and Xcelium for original cost comparisons.
- Summary: Test hybrid functional fast-forward and RTL windows using exact transfers, full anchors and total checked throughput. Require timing error at most 2 percent per class.
- Rule:
  1. Implement hybrid functional fast-forward and checked RTL windows.
  2. Use the micro-operation model method M27 functional lane and issue #347 complete checkpoint-transfer interface.
  3. Transfer architectural, memory, device, coherence, scheduler and random state into RTL windows only after independent state-equivalence validation.
  4. Use at least 100 transfer boundaries per state family.
  5. Include pending interrupts, races, faults, lock handoff and stale hidden state.
  6. Require exact state and suffix agreement on every control.
  7. Require full-anchor output and ordering checks.
  8. Use full RTL anchors to qualify window selection and error under D08.c3.
  9. Across every long-job class, require adjusted total checked throughput gain at least 3 against full RTL.
  10. Include fast-forward, transfer, warmup and rejected windows.
  11. Require timing error at most 2 percent per class.
  12. Compare total checked job cost with VCS and Xcelium using original noninferiority gates.
  13. Report sampled execution separately from continuous RTL rate.
  14. Keep hybrid acceleration OPEN after failure even if distributed scaling is infeasible.

<a id="D11c4"></a>

#### D11.c4: Qualify vector and hypervisor reference performance at manycore scale
- Phases: Start work in P12. Accept this cell in P13.
- Must pass first: D11.c2, D12.c3, D35.c2a, D07.c2, D27.c8.
- Baseline: Unchecked execution on the reference host and effective D07.c2 retirement demand.
- Summary: Test the qualification of vector and hypervisor reference performance at manycore scale. Require a rate at least the maximum of effective D07.c2 retirement demand and 1 billion divided by demand deadline seconds.
- Rule:
  1. Create vector and hypervisor reference-performance children at manycore8 and manycore16.
  2. EACH child must activate per-hart vector partial faults and guest state concurrently with coherence and device traffic.
  3. Check at least 1 billion retirements per child.
  4. Require a rate at least the maximum of effective D07.c2 retirement demand and 1 billion divided by demand deadline seconds.
  5. Require a checked-to-unchecked time ratio at most 2.0 on the reference host.
  6. Require a resident-memory ratio at most 1.5 on that host.
  7. Detect all at least 100 activated erased vector and hypervisor differences per child.
  8. Allow no sampling exemption.
  9. Include full transport and graph-check costs.
  10. Use a fallback deadline of 48 h per 1 billion retirements, independent of census demand.
  11. Higher demand must only raise the rate floor.

<a id="D11c6"></a>

#### D11.c6: Compare reference services with both vendor products
- Phases: Start work in P13. Accept this cell in P14.
- Must pass first: D11.c4, D12.c3, D27.c8.
- Baseline: Qualified ImperasDV and Siemens Questa Verification IP for RISC-V.
- Summary: Test adjusted end-to-end checked-rate lower ratio at least 1.10 against both ImperasDV and Siemens Questa Verification IP for RISC-V in every scalar, floating-point, vector, hypervisor and concurrent-state stratum.
- Rule:
  1. Require reference-service comparison against qualified ImperasDV AND Siemens Questa Verification IP for RISC-V in every relevant vendor and candidate scalar, floating-point, vector, hypervisor and concurrent child.
  2. Apply section 3.1 statistical comparisons to all endpoints.
  3. Use a completion margin of .005.
  4. Use a checked-rate reciprocal margin of 1.05.
  5. Use a memory ratio margin of 1.02.
  6. Use an adapter-effort ratio margin of 1.15.
  7. Use an upgrade-effort ratio margin of 1.15.
  8. Use a scripted checked-time ratio margin of 1.15.
  9. Use a first-divergence-time ratio margin of 1.02.
  10. Require exact independent complete-state and erased-difference controls.
  11. Report intersection numerators and denominators and every unsupported vector and hypervisor and concurrency child.
  12. Require that vendor output is never sole truth.
  13. Pin product release, patch, RVVI and API options, manuals and executable hashes before pilots for ImperasDV and Siemens Questa Verification IP for RISC-V.
  14. Choose the strongest qualified supported release under the matched-comparison protocol R08.
  15. Keep all non-inferiority, erased-difference and independent-lineage gates.
  16. Require that integration and upgrade effort remain separate non-inferior endpoints, not rescue routes.
  17. Category 6 primary: Require adjusted end-to-end checked-rate lower ratio at least 1.10 against both ImperasDV and Siemens Questa Verification IP for RISC-V in every scalar, floating-point, vector, hypervisor and concurrent-state stratum.

<a id="D11c7"></a>

#### D11.c7: Improve upstream references and compare extension authoring
- Phases: Start work in P13. Accept this cell in P14.
- Must pass first: D11.c4, D27.c8.
- Baseline: Pinned upstream Spike and Sail; ImperasDV custom-extension flow for the separate authoring child.
- Summary: Test upstream reference speed improvements and the correctness and cost of custom-extension authoring. Require the secondary checked-rate lower bound to be at least 1.10 versus pinned upstream on every scalar, floating-point, vector, hypervisor and concurrency stratum.
- Rule:
  1. Profile decode, state comparison, transport and graph costs for upstream Spike and Sail.
  2. Require the secondary checked-rate lower bound to be at least 1.10 versus each pinned upstream reference on every scalar, floating-point, vector, hypervisor and concurrency stratum.
  3. Implement the reviewed series.
  4. Produce a patch series that can be applied to the pinned upstream versions.
  5. Require a noninferiority resident-memory ratio at most 1.02.
  6. Require a noninferiority upgrade-effort ratio at most 1.15.
  7. Keep exact complete-state and erased-difference controls unchanged.
  8. The fork fallback must follow engine maintenance rules, not reduced semantics.
  9. Create a separate custom-extension authoring child.
  10. Use at least 30 instruction families independently specified under R04, the independence protocol.
  11. Include traps, state and privilege effects.
  12. Extend both Sail and Spike from blank semantics through two specification changes.
  13. Require exact independent truth vectors.
  14. Test at least 100 mutants per family.
  15. Require zero unsound agreements.
  16. Compare against the ImperasDV custom-extension flow under section 3.1.
  17. Require a construction-hour ratio at most 1.15.
  18. Require a maintenance-hour ratio at most 1.15.
  19. Require a checked-runtime ratio at most 1.02.
  20. Use a sampled-completion noninferiority margin of .005.
  21. Extend for joint power.

<a id="D11c9"></a>

#### D11.c9: Audit oracle ancestry and shared-source errors
- Phases: Start work in P13. Accept this cell in P13.
- Must pass first: D11.c8, D09.c3, D27.c8.
- Baseline: Use the baseline stated in the rule when a comparison applies.
- Summary: Audit oracle ancestry and shared-source errors. Detect every seeded shared-source error. Keep unresolved disputes OPEN.
- Rule:
  1. For each ISA stratum publish the ancestry graph of simulation references, formal ISA checks, generators and expected outputs.
  2. Record shared Sail sources even when backends differ.
  3. Where only two oracle families exist and they share ancestry, require an independently written third check before qualification.
  4. Test at least 20 seeded shared-source errors per family.
  5. Detect every error.
  6. Retain disputes as OPEN.
  7. Require that backend diversity alone is not source independence.

<a id="D20c3"></a>

#### D20.c3: Qualify finite renewal and unseen-family claims separately
- Phases: Start work in P13. Accept this cell in P13.
- Must pass first: D20.c1, D20.c2a, D20.c2b, D21.c2; SPEC plug-in, D27.c8.
- Baseline: Use the baseline stated in the rule when a comparison applies.
- Summary: Test the qualification of finite renewal and unseen-family claims separately. Keep the 225 and 899 stages as intake minima, not automatic precision receipts, even though they exceed those counts.
- Rule:
  1. Qualify the two claims separately.
  2. For FINITE-REQUALIFIED, rerun the exact frozen complete frame and full inputs at each release.
  3. Retain expected outputs, consultation history, failed builds and all changes.
  4. Require that repeated consulted families are allowed here.
  5. This receipt closes only the finite count and method counterpart under D20.c2b and 3.4.
  6. For UNSEEN-FAMILY, require fresh disjoint genealogy clusters outside all consulted families, at least 2 full inputs per family and full anchors from D21.c2.
  7. Require that new input in an old family is not fresh.
  8. Calculate the precision sample size as n = ceil((z * s / (effect_min / 2 - bias))^2).
  9. Use this calculation only when bias < effect_min / 2.
  10. Here, effect_min is the smallest preregistered useful effect.
  11. Here, s is the family log standard deviation.
  12. Here, z is the applicable normal quantile.
  13. Separately meet joint power and actual multiplicity budget.
  14. At family log standard deviation .03, unadjusted two-sided 95% half-width .004 and .002 requires 217 and 865 families, respectively.
  15. Keep the 225 and 899 stages as intake minima, not automatic precision receipts, even though they exceed those counts.
  16. For seven-class simultaneous two-sided descriptive intervals, use normal quantile 2.690109.
  17. At zero bias, effects .01 and .005 require 261 and 1043 families, respectively.
  18. Use the actual local alpha for scientific acceptance.
  19. Use the maximum of the precision and power counts unless the complete finite census route applies.
  20. Pool only after exchangeability, held-out interaction and leave-class-out checks.
  21. Publish unpooled failures.
  22. Require that three-release control on a deliberately closed small universe must yield exact finite renewals without fabricated unseen-family claims.
  23. The complete-census route in 3.4 closes the finite claim even below the population intake ambition.

<a id="D20c6"></a>

#### D20.c6: Qualify the SPEC plug-in and complete comparison method
- Phases: Start work in P13. Accept this cell in P13.
- Must pass first: D20.c1, D21.c2, D36.c4, D27.c8.
- Baseline: Full anchors and the comparator runs described by D36.c4 as explanatory context only.
- Summary: Qualify the required SPEC plug-in and its complete comparison method. Check every interface. Execute all CPU2017 integer and floating-point speed and rate workloads when complete inputs are supplied. Use two compilers, full inputs and exact outputs.
- Rule:
  1. The SPEC plug-in is required.
  2. Implement build, ROI, SimPoint, full-input and output validation and comparator runs through D36.c4 as explanatory context only.
  3. Never drop the plug-in.
  4. Report no SPEC-derived score from open proxies.
  5. Require independent synthetic adapter conformance tests for every interface.
  6. Implement a separate SPEC-QUALIFIED child for all CPU2017 integer and floating-point speed and rate workloads.
  7. Execute the child when the complete suite inputs are supplied.
  8. If those inputs are unavailable, record NOT RUN and make no SPEC-qualified claim.
  9. This status must not block open-suite Full.
  10. Use two compilers, full inputs and sampling versus full anchors.
  11. Retain D21.c2 accuracy gates and exact outputs.
  12. Reject partial-input, missing-workload and simulated-result controls.

<a id="D20c7"></a>

#### D20.c7: Calibrate open-suite comparisons and conditional SPEC proxies
- Phases: Start work in P13. Accept this cell in P13.
- Must pass first: D20.c2a, D21.c2, D36.c4, D27.c8. D22.c2 runtime receipt.
- Baseline: Qualified measured useful work on the sealed systems. Use exact SPEC ground-truth measurements for any SPEC proxy label.
- Summary: Test open-suite calibration and the conditions for a SPEC proxy label. Require held-out normalized performance-error median at most 5%.
- Rule:
  1. For open-suite comparator calibration, freeze publicly redistributable suites and natural-family census for all seven classes.
  2. Include published SPEC-correlated suites such as Embench and MiBench only where a pinned primary study actually supports that claim.
  3. Archive study data, CPU and ISA and compiler versions, correlation uncertainty and applicability.
  4. Otherwise, mark correlation as not established.
  5. Use at least 10 independently selected systems across at least 3 microarchitecture lineages including exact Zen 5 and M-series identities, two compiler versions, held-out leave-system AND leave-family calibration.
  6. Independently measure complete useful work and outputs under D36.c4 as explanatory context only.
  7. For a SPEC proxy label, require an adjusted rank-correlation lower bound at least .90.
  8. Require held-out normalized performance-error median at most 5%.
  9. Require its 95th percentile at most 10%.
  10. Expand for power.
  11. Issue separate class receipts.
  12. Use direct open-suite ratios with frozen inputs, equal-class weights and the original section 2 bounds as the primary supported comparison until D22.c2 qualifies natural deployment weights.
  13. They do not imply SPEC performance or deployment generality.
  14. Report compiler, OS, memory, tuning and missing-class sensitivity.
  15. Never infer SPEC scores from correlation alone.
  16. Keep SPEC-proxy OPEN for failed transport, absent ground-truth measurements or an unsupported class.

<a id="D20c9"></a>

#### D20.c9: Qualify proxy architecture-response transfer
- Phases: Start work in P13. Accept this cell in P14.
- Must pass first: D20.c8, D20.c7, D21.c2, D27.c8.
- Baseline: Lawful original workload measurements and independent RTL timing or qualified measured-cycle anchors.
- Summary: Test the qualification of proxy architecture-response transfer. Require zero wrong direction on mandatory controls.
- Rule:
  1. Qualify proprietary-proxy architecture-response transfer.
  2. Seal lawful original and proxy pairs, source systems and held-out predictor, issue, cache and memory changes, including interacting changes.
  3. Measure both members on each configuration with independent RTL timing or qualified measured-cycle anchors.
  4. Require zero wrong direction on mandatory controls.
  5. Require the adjusted upper confidence bound on mean absolute proxy-minus-original performance-delta error at most effect_min divided by 4 for each mechanism and interaction class.
  6. Include at least 20 equal-calibration-summary pairs with different intervention responses as negative controls.
  7. Reject all unfaithful proxies.
  8. Require leave-system confirmation.
  9. Require leave-family confirmation.
  10. Use at least 10 systems across three lineages.
  11. Expand each class for power under R07, the statistical protocol.
  12. Export a typed response-transfer receipt with system and configuration range, missing behavior mass, lawful source identity and all uncertainty.
  13. Require that source-only fidelity contributes zero qualified proprietary-workload weight to cross-system headlines.
  14. Without lawful original measurement, retain behavior-space stress use only.
  15. In that case, leave proprietary response transfer OPEN.
  16. Architecture and design-loop consumers must reject advice outside the qualified range, including at least 20 controls per consumer.
  17. Require that direct open-suite claims stay available.
  18. Express both performance deltas in the same normalized performance units.
  19. Require absolute error at most effect_min divided by 4 on every finite mandatory control.
  20. Reject at least 20 equal-size positive and negative error pairs, including same-direction underprediction.

<a id="D20c10"></a>

#### D20.c10: Qualify sampled corpus anchors
- Phases: Start work in P13. Accept this cell in P13.
- Must pass first: D20.c2b, D08.c3, D27.c8.
- Baseline: Use the baseline stated in the rule when a comparison applies.
- Summary: Test the qualification of sampled corpus anchors. At least 20 qualified sampled controls must pass with exact outputs, order and trace ends.
- Rule:
  1. Consume D20.c2b and D08.c3 for the exact hart size, workload class and synchronization identity.
  2. Apply every original corpus family, input, calibration, genealogy, bias, precision and full-anchor bound.
  3. A valid corpus with unsampled anchors passes only its unsampled route.
  4. Substituting unqualified sampled anchors must fail.
  5. At least 20 qualified sampled controls must pass with exact outputs, order and trace ends.
  6. At least 20 wrong-size, class, synchronization or generation controls must fail.

<a id="D20c11"></a>

#### D20.c11: Check SPEC response transfer
- Phases: Start work in P15. Accept this cell in P15.
- Must pass first: D20.c9, D20.c6, D27.c8.
- Baseline: The exact SPEC CPU suite and inputs supplied for calibration.
- Summary: Check SPEC response transfer against the exact supplied suite. Test at least 20 valid interventions and 20 missing-input or out-of-range controls. Record NOT RUN when the required suite or inputs are unavailable.
- Rule:
  1. Measure D20.c9 intervention-response transfer against that exact SPEC CPU suite.
  2. Apply every original response, rank, direction, uncertainty and bias bound.
  3. Publish both passing and failing calibration with scope.
  4. If the exact suite or required inputs are unavailable, mark the calibration child NOT RUN and make no SPEC calibration claim.
  5. Always export an applicability and status receipt.
  6. A passing calibration receipt is required only for a SPEC calibration claim.
  7. Require that open-suite capability remains required.
  8. Pin suite version, inputs and proxy family ancestry.
  9. Test at least 20 valid interventions and 20 missing-input or out-of-range controls.

<a id="D20c12"></a>

#### D20.c12: Qualify OS and server workload traces
- Phases: Start work in P12. Accept this cell in P13.
- Must pass first: D20.c8, D21.c2, D27.c8.
- Baseline: Use independent complete execution and measured lawful source traces.
- Summary: Test multiprocess OS, server and JIT trace fidelity. Require cycle-error upper bound at most 5% per class against complete anchors.
- Rule:
  1. Use at least 30 independent families each for multiprocess OS work, server requests and JIT execution.
  2. Capture process and thread identity, context switches, kernel transitions, code-generation epochs and synchronization.
  3. Include cold start, steady state, tail requests, code invalidation and mixed tenants.
  4. Require exact completed useful work and output agreement on mandatory controls.
  5. Require trace loss at most .1% with conservative loss propagation.
  6. Require cycle-error upper bound at most 5% per class against complete anchors.
  7. Reject all stale JIT and cross-process identity controls.
  8. Expand independent family counts under the sealed workload power ledger.

<a id="D24c9"></a>

#### D24.c9: Measure checked farm throughput on one large design
- Phases: Start work in P12. Accept this cell in P13.
- Must pass first: D23.c3 runtime receipt; D24.c3, D07.c2, D27.c8. D07.c7 as explanatory context only; it supplies no acceptance evidence.
- Baseline: Use independently qualified vManager, IMC and Verdi Planner regression-management recipes on the identical design and requirement frame. Keep VCS and Xcelium farm throughput as a separate simulation measure.
- Summary: Test checked regression-management closure throughput against vManager, IMC and Verdi Planner. Retain the separate simulator-farm throughput check.
- Rule:
  1. Use one unchanged six-wide coherent design with at least 400 ROB entries.
  2. Run at least 1000 independent seeds and checkpoint continuations on each farm.
  3. Measure completed independently checked useful jobs per elapsed hour at 16, 64 and 256 allocated cores.
  4. Include build, reference, transport, failed work and artifact costs.
  5. Require zero missing observations or falsely accepted jobs.
  6. Keep the D07.c7 distributed single-job gate OPEN if it fails.
  7. A farm receipt cannot close a distributed single-job claim.
  8. Require adjusted checked useful-job throughput lower ratio at least 1.10 against both VCS and Xcelium farms at each allocation as a secondary simulation measure.
  9. Category 12 primary: Require an adjusted checked closure-task throughput lower ratio of at least 1.10 against each vManager, IMC and Verdi Planner at each allocation.
  10. A closure task includes scheduling and recovery, test-plan revision links, coverage merge and reconciliation, failure classification, waiver expiry and a checked closure answer. Use the existing D23.c3 requirement graphs and the same 1000 seeds and checkpoint continuations.
  11. Count only tasks with exact independent expected answers and zero wrong closures. Include management setup, ingestion, failed updates, retries, checks and recovery in total allocated core-hours.
  12. Use identical sealed simulation-result streams for each management recipe. This isolates management benefit from simulator speed. Compare each named product on all management operations in its qualified feature frame. Keep unsupported operations OPEN.

<a id="D35c4"></a>

#### D35.c4: Audit archived and prospective decision portfolios
- Phases: Start work in P13. Accept this cell in P13.
- Must pass first: D35.c3, D36.c1, D27.c8.
- Baseline: Use the strongest full-RTL decision recipe and the independent exhaustive or checked portfolio oracle.
- Summary: Test portfolio regret and retained decisions across archived, generated-wide and independently selected natural lineages. Require at least TWO natural lineages and prospectively sealed portfolios.
- Rule:
  1. Audit three-generation portfolios on existing archived variants, including negative and no-gain choices.
  2. Seal alternatives and independent full-RTL utility for all decisions.
  3. Keep interactions and rejected alternatives.
  4. Compute cumulative regret at each generation as oracle feasible portfolio utility minus selected portfolio utility.
  5. Fix class weights and the constraint set.
  6. Use an independent exhaustive or checked optimizer for the oracle.
  7. Require upper normalized regret at most .05 of the feasible improvement envelope.
  8. Require regret non-inferiority versus the strongest full-RTL decision recipe.
  9. For a zero envelope, require exact zero harmful selection.
  10. Attribute every accepted and rejected step by ablation.
  11. Require no faster-core outcome.
  12. Also run a prospective sealed generated-wide portfolio in both wide strata through three structural generations.
  13. Freeze its alternatives before prediction.
  14. Use independent full RTL for all utilities and the oracle.
  15. Apply the same regret and zero-harm gates.
  16. Archive results cannot replace this receipt.
  17. Also run one prospective sealed natural-target portfolio at any width through three generations.
  18. Seal all alternatives before prediction.
  19. Execute independent full-RTL utilities.
  20. Apply the identical at most .05 normalized regret, non-inferiority and zero-envelope gates.
  21. Archive and generated portfolios cannot substitute.
  22. Require at least TWO natural lineages and prospectively sealed portfolios.
  23. Apply every original retained-winner, regret, decision-cost and maintenance gate separately.
  24. Label one passing natural lineage SINGLE-LINEAGE.
  25. One passing natural lineage cannot close this cell.
  26. Include Rocket, CVA6, XiangShan, NaxRiscv and BOOM lineages.
  27. Freeze provenance, structural ancestry and eligibility before predictions.
  28. Select TWO independent natural lineages by the presealed eligibility order, not achieved regret.
  29. Commission independent future variants on those existing lineages with held-out RTL utilities.
  30. Archive-only, generated or sibling forks cannot supply two natural lineages.
  31. If the census finds fewer than two, publish UNAVAILABLE-FRAME.
  32. Under that condition, keep the natural child OPEN.
  33. Use this machine portfolio receipt to verify utilities, regret and complete effort logs.
  34. Require two independent natural lineages with separately sealed prospective portfolios and all original gates.

<a id="D35c5"></a>

#### D35.c5: Check security-qualified decision revocation
- Phases: Start work in P15. Accept this cell in P15.
- Must pass first: D38.c5, D38.c6, D35.c3, D36.c2, D27.c8.
- Baseline: Use the baseline stated in the rule when a comparison applies.
- Summary: Test both compiler consumer receipts and transitive security-contract revocation through decisions. For 20 stale or violated-contract cases, independently check transitive revocation of model, binary, campaign and decision.
- Rule:
  1. Require both compiler consumer receipts for security-qualified decision outputs.
  2. For 20 stale or violated-contract cases, independently check transitive revocation of model, binary, campaign and decision.
  3. Keep ordinary functional decisions explicitly not security-qualified.
  4. Reuse one shared receipt without extra statistical chance.

<a id="D35c9"></a>

#### D35.c9: Qualify proxy decision recommendations
- Phases: Start work in P15. Accept this cell in P15.
- Must pass first: D35.c3, D20.c9, D27.c8.
- Baseline: Use the baseline stated in the rule when a comparison applies.
- Summary: Test exact response transfer and refusal controls before proxy recommendations can pass decision-screening gates. Require at least 20 positive in-range decisions to agree with independent RTL anchors.
- Rule:
  1. Apply every D35.c3 machine-correctness, retained-winner, resolution, uncertainty, compiler, generation, wide-geometry and cost-log bound to proxy recommendations.
  2. Require the exact D20.c9 response-transfer receipt.
  3. Require at least 20 positive in-range decisions to agree with independent RTL anchors.
  4. Require at least 20 missing or out-of-range receipts to refuse recommendations.
  5. A matched calibration summary cannot authorize transport.
  6. Close proxy machine-cost superiority only when the adjusted upper allocated-core-hour cost ratio is at most 0.90 against every D35.c3 comparator.
  7. Human productivity remains an owner task.

<a id="D36c2"></a>

#### D36.c2: Audit end-to-end performance decisions
- Phases: Start work in P14. Accept this cell in P14.
- Must pass first: D36.c1, D35.c3, D20.c3, D22.c2, D27.c8.
- Baseline: Use the baseline stated in the rule when a comparison applies.
- Summary: Test full decision traceability and seeded performance regressions through three generations using the single D35.c3 comparison receipt. Run hidden prediction, independent RTL, correctness and security checks, genealogy and bias checks, then reporting through three generations.
- Rule:
  1. Use fresh full-anchor audits each generation.
  2. Detect all seeded sign reversals and class regressions more than .5%.
  3. Use direct baseline-to-current ratios, not added gains.
  4. Run hidden prediction, independent RTL, correctness and security checks, genealogy and bias checks, then reporting through three generations.
  5. Reopen invalidated retained results.
  6. Use D35.c3's single comparison receipt for measured resolution quality and mandatory prospective benefit under section 3.1.
  7. Do not create a second hypothesis.
  8. Independently audit traceability without missing ancestors.
  9. Treat a supported negative performance finding as success.
  10. Require no faster-core outcome.

<a id="D38c3"></a>

#### D38.c3: Qualify compiled-code quality and model accuracy
- Phases: Start work in P14. Accept this cell in P14.
- Must pass first: D38.c2, D38.c5, D38.c6, D20.c3, D21.c2; upgrades invalidate affected model receipts, D20.c1, D27.c8, D38.c8, D38.c9.
- Baseline: Use independently specified LLVM and GCC models with the same compilers and flags and equal tuning.
- Summary: Test compiled-code quality and model accuracy against independent LLVM and GCC models. Require the construction and maintenance scripted checked-time upper ratio at most 0.90. Preserve exact outputs and the code-cycle, code-size and spill bounds.
- Rule:
  1. Use all output-checked D20.c3 families, two LLVM and GCC versions, and three description and RTL generations.
  2. Require exact absence of mandatory code-generation or ISA errors.
  3. Measure compiled-code quality per class and accuracy against independently specified models at equal tuning effort under section 3.1.
  4. Measure compiler-model construction and maintenance with scripted runs.
  5. Preserve required upper construction and maintenance scripted checked-time ratio at most .90 in the machine receipt.
  6. Require RTL-measured compiled-code cycles to be non-inferior with upper workstation-to-baseline ratio at most 1.01 per D20.c3 class.
  7. Use a maximum 1% runtime budget, tightened to minimum effect effect_min divided by 4 where smaller.
  8. Require code-size upper ratio at most 1.02.
  9. Require spill-traffic upper ratio at most 1.02.
  10. Require direction and sensitivity non-inferiority margin .005.
  11. At zero spill baseline, require exactly no extra spills.
  12. Use independently specified LLVM and GCC models as the baseline.
  13. Use the same compilers and flags and equal tuning.
  14. Require exact outputs.
  15. Count failed compiles, unsupported models and debug work.
  16. Require no faster-core outcome.
  17. An llvm-mca estimate is never RTL evidence.
  18. Upgrades must invalidate affected model receipts.

<a id="D38c8"></a>

#### D38.c8: Qualify the LLVM RVV vectorizer cost model
- Phases: Start work in P13. Accept this cell in P13.
- Must pass first: D38.c4, D34.c4, D21.c2, D38.c3 (sealed interface schema only; no final runtime or comparison receipt), D27.c8.
- Baseline: Use BOTH unmodified pinned LLVM versions and the strongest qualified hand-tuned vectorizer recipe under R08.
- Summary: Test LLVM vectorizer decisions and costs against full RTL, pinned compiler versions and the strongest qualified tuned recipe. Require correct-winner probability lower bound at least 0.95.
- Rule:
  1. Generate and integrate a LLVM RVV vectorizer cost model from the checked machine description.
  2. Pin two native compiler versions.
  3. Test all three structural generations.
  4. Model vector setup, scalar and vector crossover, gather, scatter, reductions, masking, tails, VLEN and LMUL choices, and memory costs.
  5. Seal at least 30 fresh loops per mechanism and generation.
  6. Expand for power.
  7. Include aliasing, loop-carried dependence, short trips, variable trips and unsupported operations.
  8. Independently specify legality and scalar or vector winner expectations before compilation.
  9. Verify exact outputs and zero unsafe transformations.
  10. Require explicit abstention for unsupported legality or cost ranges.
  11. Measure cycles on independent full RTL anchors for forced scalar, forced vector and automatic decisions.
  12. Require correct-winner probability lower bound at least 0.95.
  13. Require relative regret upper bound at most 0.02 per mechanism.
  14. Compare against BOTH unmodified pinned LLVM versions and the strongest qualified hand-tuned vectorizer recipe under R08.
  15. R08 requires matched work and qualified recipes selected on disjoint controls before confirmation.
  16. Require code-cycle ratio at most 1.02.
  17. Require construction and maintenance effort ratios at most 0.90.
  18. Apply all existing compiled-code quality and effort bounds in the sealed D38.c3 interface.
  19. Require every unsafe-transform, wrong-VLEN and stale-model control to fail.
  20. Report missed profitable vectorization and correct refusal separately.
  21. Scheduling-table correctness cannot close this child.

<a id="D38c9"></a>

#### D38.c9: Qualify the GCC RVV vectorizer cost model
- Phases: Start work in P13. Accept this cell in P13.
- Must pass first: D38.c4, D34.c4, D21.c2, D38.c3 (sealed interface schema only; no final runtime or comparison receipt), D27.c8.
- Baseline: Use BOTH unmodified pinned GCC versions and the strongest qualified hand-tuned vectorizer recipe under R08.
- Summary: Test GCC vectorizer decisions and costs against full RTL, pinned compiler versions and the strongest qualified tuned recipe. Require correct-winner probability lower bound at least 0.95.
- Rule:
  1. Generate and integrate a GCC RVV vectorizer cost model from the checked machine description.
  2. Pin two native compiler versions.
  3. Test all three structural generations.
  4. Model vector setup, scalar and vector crossover, gather, scatter, reductions, masking, tails, VLEN and LMUL choices, and memory costs.
  5. Seal at least 30 fresh loops per mechanism and generation.
  6. Expand for power.
  7. Include aliasing, loop-carried dependence, short trips, variable trips and unsupported operations.
  8. Independently specify legality and scalar or vector winner expectations before compilation.
  9. Verify exact outputs and zero unsafe transformations.
  10. Require explicit abstention for unsupported legality or cost ranges.
  11. Measure cycles on independent full RTL anchors for forced scalar, forced vector and automatic decisions.
  12. Require correct-winner probability lower bound at least 0.95.
  13. Require relative regret upper bound at most 0.02 per mechanism.
  14. Compare against BOTH unmodified pinned GCC versions and the strongest qualified hand-tuned vectorizer recipe under R08.
  15. R08 requires matched work and qualified recipes selected on disjoint controls before confirmation.
  16. Require code-cycle ratio at most 1.02.
  17. Require construction and maintenance effort ratios at most 0.90.
  18. Apply all existing compiled-code quality and effort bounds in the sealed D38.c3 interface.
  19. Require every unsafe-transform, wrong-VLEN and stale-model control to fail.
  20. Report missed profitable vectorization and correct refusal separately.
  21. Scheduling-table correctness cannot close this child.

## M7: Audit the full release

Acceptance phases: P16–P18.

<a id="D27c3"></a>

#### D27.c3: Check release comparison labels
- Phases: Start work in P17. Accept this cell in P18.
- Must pass first: D27.c2, D28.c3; these downstream audits are not bootstrap inputs, D27.c6, D35.c5, D38.c3, D36.c2, D27.c7, D27.c8, D28.c6, D01.c12, D20.c9, D08.c3, D08.c4, D34.c7, D35.c8, D06.c12, D07.c7, D02.c4, D35.c9, D20.c10, D01.c14, D01.c15, D06.c13, D07.c15, D09.c3, D11.c9, D15.c12, D17.c15, D20.c11 applicability and status receipt only; a passing SPEC response receipt is required only for a SPEC calibration claim; D25.c10, D30.c8, D32.c8, D33.c9, D38.c8, D38.c9.
- Baseline: Use the whole relevant pinned vendor inventory from the commercial feature inventory for each comparison label.
- Summary: Test complete feature and evidence frames, error budgets and independent label decisions before publication. Reject 20 controls per missing or wrongly typed release receipt, including conditional SPEC status and duplicate category credit.
- Rule:
  1. For each comparison label, print the whole relevant vendor inventory denominator from the commercial feature inventory.
  2. Print covered count, reasoned exclusions and target versions.
  3. Require every relevant feature for whole-scope parity or superiority, not only common intersections.
  4. Keep feature-local comparisons labeled partial until the inventory conjunction closes.
  5. In the machine-readable release manifest, name each comparison claim, alpha allocation, support frame and upstream version.
  6. Include raw evidence, unmet inference and mandatory failure.
  7. Independently recompute every acceptance value.
  8. Test 20 internally consistent shared-omission artifacts.
  9. Agreement of two evaluators cannot pass without requirement audit.
  10. Use weekly wrong canaries to quarantine descendants.
  11. Have 10 unfamiliar agents find all task obligations in at most 5 min per task.
  12. Compute the typed trust vector from section 3.4.
  13. Publish the complete claim, endpoint, attempt and look alpha ledger.
  14. Include the per-release 0.04 scientific plus 0.01 validation category union bound.
  15. Explain intersection-union test, gatekeeping and Holm roles.
  16. Reject reports that call this a probability of tool correctness.
  17. Reject 100 cases covering missing ancestors, overallocated error budgets, selective reruns and unqualified substitute promotion.
  18. Include stale census renewal and missing component status in those cases.
  19. Test every intermediate tier in section 5.
  20. A narrower tier must never change an open final gate to passed.
  21. Apply RL24, the release-label-vector protocol, to every tier and export.
  22. Reject machine-population claims that replace a required powered machine test with a finite census receipt.
  23. Reject generated-only natural-target Full claims and missing route shares.
  24. Reject NONINFERIOR converted to exact equality.
  25. Test at least 20 controls of each type.
  26. Evaluate ROUTE25, the preallocated alternative-qualification-routes protocol, before any tier label.
  27. Require explicit natural cells for natural Full, not context links.
  28. Reject at least 20 complete-looking releases missing each natural, scaled or powered receipt.
  29. Keep adoption counts separate from capability and readiness category labels.
  30. Require D01.c12 for Category 1 Full.
  31. Require D20.c9 for final architecture and workload proxy claims.
  32. Require D08.c3 for sampled multithreaded claims.
  33. Require D08.c4 as a separate labeled route for final simulation acceleration.
  34. That route must not replace continuous RTL or D07.c7.
  35. Require D34.c7 for final quantitative security labels.
  36. Require D35.c8 for final agent design-loop claims.
  37. Require a second independently authored label-logic evaluator.
  38. Use a separate implementation language, parser and decision code.
  39. Share only the normative prose contract and independently specified test vectors.
  40. Require exact agreement on all accepted, refused, stale, revoked, missing and wrong-frame label decisions.
  41. Cover the complete finite schema-state inventory and held-out mutations.
  42. Any disagreement must block publication.
  43. Agreement is necessary and cannot establish semantic truth.
  44. Do not use these downstream audits as bootstrap inputs.
  45. Always check the D20.c11 applicability and status receipt.
  46. Reject 20 cases that use one receipt as evidence for two category labels without separate requirement witnesses and separately evaluated endpoints.
  47. Permit shared raw artifacts only when each category has its own checked predicate and receipt identity.
  48. Reject 20 SPEC calibration claims with failed response-transfer calibration.

<a id="D27c5"></a>

#### D27.c5: Check complete vendor feature implementation
- Phases: Start work in P09. Accept this cell in P16.
- Must pass first: D27.c2, D27.c4, D31.c1, D29.c2; owning-cell schema interfaces sealed independently under R04 (independent requirement-derived expectations and separate producer and checker implementation ancestry), D27.c8, D27.c9, D31.c4, D01.c2, D01.c3b, D01.c8, D02.c1, D05.c1, D05.c5, D06.c1, D06.c10, D06.c2, D07.c1, D07.c3, D07.c8, D08.c1, D09.c2, D10.c1p1, D10.c1p10, D10.c1p11, D10.c1p12, D10.c1p13, D10.c1p14, D10.c1p15, D10.c1p16, D10.c1p17, D10.c1p18, D10.c1p19, D10.c1p2, D10.c1p20, D10.c1p3, D10.c1p4, D10.c1p5, D10.c1p6, D10.c1p7, D10.c1p8, D10.c1p9, D10.c90, D11.c5, D11.c6, D11.c7, D12.c1, D13.c2, D14.c2, D14.c3, D14.c5, D14.c6, D14.c7, D15.c10, D15.c2p1, D15.c2p10, D15.c2p2, D15.c2p3, D15.c2p4, D15.c2p7, D15.c2p8, D15.c2p9, D15.c3, D15.c4, D15.c5, D15.c6, D15.c8, D15.c9, D16.c3, D16.c4, D17.c3, D18.c1, D18.c10, D18.c2, D18.c3, D18.c4, D18.c5, D18.c8, D18.c9, D19.c1, D19.c4, D21.c1, D23.c1, D23.c2, D23.c3, D24.c1, D24.c2, D24.c5, D24.c6, D24.c7, D25.c5, D25.c7, D26.c2, D28.c1, D28.c4, D29.c10, D29.c5, D30.c7, D31.c1, D31.c2, D31.c3, D31.c4, D31.c5, D31.c6, D33.c1, D33.c2, D33.c3, D34.c2, D34.c3, D34.c4, D35.c3, D36.c3, D37.c1, D37.c2, D37.c3, D37.c7, D37.c90.
- Baseline: Use qualified independent vendors on identical complete feature tasks.
- Summary: Test every relevant vendor feature, its exact behavior, comparisons and pre-outcome relevance record. Require zero false accepts.
- Rule:
  1. Make every nonexcluded feature in commercial-features.md a mandatory child.
  2. Expand all relevant manual and standard subclauses before implementation.
  3. Extend the mapped open engine, app or interface to cover the complete feature.
  4. Include vendor-only capabilities absent from current intersections.
  5. Use at least 50 independently specified positive and at least 50 invalid or boundary controls per semantic family.
  6. Require exact mandatory outputs, state, bins, proof, debug and status.
  7. Require zero false accepts.
  8. Run identical complete tasks on qualified independent vendors.
  9. For every feature, require section 3.1 checked-time, cost and resident-memory ratios at most 1.02.
  10. Require capacity ratio at least 1 divided by 1.05.
  11. Require sampled completion and sensitivity difference at least -.005.
  12. Require scripted checked time ratio at most 1.15 where applicable.
  13. Require tail ratios at most 1.20 where applicable.
  14. Justify margins from task budgets.
  15. Require reasons and an independent checker result before data for genuine metric nonapplicability.
  16. Retain existing stricter owning-cell bounds.
  17. Keep missing features OPEN.
  18. Do not exclude missing features because of effort or engine limits.
  19. Before outcomes, use two independent enumerator implementations to check the V26 relevance record for every feature and subclause.
  20. Freeze CPU-REQUIRED and CPU-LOW-RELEVANCE tiers with task witnesses.
  21. Reject at least 20 post-result reclassification, unreviewed-exclusion and missing-low-relevance-status controls with zero false accepts.
  22. Consume every actual mapped final implementation, proof, natural-transfer and required all-comparator receipt.
  23. Early schemas must never substitute.
  24. Reject complete schemas with OPEN D31.c4.
  25. Reject a CPU-LOW-RELEVANCE coverage statement promoted to whole-product parity.
  26. Use at least 20 controls of each type.
  27. Seal owning-cell schema interfaces independently under R04.

<a id="D27c6"></a>

#### D27.c6: Audit whole-scope comparison claims
- Phases: Start work in P14. Accept this cell in P17.
- Must pass first: D01.c2, D01.c3b, D01.c8, D02.c1, D05.c1, D05.c5, D06.c1, D06.c2, D07.c1, D07.c3, D07.c8, D08.c1, D10.c1, D10.c90, D11.c4, D11.c5, D11.c6, D12.c1, D13.c2, D14.c2, D14.c3, D14.c5, D14.c6, D14.c7, D15.c2p1, D15.c2p10, D15.c2p2, D15.c2p3, D15.c2p4, D15.c2p7, D15.c2p8, D15.c2p9, D15.c3, D15.c4, D15.c5, D15.c6, D15.c8, D15.c9, D17.c3, D18.c1, D18.c2, D18.c3, D18.c5, D18.c6, D19.c1, D19.c4, D23.c1, D23.c2, D23.c3, D24.c1, D24.c2, D24.c5, D25.c5, D25.c7, D26.c2, D27.c5, D28.c1, D28.c3, D28.c4, D29.c10, D29.c5, D31.c3, D33.c1, D33.c2, D33.c3, D34.c2, D34.c3, D34.c4, D35.c3, D36.c3, D37.c1, D37.c3, D37.c6, D37.c7, D37.c90, D15.c10, D18.c8, D18.c9, D24.c6, D24.c7, D31.c4, D31.c5, D31.c6, D27.c8.
- Baseline: Use qualified vendor comparisons over the whole relevant inventory in commercial-features.md.
- Summary: Test complete vendor feature coverage, qualified comparisons and valid exclusions before whole-scope labels. Require 100% feature coverage with no unmatched clause.
- Rule:
  1. Require the mapped implementation receipt and qualified vendor comparison for every relevant feature and subclause in commercial-features.md.
  2. Apply all stricter owning-cell gates.
  3. Give each exclusion an approved owner-scope or CPU-irrelevance reason.
  4. Require 100% feature coverage with no unmatched clause.
  5. Require category conjunctions and fixed benefit primaries.
  6. For non-inferiority-only features, print actual margins.
  7. Use 20 controls each for missing features, vendor-only features, hidden options, invalid exclusions and narrow intersections.
  8. Make each control block whole-scope labels.
  9. Exports cannot replace the denominator with intersections.
  10. Apply WM24 requirement-derived witnesses, RP04 wrong-subject checks and RP08 substitution controls.
  11. Make 20 valid-ID but wrong-subject mutants fail.
  12. Use two independent enumerator implementations to reconcile pinned vendor manuals, options and app lists.

<a id="D27c7"></a>

#### D27.c7: Audit complete inherited protocol enforcement
- Phases: Start work in P16. Accept this cell in P16.
- Must pass first: D27.c4, D28.c3, D16.c6, D17.c11, D17.c12, D33.c7, D01.c11, D27.c8.
- Baseline: Use the baseline stated in the rule when a comparison applies.
- Summary: Test late protocol completeness and all mandatory natural, scaled and powered receipts. Require zero false accepts.
- Rule:
  1. Import and enforce every shared protocol R01–R12 as typed children of each applicable cell.
  2. Cover sections 3.1–3.5.
  3. Apply RL24 release labels, QH24 interaction hosts, SR24 source imports, MX24 semantic mappings and ISA24 extension rules.
  4. Apply ROUTE25 alternative routes, R25 inherited independence and literal phrase expansions.
  5. Reject unowned acceptance predicates outside defining cells or registered inherited protocols.
  6. Use at least 20 removed-clause, hidden-Full-predicate and wrong-context controls per protocol.
  7. Require zero false accepts.
  8. Use this cell for the late completeness audit.
  9. It must not replace early enforcement or any capability test.
  10. Require natural Formal, SMT, coherence and Security receipts and largest-scale transfer before matching Full labels.
  11. Keep every required powered machine test mandatory.
  12. Treat D27.c8 as context for early enforcement, which precedes dependent measurements.
  13. Reject any Alpha or Beta receipt without early-enforcement identity.

<a id="D35c8"></a>

#### D35.c8: Qualify the agent proposal-to-merge campaign
- Phases: Start work in P17. Accept this cell in P17.
- Must pass first: D35.c4, D25.c5, D25.c9, D20.c9, D27.c8, D35.c9, D20.c10, D01.c14.
- Baseline: Use the strongest qualified scripted gem5, performance-monitoring-unit, native simulation and debug chain under equal budgets.
- Summary: Test complete agent decision campaigns against scripted work without authorizing a repository merge. Require effort ratio at most 1.15.
- Rule:
  1. Seal fresh tasks across predictor, issue, cache and memory changes, including interactions.
  2. Use three structural generations and two tool and model upgrades.
  3. Run proposal, model prediction, RTL change, independent verification and merge recommendation as one receipt chain.
  4. This planned test does not authorize a repository merge.
  5. Use at least 30 decision clusters per mechanism as a pilot.
  6. Expand for R07 joint power, which requires preregistered statistics and at least 80% joint power for all applicable gates.
  7. Compare with the strongest qualified scripted gem5, performance-monitoring-unit, native simulation and debug chain under equal budgets.
  8. Require fixed adjusted total verified-decision-cost upper ratio at most .90.
  9. Require correct-decision lower bound at least .90.
  10. Require sampled completion non-inferiority margin .005.
  11. Require effort ratio at most 1.15.
  12. Require 95th-percentile time ratio at most 1.20.
  13. Require zero false accepted changes.
  14. Retain every known winner.
  15. Include rejected proposals, failed checks, repair, help, security review and all tool costs.
  16. Consume final integrated machine tests, fresh contamination controls and permission receipts.
  17. No local model or agent gain can rescue a wrong merge recommendation.
  18. Require an immutable candidate branch with a recorded base and head.
  19. Require every applicable machine check to pass and no unresolved technical review finding.
  20. Require an independently checked clean application to the recorded base.
  21. Invalidate approval when the base or head changes.
  22. Record the merge recommendation without executing a repository merge.
