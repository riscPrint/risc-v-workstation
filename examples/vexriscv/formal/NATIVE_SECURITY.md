# Native security continuation

Fresh exports used private core revision
`a62c145aa042a5de874344e0a7683bd7c8c8c870` and the workstation generator at
`7023cb9686bb238fe31801c32e76d1b643999363`. The entry point was
`rvwvex.SecRtl`. Builds used `sbt-equiv` and `nice -n 10`.
No shared core source was changed. Source pins are local provenance.
An independent clean export reproduction was not run.

Run each exported variant in sequence:

```sh
rvw/.venv/bin/python examples/vexriscv/formal/pair-smoke.py \
  --rtl /path/to/rv32im/VexTop.v --csr-source CsrPlugin_mscratch \
  --out /path/to/new-run --depth 8 --timeout 90
```

The script now defaults to bounded IFT. Use `--ift-mode prove` for the old
unbounded IFT mode. The IFT policy marks external data responses and the
selected CSR register as persistent secret sources. It lowers finite memory
exactly. Memory response regions and response/address alignment are not inferred.

| Variant | Check | Depth | Result |
| --- | --- | --- | --- |
| RV32IM | Two-copy memory observation contract | 8 | Counterexample at cycle 5 |
| RV32IM | Initial-state independence | 8 | Counterexample at cycle 5 |
| RV32IM | Memory and CSR taint | 8 | Inconclusive before solving |
| RV32IMU PMP | Two-copy memory observation contract | 8 | Mapping refused |
| RV32IMU PMP | Initial-state independence | 8 | Mapping refused |
| RV32IMU PMP | Memory and CSR taint | 8 | Mapping refused |

Both counterexamples differ on data-bus command-valid. The memory contract
still has equal raw architectural prefixes at its failing sample.
The copies have independent uninitialized state. The configuration does not
zero the architectural register file. Bus responses are unconstrained.
These counterexamples do not isolate a memory-secret leak or an ISA fault.
They refute the exact observation contracts. No contract was changed to hide them.

The taint transform completed for RV32IM. The generated design then exceeded
the remaining 84-second native port-probe budget. It did not reach a solver.
This is not a taint proof.

The PMP export has two undriven signals:

- `DBusSimplePlugin_mmuBus_rsp_bypassTranslation`
- `IBusSimplePlugin_mmuBus_rsp_bypassTranslation`

Yosys `check -assert` refused the export. No constant or assumption was added.
PMP isolation is blocked on this export fault. No PMP, initialization or
whole-core security proof closed.

See `resume-security-results.json` for hashes, plans, outcomes and failure
locations. Full native job trees and VCDs remain in the private run directory.
VexiiRiscv security and initialization were NOT RUN.
