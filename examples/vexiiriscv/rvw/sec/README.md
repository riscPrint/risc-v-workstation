# Security runs on VexiiRiscv

Project data for `rvw sec` native runs (see `rvw/src/rvw/sec/README.md`).

```sh
rvw/sec/build-rtl.sh "$RVW_SEC_RTL/vexii"      # VexiiRiscv.v of the rv32im configuration
rvw sec contract --manifest rvw/sec/constant-time.json --out out/ct
rvw sec ift-core --binding rvw/sec/core.json --policy rvw/sec/ift/memory-policy.json \
  --asm ../vexriscv/rvw/sec/ift/leak-index.S --out out/ift
```

VexiiRiscv has no RVFI port. `core.json` takes the commit PC from the upstream
WhiteboxerPlugin, so only `pc` and `insn` are compared with Spike. CSRs live in a
RAM, so there is no single `mscratch` source signal for `ift-core`.
The constant-time run finds data-dependent divide latency (`DivRadix2`).
