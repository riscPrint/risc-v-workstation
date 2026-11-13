# ACT4 suite build contract

`rvw.act4/1` is a project-owned JSON description. It selects a pinned ACT4
revision, a cosim platform file, UDB extension versions and UDB parameters.
`test_extensions` selects a nonempty subset. `include_priv_tests` is explicit.
`privileged_extensions` declares additional supervisor options. `files` names
`rvmodel_macros.h`, `sail.json` and `link.ld`, relative to the description.
The project must review these files against its platform. The halt convention
is `tohost-1-3`. An ISA string alone cannot describe WARL behavior or devices.

`rvw regress act4-build` runs the upstream build in a new output directory.
ACT4 runs Sail to produce expected signatures, then compiles the final
self-checking ELF. The command retains intermediates and the build log.
`rvw.act4-build/1` records the revision, input hashes, commands, final ELF
hashes and selection. A failed or empty build has status `error`.

A suite can set `act4_manifest` to this manifest. Discovery checks the entire
ELF set and hashes before it applies test filters. Changed or missing ELFs
are errors. This manifest records the local build, not external certification.
Run ELFs through `rvw regress run --rvfi-trace`. Use `rvw regress cosim` for
Spike comparison. Keep C1 signature results and reference comparison separate.
A signature failure or reference mismatch is never converted to a pass.

Build manifests also record compiler and reference executable hashes and version
lines. `signatures` records each retained Sail `.sig` hash. Selection includes
the project's explicit `limits` as `limitations`. Model-only devices required
by ACT4 must be stated in the project profile limits. They do not establish
DUT device support.

Set `"all_applicable": true` in the JSON profile to let pinned ACT4 metadata
select all compatible groups from the UDB declaration. Do not also set
`test_extensions`. This mode includes privileged test directories by default.
The plan reports `include_priv_tests`; a project can set it explicitly.
The build explicitly clears extension exclusions. The plan
labels this mode `all-applicable`; the build manifest lists the final tests.

`rvw.act4-observations/1` is a retained native observation package. It records
source pins, build input hashes, per-extension counts and each test's C1 and
strict Spike status. Failed baselines remain separate from final instruction
suite counts. A core finding names its first difference and reproduction.
These observations do not grant a regression gate accept or certification.
