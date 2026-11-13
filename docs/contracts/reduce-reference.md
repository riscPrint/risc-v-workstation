# Strict reference mismatch reduction

`rvw reduce --cosim-platform PLATFORM` and MCP `reduce_run.cosim_platform`
select a strict Spike predicate for a conclusive C1-passing run. The original
comparison must contain a mismatch with differing fields. Every trial requests
C2. Only a conclusive C1 pass followed by a strict mismatch can reproduce it.
A complete, nonempty, unmasked, unsynchronized match is a non-reproduction.
Reference errors, incomplete results, masked comparisons, synchronized
comparisons and missing traces are inconclusive. C1 failures do not reproduce
a reference mismatch. Existing C1-only reduction remains the default.

The signature is `cosim:` plus sorted differing field names separated by commas.
It preserves the observable difference class, not a proven root cause.
`rvw.reduce/1` adds optional `reference_platform` and `original_reference`.
Each trial adds `reference` with the comparison and predicate status. The report
retains C1 status separately. The platform is captured through C8. ELF bytes
must match each trial's C1 identity. No reference mask or synchronization option
is added by this predicate.
