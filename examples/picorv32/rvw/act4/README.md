# ACT4 on the mapped Verilog adapter

This profile selects 51 I, M and Zmmul cases for the RV32IM project from
`rvw init --hdl sv`. It uses the same generic ACT4 builder, C1 adapter
contract and regression suite selection as the Spinal examples.

The DUT has no Zicsr interface. The reset linker and bootstrap execute no
CSR instructions. ACT4's Sm parameters describe its signature model
scaffolding. They do not declare DUT CSR support. No standard Sm, trap or
privileged-suite qualification is claimed. Sail-only devices are not DUT
devices. Every selected test body and signature check remains present.

## Build and run

Use the pinned upstream PicoRV32 file and the setup in the project README.
Use the ACT4 revision in `profile.json`. From the project:

```sh
rvw regress plan --act4 rvw/act4/profile.json --json
rvw regress act4-build --profile rvw/act4/profile.json \
  --checkout "$ACT4_CHECKOUT" --out rvw/out/act4
rvw regress run --suite act4 --rvfi-trace --jobs 1 --out rvw/out/act4-run
rvw regress cosim rvw/out/act4-run --platform rvw/cosim.json
```

The launcher accepts `RVW_CORE_LOCK` and `RVW_SBT_LOCK` for private build
locks. Their defaults remain `picorv32` and `sbt`.

## Native results on 2026-11-13

All 51 cases built and ran through `rvw regress`. C1 reports 50 pass and
one fail. All 50 passing cases have complete strict Spike matches, with
zero masks and zero synchronization. See `observations.json` for each ELF,
raw C2 hash and reference result. `build-manifest.json` retains the build
record. The upstream pin is `ef203c2b0a3fb793280f5114941416c425c5b461`.
No core source was changed.

The declared `full_word` memory read convention describes the mapped
adapter's raw bus view. The generic normalizer checks the decoded load,
address, alignment and full-word strobe before it derives the active byte
lanes. It does not mask destination register values. With the default
architectural-load convention, four passing byte/halfword load cases had
trace-view differences. The shared `rvw/cosim.json` now states the actual
view. Both the regression comparison and direct comparison use it.

`I-fence-00` remains failed. Its first difference is `0x0330008f` at
`0x80000054`, FENCE with rd=x1. Spike preserves x1. RTL reports a write to
x1 and fails the signature check. The [RV32I FENCE rule](https://docs.riscv.org/reference/isa/unpriv/rv32.html)
requires base implementations to ignore the reserved rs1 and rd fields.
This difference is retained. No comparator exception or core fix is added.
These are instruction-case results, not certification or memory-order proof.
