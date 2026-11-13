# Verification plans

`rvw plan status plan.json --json` rolls up a project-owned verification plan.
`plan_status` is the MCP job. The Python API is `VPlan(path).status()`.
Use `--out status.json` to save a snapshot. Use `--previous status.json` to
compare against an earlier snapshot from the same plan.

```json
{
  "schema": "rvw.vplan/1",
  "requirements": {"ISA.ADD": "Add returns the required integer result."},
  "features": [{
    "id": "integer-add",
    "requirements": ["ISA.ADD"],
    "coverage": [{"path": "coverage.json", "groups": ["sem_add_rs1"]}],
    "tests": [{"path": "runs/add/result.json"}],
    "formal": [{"path": "formal/result.json", "properties": ["add-result"], "proof_kind": "unbounded"}],
    "checks": [{"path": "gate/verdict.json", "kind": "gate"}]
  }]
}
```

Paths are relative to the plan file. Each evidence reference can add a `sha256`
to require exact bytes. Without that pin, the report captures the current bytes
and records their hash. Requirements need nonempty descriptions. Feature IDs
must be unique. Every feature must link declared requirements. Unassigned
requirements remain visible.

## Evidence rules

Coverage references require explicit `groups`. Functional groups need fixed
expected denominators. Unseen bins remain holes. RTL group names are exact bin
or sequence IDs. Sampling must be complete. Code groups are exact native instance
scopes. Collapsed scopes cannot supply exact denominators. Code exclusions do
not remove holes in this first rollup.

Test references accept C1 and C3. C1 must be a conclusive pass. C3 can select
explicit test `ids`; missing, failed or inconclusive tests remain holes.
Formal references select named properties in `rvw.formal-app-results/1`.
Each child result must have assertions, a passing result, matching proof kind
and a reachable legal environment. Bounded evidence cannot meet an unbounded
obligation. Proof assumptions and the missing activation check remain explicit.

Check kinds are `gate` for a valid accepted C4 verdict and `block` for a recorded
eligible block reuse check. Features can declare `scope` as `block` or `integration`. The default is
`integration`. Block-only evidence cannot close an integration feature.
Block evidence does not cover new integration wiring.
Unknown schemas, stale pins and missing files remain holes. A feature with no
evidence checks stays open.

The result schema is `rvw.plan-status/1`. Features have recorded closure status,
coverage totals, evidence hashes and holes. Trends report changes in hole count
and covered bins. A different coverage context produces an incompatible trend
instead of a numeric gain. Plan changes refuse comparison.

## Decisions and limits

This tool builds on existing C1/C3/C4, coverage and formal report formats.
It does not run tests or prove properties. Links are project declarations.
`reported_closed` means that the selected recorded evidence has no reported
hole. It does not establish complete requirements, correct mappings, runtime
assumptions, unconditional proof, whole-core closure or C4 acceptance.
Native campaign qualification and proof exclusion rollups remain separate.

## Probe goal evidence

Coverage references also accept `rvw.probe-coverage/1`. Select explicit event
or sequence IDs in `groups`. The report must have qualified execution and a
complete strict reference comparison, with zero masks and synchronization.
The result keeps the plan and generated RTL identities in the coverage context.
A pending sequence is a hole until at least one completion is observed.
The report does not prove probe wiring or complete requirements.

Both example cores have `verification-plan.json` and a saved status from real
native samples. Their plans retain native point and retirement-pair holes.
They pin evidence hashes. Missing worker-local C1 files remain missing evidence
on a clean checkout. Saved status path aliases are for display.

## Evidence verdict bound

Entries, features and the report include `verdict`. The report retains the
weakest selected input verdict. Missing evidence and unassigned requirements
prevent pass. `reported_closed` is a planning count. It does not grant C4 acceptance.
See `docs/contracts/evidence.md` for layer ownership and aggregation rules.
