# Coherence protocol model checking

## Goal and boundary

Check a finite TileLink-C permission model with two agents and one home.
Generate monitors from the checked transition relation. Run the permission
projection on the existing two-hart RTL fixture. This is an abstraction check.
It is not a proof that a TileLink-C cache implements the specification.

The first model has one line, two data values, one request per agent,
and one active home transaction. Each agent can request Branch or Trunk.
The home accepts A requests, sends B probes, consumes C acknowledgments,
sends D grants, and consumes E acknowledgments. A Trunk recipient writes once at E completion. This merges a local write
with GrantAck in the abstraction; E carries no data.
A completed agent can release its copy. Dirty data must reach the home before
it grants a copy to another agent. Whole messages are atomic model steps.
The model omits multibeat transfers, source/sink reuse, errors, channel buffers,
AcquirePerm upgrades, multiple outstanding home transactions and arbitrary
program streams. These limits are inputs to the result, not proof conclusions.

## Prior art and existing code

- [TileLink 1.8.1 specification, sections 8 and 9](https://starfivetech.com/uploads/tilelink_spec_1.8.1.pdf)
  defines N/B/T permissions and A/B/C/D/E message flows. Permission is separate
  from dirty data. The model uses those permissions, not a renamed MESI model.
- [TLC model configuration](https://dl.tlapl.us/tlatoolbox/doc/model/overview-page.html)
  separates the next-state relation from fairness. TLC is a suitable future
  independent oracle. The first backend is a small Python explicit-state checker.
- `RiscvSim/src/main/scala/riscvsim/CoherenceMonitor.scala` checks observed
  grants and shrinks. It does not explore a protocol state space.
- `SpinalChecks/src/main/scala/spinalchecks/ProtocolChecks.scala` checks
  channel legality and transaction identity. Keep those checks.
- `RiscvSim/src/test/scala/riscvsim/AtomicFixture.scala` has N/B/T permission
  outputs and two instruction-driven harts. It has no TileLink-C channels.
  Its shared memory is current even when an agent has Trunk permission.
- Issues #108 and #128 leave racing requests and progress verification open.
  Issue #294 tracks the broader formal engine work.

## Architecture

Place the finite model, graph exploration and monitor generator under
`SpinalChecks/coherence/`. Keep core bindings out of the generic model.
Use immutable states. Explore all enabled transitions with breadth-first search.
Keep predecessor edges for a shortest safety or deadlock witness.
Check SWMR in every state: Trunk excludes every other valid copy.
Check each valid cache value against the last abstract write. Check home data
when no dirty owner exists. Do not compare stale home data to the last write
while an owner holds the current value.

Deadlock means a nonterminal reachable state has no enabled transition.
Check nonterminal graph cycles for livelock. The finite workload has no legal
nonterminal cycles. Thus this first backend can use a stronger cycle-free
progress condition, after removing environment stutter. It assumes each enabled
protocol step is eventually taken. It does not prove arbitration fairness or
progress through infinite request streams. A cycle witness refutes this stronger
condition; later general workloads need fair SCC analysis, not this criterion.
State or work limits must produce inconclusive, never pass.

Seed defects for conflicting grants, stale intervention data, a lost response,
and retry without progress. Require witnesses from the graph search.
Generate legal global permission states and projected transitions from the
unmutated reachable graph. Bind the generated Scala relation to a SpinalChecks
Area with explicit permission inputs. Reuse the same relation in simulation.
The fixture can complete a shrink and grant in one clock. Its adapter uses
finite paths through the relation between sampled states. This loses transient
channel ordering information. Assert that limitation in the monitor interface.
Do not infer cache data checks from the fixture's permission-only binding.

## Interfaces and C1–C9

| Contract | Use |
|---|---|
| C1 | Keep RTL fixture completion separate from the model verdict. No core adapter change. |
| C2 | No RVFI change. Permission events are not retired instructions. |
| C3 | Future suite integration must distinguish model, generated-monitor and RTL results. |
| C4 | No gate acceptance from an abstract model pass. |
| C5 | Store model parameters and a witness in the failure artifact directory. |
| C6 | No database schema change. Bind explicit project signals. |
| C7 | No MCP tool in this slice. |
| C8 | Local inputs and outputs only. No hostile-input claim. |
| C9 | No architecture calibration or performance claim. |

The checker emits a local JSON report with scope, counts, verdict and witness.
Document this local interface before other tools consume it. The generator must
be deterministic. Tests compare generated source with fresh graph output.

## Acceptance tests

- Exhaust the base graph for two agents, one home and both request permissions.
- Catch each seeded defect with the expected invariant or progress failure.
- Exercise writes, dirty intervention, releases and both arbitration orders.
- Reject invalid bounds. Report exhausted budgets as inconclusive.
- Compile the generated SpinalChecks monitor. Run positive and negative RTL tests.
- Run the generated permission projection on AtomicFixture. Detect its conflicting
  ownership fault. State that this does not exercise TileLink-C channel RTL.
- Keep all prior channel checks. Use targeted tests and machine locks.

## Risks and phased plan

1. Deliver the finite model and generated permission projection. Keep the PR draft
   if any runtime test has not run.
2. Add channel queues, backpressure, upgrades, multiple lines and repeated requests.
   Validate a second encoding with TLC or Murphi. Add fair SCC liveness checks.
3. Add explicit MESI and MOESI directory profiles. Model Owned data separately
   from Trunk permission. Do not advertise a configurable profile before tests exist.
4. Add a real two-client TileLink-C RTL fixture and project-owned bindings.
   Check accepted last beats and dirty data against an independent write oracle.
   Prove a refinement contract before making a protocol implementation claim.

Follow-up work: [fair progress and directory profiles #361](https://github.com/riscPrint/risc-v-workstation/issues/361)
and [TileLink-C RTL refinement #363](https://github.com/riscPrint/risc-v-workstation/issues/363).
No core source changes are needed.
