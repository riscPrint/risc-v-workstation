# Hardware leakage contracts

Part of the [platform contracts](../PLATFORM_CONTRACTS.md).

## Hardware leakage campaign result

`rvw formal security contract` writes `rvw.leakage/1` in `result.json`.
`verdict` is `violation`, sampled `no_violation`, or `inconclusive`.
Exit codes are 1, 0, and 3 respectively. This is separate from a C4 accept or
formal proof. `cases`, `compared_pairs`, `zkt_add_comparisons`, `zkt_verdict`,
`violations` and `errors` preserve the tested scope. A case with missing evidence
or architectural differences cannot contribute a clean comparison. No comparable
pair is inconclusive. A witness can coexist with incomplete cases.

The sequential Spike contract exposes retired PCs and memory addresses. RTL
adapters return `complete`, reference-comparable `effects`, strictly increasing
retirement `cycles`, and integer `observations` for exactly the declared channels.
The runner compares only equal public contexts and equal contract traces.
It records source inputs and adapter responses. Adapters must bind their native
tools and all external dependencies. See `rvw/src/rvw/formal/security/README.md`.
The hardware threat model and unmodeled channels do not expand C8.

### Formal campaign observations in C3 and C4

`rvw formal sby-regress` writes standalone C3 suites named `formal-sby`.
Each row names one single-assertion SBY job. Extra fields retain `formal_status`,
`requirements`, `assumptions`, `configuration` and `job_sha256`.
`formal_status` is `bounded_pass`, `unbounded_engine_pass`, `counterexample`,
`timeout`, `unknown` or `error`. C3 maps engine passes to `pass`, counterexamples
to `fail`, timeouts to `timeout`, and other states to `error`.
Every row carries an `inconclusive` reason: input closure, property attribution
and vacuity are not checked. A raw engine pass cannot earn acceptance.
C4 records `verdict: inconclusive` and `tests: incomplete`.
Retained standalone C3 directories form the history store. Each sample keeps
configuration and assumptions. Samples cannot be pooled into one proof.

Formal results add `proof_kind: bounded | unbounded`.
Only `formal prove` selects unbounded mode. Depth-search summaries use
`rvw.formal-depth-search/1`, retain attempt paths and statuses, and report
`max_bounded_pass`. Their status is `fail` or `inconclusive`; never proof.
Cut-point records name the signal, width and `unconstrained_anyseq` semantics.
An abstract counterexample records `status: unknown`, not a concrete failure.

### Bounded riscv-formal results

`rvw formal riscv` writes standalone C3 `results.json` and C4 `verdict.json`.
Each requested task is a C3 entry. PASS requires exit 0 and SBY PASS. Missing
status, unreachable retirement cover, tool errors and wall timeouts are
inconclusive. Without retirement cover, assertion PASS entries carry an
`inconclusive` reason. `source.formal_inputs` records input hashes;
`identity_complete` is false. The suite records the maximum selected check depth as `bounded_depth` and the settings.
C4 rejects assertion failures. Other outcomes remain inconclusive, including
complete bounded tests. These files cannot establish committed gate acceptance.
C1 is not emitted because these jobs do not execute an ELF.

`check_options.<exact check name>` can set `cycles`, `engine` and `defines`.
Cycles are `[check]` for instruction checks, `[start, check]` for consistency
and cover checks, and `[start, trigger, check]` for liveness and unique.
Each C3 entry retains these values in `formal_settings`. Engines are
`abc bmc3`, `btor btormc` or `smtbmc` with a supported solver. Cover needs SMTBMC.
ABC jobs omit the unsupported SBY `skip` option. The checker cycle still
controls when each assertion fires. `instruction_models` maps instruction
names to model files. The runner copies these over the private checker tree
and hashes them. It does not modify the upstream models.
