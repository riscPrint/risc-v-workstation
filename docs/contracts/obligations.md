# Verification obligations contracts

Part of the [platform contracts](../PLATFORM_CONTRACTS.md).

## Reviewed specification obligation catalogs

The optional `rvw.isa/1` `specifications` entries can bind a document and a
reviewed `rvw.spec-obligations/1` catalog. Each entry has `kind`
(`isa|profile|debug|platform`), `revision`, `path`, `sha256` and
`obligations` (`path`, `sha256`). Paths use the corresponding opcode source
root. Catalog rows in `obligations` have unique `id`, exact document excerpt
`text`, `checkers` and `tests` arrays. Diff verifies both hashes and document
excerpt membership. `rvw.isa-diff/1.obligations` reports added, removed and
changed rows, affected checkers, missing tests and present test hashes.
It reports metadata-only pins as unchecked. A changed catalog requires adoption.
Catalog completeness needs review. Test presence does not establish execution.

`rvw.isa/1.probes` can configure `compiler|dut|reference|act|coverage` probes.
Kinds are `gcc` (native target macros), `command` (native JSON capability
output), and `json|toml` (captured settings file with optional `key` path).
Command probes return `rvw.isa-consumer/1` with `xlen`, `extensions` (versions
or null), and `options`. File probes select the same fields. Paths use the
manifest directory. `rvw.isa-check/1` includes observed `probes` and
`unchecked_consumers`. `consistent` requires all five inputs with known,
matching versions and options. Missing evidence gives `inconclusive`.
Contradictions are errors. These statuses describe configuration consistency.
They do not certify ISA implementation or compliance.

`rvw.isa/1.semantics` can include `forms` and `crosses`. Forms map instruction
names to fields with `bits` (`[hi,lo,destination_lo]` slices), `width`, `bins`
(explicit values or `boundaries`), optional `signed`, `offset` and register
`bank`. Crosses declare `id`, `instruction`, `fields`, and exhaustive
`combinations` (`bin`, `status`, `reason`) within those finite field domains.
Statuses are `legal|illegal|unavailable`. Functional plans retain the catalog.
Cross reports retain every bin in the denominator and add `classifications`
with observed `count`. No catalog declaration is a proof exclusion.

`rvw.coverage-report/1.scala_mapping.methods` counts source mapping methods.
The `covered-span-assignment-links` method navigates to a unique local full
SpinalDB data assignment for an exact covered RTL target. Multiple, partial,
init/reset and nonlocal assignments refuse that inference. Mixed links have a
separate method. These links do not prove individual Scala statement hits;
`scala_mapping.statement_hit_status` remains `undetermined`.


### Cooperative farm capacity extensions (#57)

Host capacity and request resources support `disk_bytes` and `jobs` in addition
to CPU slots, memory bytes and named locks. A host can set `projects` with
per-project limits for those four dimensions. Requests then require a configured
`project`. All active requests for that project share its quota. Host aliases
share the same host state. An oversized request is refused; a capacity conflict
waits within the request timeout. Disk admission also checks current free space.
Reports include effective `limits`, `queued_s`, `held_s`, `released` and `outcome`.
Handled cancellation releases all reservations. These fields describe reservations,
not actual consumption. OS resource limits and cumulative project accounting are
not provided. See `rvw/src/rvw/farm/README.md` for defaults and remaining limits.

### Paired SoC bridge observations (#134)

The optional extended `soc check --transactions` JSONL record includes `write`,
`data`, `error`, `beats`, and optional `register`, in addition to the original
address fields. Bindings can declare `byteorder` and `software_byteorder`.
Beat masks index lanes by ascending address. The format and bounded comparison
rules are defined in `rvw/src/rvw/soc/README.md`. Matching samples never produce
a pass. Endpoint pairing and observation provenance remain the capture
producer's responsibility. The bundled captures do not emit extended records.

### riscv-formal input provenance (#63)

C3 `source.formal_inputs.settings_sha256` binds the selected formal settings.
`source.formal_inputs.committed_inputs.files` lists copied input hashes and their
comparison with repository HEAD bytes. Rows report `committed`, `modified`,
`untracked_or_unavailable`, or `unavailable`. The nonempty list has
`all_committed=true` only when every row matches a commit. This is file provenance,
not a generator-origin or adapter-conformance claim. `source.identity_complete`
remains false. C4 remains bounded and cannot accept. No C1 ELF run is fabricated.

## Verification obligation plans

`rvw.verification-obligations/1` declares explicit `specifications` versions and
`obligations`. Extension obligations expand operand bins, exception scenarios
and dependency scenarios. Environment-control obligations expand project legal
writes, contexts, transitions and enabled/disabled expectations for menvcfg,
senvcfg or henvcfg. Each obligation includes attributed independent reference
vectors and attributed mutants that differ from a named vector.
`rvw.verification-plan/1` output has `status: generated` and `not_run` cases.
No RTL execution is implied. `rvw verification-plan check` compares supplied
observations only for reference cases and writes C3 with incomplete source
identity. Missing observations are errors; differing observations are failures.
Other case kinds remain unexecuted. C3 vector passes do not establish plan
closure, mutation coverage, architectural correctness or C4 acceptance.

## Pinned named-profile obligations

`rvw.profile-plan/1` supplies `isa_manifest`, selected `profiles` and hash-pinned
AsciiDoc `documents`. Optional tables map obligation IDs to `proofs`, `tests`,
and `checkers`; `unsupported` lists IDs or extension names. Optional extension
obligations activate from the selected ISA. Supervisor profiles inherit the
unprivileged extension requirements without weakening mandatory items.

`rvw.profile-report/1` preserves full named requirement text, source line/hash,
source revision/URL when supplied, and separate implemented/verified/missing/
unsupported/not-selected inventories per profile. Verified requires a hash-bound
unbounded pass with assertions and reachable environment. It is scoped to the
reviewed obligation-to-proof mapping and retains restrictions. Base clauses,
notes, implicit dependencies and full-profile acceptance are excluded.

A baseline diff reports changed text, mandatory/optional category and activation,
affected checkers and missing tests. Test presence has hashes but implies no
execution. Changes require explicit adoption. This command changes no source,
pin or model. Valid reports exit 3 and remain inconclusive. Input errors exit 2.
