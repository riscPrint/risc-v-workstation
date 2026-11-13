# In-order own-model description

`own.json` describes this example's single-issue RV32IM pipeline for the
trace-driven model. It uses `rvw.arch-core/1` with kind `minor` and an explicit
`ooo` table with `issue_order: in_order`. Widths match the example's one decode
and execute lane. RAM is 16 MiB. There are no caches or address translation.
Execution latencies and queue sizes are timing approximations. They are not
an elaborated snapshot. The model does not reproduce all VexiiRiscv interlocks.

```sh
rvw ooo rvw/arch/own.json RUN/rvfi.jsonl --json
```

See [the correlation procedure](../../../../Arch/ooo/correlation/README.md)
for six real RTL programs, training-only fitting and held-out IPC errors.
This example has no SpinalProbes binding. Its calibration is IPC-only.
The C2 trace comes from the upstream VexiiRiscv probe. That commit trace does
not supply the missing SpinalProbes counters.

The `rv32im` own-model description selects sequential prediction. The cached
`rv32im_cached` RTL config adds BTB, GShare and RAS. This cacheless description
does not describe the cached config. Use separate parameters for that config.
