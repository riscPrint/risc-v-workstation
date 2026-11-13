# NaxRiscv findings

Security findings from `rvw sec` runs on 2026-11-13. Core `9f452d50560d02fb391bc8039f5453c54e0911af`,
configuration `rv32imasu`, Verilator 5.049. Every compared C2 trace matched
Spike in all fields. Inputs: `rvw/sec/`. No upstream report was filed.

These are confirmed leakage findings. They are not functional defects: the
architectural results are correct. They matter for code that must run in
constant time on this configuration.

## NAX-SEC-DIV-001

Operand-dependent divide latency. `rvw sec contract --manifest rvw/sec/ct.json`
reduced the constant-time program to one instruction:

```
remu x13, x6, x7     # x6=7, x7=3: 7 cycles;  x6=0x7fffffff, x7=1: 19 cycles
```

The architectural traces are equal (same PCs and memory addresses); retirement
timing differs by 12 cycles. In the full program each of `div`, `divu`, `rem`
and `remu` took 6 or 7 cycles for 7/3 and 18 or 19 cycles for 0x7fffffff/1
(121 against 169 cycles in total). Do not divide secrets in constant-time code
on this configuration.

## NAX-SEC-SPECTRE-001

Transient loads leave a secret-dependent data-cache footprint (Spectre v1 and
v2 patterns). `rvw sec spec-suite --binding rvw/sec/run.json --template rvw/sec/spec.S`:

```
andi t0, x7, 0x7c0        # secret-derived offset: 64 or 1024
la   s1, sec_probe
add  t0, s1, t0
li a0, 64; li a1, 16
bgeu a0, a1, 1f           # taken; the cold predictor falls through
lw   t1, 0(t0)            # wrong path: fills the secret's cache line
lw   t2, 0(t1)
1: nop
lw t5, 64(s1)             # receiver (public addresses)
lw t5, 1024(s1)
```

For secret 64, the receiver load of line 64 retires 4 cycles after the `nop`
and the load of line 1024 6 cycles later (a miss). For secret 1024 the pattern
is reversed (9 and 0 cycles). The branch mispredict is in the counters
(`cond_mispredicts` 1); total cycles differ by one (120 against 119). The v2
gadget (fall-through after a late-resolved `jalr`) shows the same pattern.
Control: `rvw/sec/spec-v1-control.json`, the same gadget with the wrong-path
load replaced by `nop`, is `no_leak_observed`. The rsb and v4 gadgets were
`no_leak_observed` in this run; that covers only those gadgets.

This is the expected behavior of an out-of-order core without speculation
barriers. Code that indexes memory with secrets behind a bounds check needs
a software or hardware mitigation on this core.

## RV64 configuration limits

| Finding | Minimal reproduction | Observed result | Scope |
|---|---|---|---|
| RV64 static translation does not elaborate | Pinned `naxriscv.Config.plugins(xlen = 64, withMmu = false, withSupervisor = false, withUser = false, withRvc = false, withFloat = false, withDouble = false)` | `StaticAddressTranslationPlugin.scala:50` assigns a 34-bit pre-translation address to a 32-bit translated address. Fetch and Lsu2 fail `PhaseNormalizeNodeInputs`. | Core elaboration difference. No RTL simulation or Spike result. |
| MMU plugin requires supervisor mode | `Config.plugins(xlen = 64, withMmu = true, withSupervisor = false, withUser = false)` | Null dereference at `MmuPlugin.scala:208` when the SATP callback reads the absent `mstatus.tvm` field | Core elaboration difference. This setup is not offered. |
| Upstream commit observer assumes S exists | Construct `NaxriscvProbe` on M-only RTL | Null dereference at `NaxriscvProbe.scala:142` for `ioInt.supervisor.external`; no instruction executes | Simulation observer limitation. The integration generates `CommitProbe` from the pinned observer with this optional interrupt checker guarded. Wide wire reads also use the generic `SimEncoding.longBits` helper. Core source stays unchanged. |

Pin: `9f452d50560d02fb391bc8039f5453c54e0911af`.
SpinalHDL: `c362657003fa178350d6955055867e9ab363c44a`.
The project leaves upstream source unchanged. The M-only RV64 config sets
the static translator's public `physicalWidth` parameter to 64 before
elaboration. Its pre-translation and physical widths then agree.
The Sv39 config keeps the upstream 32-bit physical address limit.
