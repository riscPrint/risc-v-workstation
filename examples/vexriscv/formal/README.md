# Real-core two-copy controls

```sh
rvw/.venv/bin/python examples/vexriscv/formal/pair-smoke.py \
  --rtl /path/to/VexTop.v --out /path/to/new-proof --depth 8 --timeout 90
```

Use a self-contained RTL export of the example core. Put the native formal tools
on PATH first. The script copies the export into its private output directory.
It records the SHA-256 and complete port interface. Native commands use the
`vex-equiv` lock and `nice -n 10`. Cases run in sequence. Each has a 90-second
budget by default. The script does not build the core or edit its sources.

## Recorded run, 2026-11-13

The supplied export had SHA-256
`1a791f8d828a42b774181017108324ef23675253056effdb53c405b695f33415`.
Both depth-eight checks and the memory source/sink IFT attempt returned
`inconclusive` before solving. Yosys reported:

```text
Warning: Wire VexTop.\CsrPlugin_stvec_mode [1] is used but has no driver.
Warning: Wire VexTop.\CsrPlugin_stvec_mode [0] is used but has no driver.
ERROR: Found 2 problems in 'check -assert'.
```

`pair-results.json` records these attempts. No security or initialization proof
closed. The IFT attempt requested the existing unbounded policy flow, but it
also stopped before instrumentation or solving. This export was captured from an existing example build. It was not
freshly elaborated for this run. Its source revision was not certified.

## Limits

The secret source is the external memory response data port. It covers all
responses. It does not select a memory region or mark CSR state secret. The
architectural guard compares raw `rvfi_pc_rdata` and `rvfi_rd_wdata` each cycle.
It does not align transactions or qualify these payloads by `rvfi_valid`.
Different raw prefixes can end a comparison class early. A bounded pass would
apply only to this exact observation contract. The initialization case compares
raw fetch PC even when fetch-valid is low.

CSR source injection, region-specific policies, internal taint instrumentation,
PMP/ePMP isolation, instruction coverage and long bounds remain open. The original captured
VexRiscv configuration has no PMP. A later optional PMP variant is recorded
in `NATIVE_SECURITY.md`. VexiiRiscv PMP proofs were not run. These controls do
not establish digital noninterference, ISA correctness or physical security.

## Fresh exports and CSR sources

See [the continuation results](NATIVE_SECURITY.md) for fresh RV32IM and PMP
exports. The new script accepts `--csr-source CsrPlugin_mscratch` and defaults
to bounded IFT at `--depth`. Use `--ift-mode prove` for unbounded IFT.
The older results above remain historical attempts.

## M unit and Sail UF route

See [M_ROUTE.md](M_ROUTE.md) for the product-mode adapter, reduced divider
operand domains and pinned Sail MUL/MULHU checks with abstract multiplication.
Reduced-domain proofs do not establish unrestricted RV32 instruction signoff.
