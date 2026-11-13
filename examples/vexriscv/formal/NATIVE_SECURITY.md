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

## PMP environment binding, 2026-11-13

The example now binds both response `bypassTranslation` metadata bits in
`PmpResponseBinding`, from `rvw/sec/pmp-response.json`. This PMP-only variant
uses physical addresses without page translation. Both response bits are
true. They do not bypass the PMP permission outputs. The external core source
is unchanged. Yosys `check -assert` accepts the fresh export. No undriven
net is silently converted to a constant by the formal mapper.

| Fresh PMP export check | Depth | Result |
| --- | --- | --- |
| Two-copy memory observation | 5 | Pass within bound |
| Initial-state independence | 5 | Pass within bound |
| Two-copy memory observation | 8 | Counterexample at cycle 5 |
| Initial-state independence | 8 | Counterexample at cycle 5 |
| Memory taint | 5 | Inconclusive within 45-second budget |

The depth-5 checks end before the cycle-5 failure. They cannot qualify this
core. The two depth-8 failures retain independent initial state and
unconstrained bus inputs. They do not isolate a PMP permission violation.
A CSR-programmed PMP permission proof remains open.

An asynchronous-reset assertion fixture returns `unsupported` before a solver
starts. The diagnostic gives the sampled-reset assertion fix and the shared
SYNC elaboration fix for IFT. It does not remove a property to obtain a pass.
See `pmp-bound-results.json` for compact receipts.

## Closed-core PMP isolation observations

`pmp-isolation.py` now runs the static isolation policy on actual emitted
data commands from the fresh PMP export. Project bindings add output aliases
for bus commands, pre-PMP access attempts and the privilege state used by
`PmpPluginNapot`. They retain every original cell and input. No internal
signal is cut or tied. The policy checks the starting byte of each emitted
data command. It denies U-mode access to the example keystore at
`0x80008000..0x800080ff`. Public instruction and bus responses stay arbitrary.

```sh
rvw/.venv/bin/python examples/vexriscv/formal/pmp-isolation.py \
  --rtl /path/to/rv32imu-pmp/VexTop.v --out /path/to/new-isolation --depth 8
```

| Bound | Data-command isolation | U-mode keystore attempt before PMP |
| --- | --- | --- |
| 8 | Pass within bound | Not reached within bound |
| 16 | Pass within bound | Inconclusive, 60-second reach query timeout |

The attempted-access check uses the pre-PMP request, not the emitted grant.
It is a separate negated reach predicate. Neither isolation pass demonstrates
that the protected U-mode path was exercised. These results therefore do not
qualify CSR-programmed PMP isolation. Fetch isolation, full access extents,
initialization independence and software setup remain outside this policy.
The two-copy cycle-5 counterexamples above remain valid separate results.
See `pmp-isolation-results.json` for both bounded receipts.
