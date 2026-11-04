# Debug transport and instruction trace

This package will add tool-side checks for RISC-V Debug 0.13.2 and the baseline
E-Trace reference decoder (1.1.3-Frozen). OpenOCD is the reference debug client.
Spike supplies a simulated JTAG DTM and Debug Module for native reference tests.
A reference-model pass does not prove a core implementation.

## Decisions

Reuse OpenOCD and the upstream E-Trace decoder. Keep external tools optional.
Pin decoder source before use. Compare exact PC sequences with independent
retirement data. Missing packets or incomplete retirement data cannot earn a match.

## Limits

Core DMI/JTAG and encoder ingress hooks are proposals. Do not change core RTL.
N-Trace needs a separate decoder and campaign (#194). E-Trace is not N-Trace.
