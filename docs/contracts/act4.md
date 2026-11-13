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
