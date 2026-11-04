# Agent benchmark task pack

This evaluator-only example pack uses schema `rvw.agent-tasks/1`. Pass it to
`rvw agent-bench dry-run` from the repository root. See
[the tool guide](../../rvw/src/rvw/agent_bench/README.md).

Tasks 01–08 cover add, subtract, AND, OR, XOR, logical left shift, logical right
shift and unsigned compare. Tasks 09–10 model signed compare and equality in a
VexRiscv ALU scenario. They do not execute VexRiscv. Each task replaces the intended
operation with the next operation in this list. Each task has 49 boundary pairs
and 64 pseudorandom pairs from seed 27. These are stored oracle values, not
calculated by the runtime evaluator.

Tasks 03, 06 and 09 contain a wave with a different RTL identity. Tasks 04, 07 and
10 contain a result with a different ELF identity. Correct agents must reject
these artifacts with the exact mismatched identity field.

`public` is the complete agent view. `private` holds cause IDs, defect labels and
hidden vectors. Never put this pack in an external agent's readable workspace.
The example labels are public repository data; use a separate private pack for
agent comparisons. These fixture identities do not certify native artifacts.
