# Verification-plan generation

Generate a custom extension plan from explicit project obligations:

```sh
rvw verification-plan generate Uvm/plans/example.json --out /tmp/plan.json
rvw verification-plan check /tmp/plan.json observations.json --out /tmp/results.json
```

`rvw.verification-obligations/1` requires a `specifications` object with named
versions and an `obligations` array. Each obligation has a unique `id` and
`kind`. An `extension` obligation requires `operand_bins`, `exceptions` and
`dependencies`. The generator expands the Cartesian operand product and adds
one case for each explicit exception and dependency scenario.

An `envcfg` obligation requires `csr`, `field`, `legal_writes`, `contexts`,
`transitions`, `enabled` and `disabled`. `csr` must be `menvcfg`, `senvcfg` or
`henvcfg`. Cases expand legal writes, contexts, transitions and both enabled
states. The project supplies the expected behavior for each state. Specify
the privileged and extension versions in `specifications`. No implemented CSR,
field or extension is inferred from a core name.

Each obligation requires `reference_vectors` and `mutants`. A vector needs
`id`, `inputs`, `expected` and `author`. A mutant needs `id`, `vector`,
`observed` and `author`. Its declared result must differ from its reference
vector. The generator does not create an oracle or mutate its own expression.
Authors must supply these independently. An author string records attribution;
it cannot prove independence.

Output uses `rvw.verification-plan/1`, `status: generated` and `not_run` on every
case. This is a plan, not executable ISA stimulus. Bind cases to a project
adapter or UVM sequence before execution. The example declares arithmetic only;
it does not define an instruction encoding or claim a RISC-V extension.

`check` compares supplied observations, keyed by case ID, to reference cases.
Missing observations are C3 errors with an inconclusive reason. Differences are
failures. Exact JSON values must match, including type. This command checks
reference cases only. Operand, dependency, exception, envcfg and mutant cases
remain unexecuted. C3 source identity is incomplete. A vector match is not
architectural conformance, mutant campaign success, plan closure or C4 acceptance.

## Decisions and limits

Keep specification versions and implemented controls in project data. Refuse
missing reference vectors or vacuous mutants. Do not invent expected traps or
legalization rules. This generator addresses the plan part of #155 and prepares
matrices for #177. Native custom-extension tests and actual environment-control
execution remain open. The tool does not edit a core or run a simulator.
