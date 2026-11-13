# Privilege campaigns

Build a project-owned RV64 control campaign:

```
rvw regress privilege build examples/privilege/controls.json --out rvw/out/controls
rvw regress privilege reference rvw/out/controls --timeout 2
```

The generator crosses TVM, TW and TSR with set/clear states and actual M/S/U
entry. It tests satp reads, satp writes, SFENCE.VMA, WFI and SRET. Each program
checks the trap cause and exception PC. It checks control retention on entry to
M-mode. It clears the bit and retries the operation in S-mode. SSIP is pending,
locally enabled and delegated. Global enables are clear. WFI has no minimum
sleep requirement. The expectations use the 20260120 privileged specification.

Use `modes` to select modes. The project supplies `isa`; the default is
`rv64im_zicsr_zifencei`. This first campaign requires S, U, PMP and RV64.
An unsupported configuration is not a passing disabled-feature test.

Merge the generated `suite.toml` section into the project's regression TOML.
Set its `dir` to the generated directory relative to that TOML. Run through the
project's existing C1 adapter:

```
rvw regress run --suite privilege --rvfi-trace --out rvw/out/controls-dut
rvw regress privilege check rvw/out/controls --results rvw/out/controls-dut --platform platform.json
```

`check` requires one conclusive passing C1 result per ELF and a complete strict
Spike match. A mismatch fails. Missing C1, missing traces, duplicate results,
incomplete comparison and synchronized comparison stay inconclusive. Functional
groups use all-member pass. Spike self-check results never earn DUT groups.
MCP tools expose build, reference and check with the same inputs.

## Decisions

Keep campaign generators separate from MMU and multi-hart modules. Reuse the
existing regression adapter and strict reference checker. Keep programs small.
Emit a new output directory for each build to prevent stale ELF discovery.

## Limits

This increment does not close #139. SUM, MXR and MPRV campaigns remain in the
existing MMU framework. Full disabled-feature combinations remain open. No RTL
run was made. The control programs do not test PLIC delivery, late WFI wake, reset,
Smrnmi, PMA, ePMP, AIA, CLIC, Sstc, state-enable, environment controls, CFI, RAS
or DVFS. These need separate campaigns and project interfaces.

## Timer and software WFI campaigns

Set `kind` to `wfi` and supply `timer.mtime`, `timer.mtimecmp`, `timer.msip`
and `timer.delta`. Addresses are integers. Delta is the future timer offset in
ticks. `examples/privilege/spike-wfi.json` declares the native Spike CLINT map.
Copy and change that data for the project's map. The generator does not choose
addresses for a core.

The four programs cross software/timer sources with global MIE clear/set.
They enable the local source. They drive the software event or program a future
timer compare. A masked case requires eventual pending and retained register
state without trap entry. An enabled case checks interrupt cause, exception PC
within the independent wait region, MIE clear on entry and retained state.
Legal early WFI return is allowed. The external C1 cycle bound limits waiting.
The programs restore the device interrupt state before reporting completion.
These cases do not test physical clock stop, delayed external input or reset.
They are a bounded increment for #149 and do not close that issue.

Builds also write `functional-groups.json` for `rvw cov functional --config`.
It describes CSR/mode, trap and interrupt observation domains. Observed bins
measure trace activity. Use `privilege check` for architectural pass groups.
An observed hit alone never establishes a correct outcome.
