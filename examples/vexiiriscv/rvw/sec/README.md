# Security runs on VexiiRiscv

Project data for `rvw sec` native runs (see `rvw/src/rvw/sec/README.md`).

```sh
rvw/sec/build-rtl.sh "$RVW_SEC_RTL/vexii"      # VexiiRiscv.v of the rv32im configuration
rvw/sec/build-rtl.sh "$RVW_SEC_RTL/vexii" rv32imasu   # rv32imasu/VexiiRiscv.v (S/U, Sv32, PMP)
rvw sec isolation --manifest rvw/sec/tlb-us-leaky.json --out out/tlb
rvw sec contract --manifest rvw/sec/constant-time.json --out out/ct
rvw sec ift-core --binding rvw/sec/core.json --policy rvw/sec/ift/memory-policy.json \
  --asm ../vexriscv/rvw/sec/ift/leak-index.S --out out/ift
```

VexiiRiscv has no RVFI port. `core.json` takes the commit PC from the upstream
WhiteboxerPlugin, so only `pc` and `insn` are compared with Spike. CSRs live in a
RAM, so there is no single `mscratch` source signal for `ift-core`.
The constant-time run finds data-dependent divide latency (`DivRadix2`).

Also here: `campaign.json`, `probe-ct.json`, `model-precheck.json` and
`model-precheck-mul.json` (a planned early-out multiplier), `soc-sec.json` and
`ift/auto-policy.json`. `core.json` declares the Whiteboxer prediction-learn
port as a branch probe event.

`core-su.json` binds the supervisor profile `rv32imasu` (M/S/U, Sv32, 8 PMP
entries, cacheless buses). The commit port carries the privilege
(`rvw_privilege`), so `mode` is a checked C2 field; the trap tap gives the PC of
each `ecall`, which the commit port does not report. `tlb` events come from
the page-walk tap (`WalkTap`): walk start (VA, access), PTE reads and refill.
Isolation manifests (`isolation-{um,us,sm}-{ct,leaky}.json`, templates
`iso-*.S`) cross U-M, U-S (delegated) and S-M; public `a0` selects the
constant-time handler (0) or the secret-dependent loop (control).
`tlb-us-{ct,leaky}.json` (template `tlb-us.S`) test the TLB as a channel
from S to U. `SecRtl` sets `riscvsim.script`, which `VexiiTop` now reads.
