# Security runs on VexRiscv

Project data for `rvw sec` native runs (see `rvw/src/rvw/sec/README.md`).

```sh
rvw/sec/build-rtl.sh "$RVW_SEC_RTL/vex"        # rv32im and rv32imu VexTop.v
export RVW_SEC_RTL=/path/to/rtl RVW_SEC_WORK=/path/to/cache
rvw sec ift-core --binding rvw/sec/core.json --policy rvw/sec/ift/memory-policy.json \
  --asm rvw/sec/ift/leak-index.S --out out/ift
rvw sec contract --manifest rvw/sec/constant-time.json --out out/ct
rvw sec isolation --manifest rvw/sec/isolation-ct.json --out out/iso
rvw sec spec-suite --binding rvw/sec/core.json --template rvw/sec/spec.S --out out/spec
```

- `core.json`: the example `rv32im` configuration. `core-mu.json`: the same core
  with user mode (`SecRtl` variant `rv32imu`) and the Spike platform `platform-mu.json`.
- `core-leaky.json`: RTL built from a private copy with `leaky-transient-load.patch`
  applied. The patch lets flushed loads reach the data bus. It is a positive
  control for the speculative receiver, not a core change.
- `ift/`: programs and policies (secret `secret_key` words, or the `mscratch` register).
- `case.S`, `spec.S`, `isolation-*.S`: case templates for `python -m rvw.sec.core_adapter`.
