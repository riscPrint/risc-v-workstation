# ACT4 MU profile

This profile selects all applicable RV32IMC machine and user tests from ACT4
`56d40ab301dba23dd3104c17bd969afbaaea1931`. PMP is disabled in the RTL.
The standard Sm bootstrap remains in use. No bootstrap access is removed.
The harness drives software, timer and external interrupts through declared
MMIO devices. Fast IRQ and NMI inputs remain low. Sail generates signatures
with its independent devices. Native C1 and strict C2 results remain separate.
UDB has no exact word-split policy. The profile declares `custom` for Ibex.

Keep the ACT4 checkout and its own Python venv outside the repository. Use the
Ruby and Sail versions that ACT4 pins. On macOS, use a private XDG cache for
the UDB Z3 library. Link its `libz3.so` to the installed `libz3.dylib`.
Do not link a private checkout to a shared Python venv.

```sh
rvw regress plan --act4 rvw/act4/profile.json --json
rvw regress act4-build --profile rvw/act4/profile.json \
  --checkout "$ACT4_CHECKOUT" --out "$IBEX_WORK/act4"
rvw regress run --suite act4 --rvfi-trace --out "$IBEX_WORK/act4-run" --no-index --json
rvw regress cosim "$IBEX_WORK/act4-run" --platform rvw/platform.json \
  --out "$IBEX_WORK/act4-cosim.json" --json
```

The run limit is 500,000 cycles per program. Timeouts remain timeouts.
A plan or successful build is not a DUT result. Full conformance and device
qualification require further evidence. Generated tests and signatures stay
outside Git. The manifest binds the full ELF corpus before filters apply.
