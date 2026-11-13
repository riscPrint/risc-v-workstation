# ACT4 instruction profile

This profile builds 69 instruction cases for the out-of-order RV32IMA
adapter. It selects I, M, Zaamo, Zalrsc, Zicsr, Zifencei and Zmmul. No core
name or test list is added to the generic selector.

The signature build uses a machine-mode view of the platform in
`platform-machine.json`. The RTL target remains `rv32imasu`. It still has
S, U and Sv32. The reduced bootstrap initializes the M-mode trap context.
This profile does not qualify standard Sm, supervisor tests or the MMU.
Sail-only interrupt devices are not DUT devices. The architecture ID is 5,
as declared in the pinned upstream `PrivilegedConfig.full`.

## Build and run

Set up the private core and pinned SpinalHDL as described in the project
README. Use the pinned ACT4 revision in `profile.json`. From the project:

```sh
rvw regress plan --act4 rvw/act4/profile.json --json
rvw regress act4-build --profile rvw/act4/profile.json \
  --checkout "$ACT4_CHECKOUT" --out rvw/out/act4
rvw regress run --suite act4 --rvfi-trace --jobs 1 --out rvw/out/act4-run
rvw regress cosim rvw/out/act4-run --platform rvw/platform.json
```

## Native results on 2026-11-13

All 69 cases built and ran through `rvw regress`. C1 reports 69 pass and
0 fail. All 69 have complete strict Spike matches, with zero masks and
zero synchronization. The counts by group, ELF hashes and raw C2 hashes
are in `observations.json`. `build-manifest.json` is the published build
record. It does not include the ELFs.

The core pin is `9f452d50560d02fb391bc8039f5453c54e0911af`. SpinalHDL is
`c362657003fa178350d6955055867e9ab363c44a`. The build uses a private core,
private targets, private locks and `nice -n 10`. One native model build
completed within the authorized 15-minute cap. An earlier short attempt
was stopped before that authorization. No core source was changed.

These results qualify the observed instruction cases only. They are not
architectural certification or a whole-core proof. Standard bootstrap and
supervisor ACT4 on this target are NOT RUN.
