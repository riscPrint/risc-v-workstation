# RV64 tool evidence

[The record](tool-results.json) retains native results and scope limits.
The config is the unchanged upstream core with the `rv64ima` adapter profile.

- Functional coverage: 85 strict-matched ISA traces, 33,733 instructions,
  zero unknown encodings. Word bins include ADDW 52, MULW 43 and DIVW 10.
- Instrumented DIVW has 140 complete strict-compared instructions.
- DIVW code coverage: 747/878 line points and 656/796 branch points hit.
  This is one instrumented program. It does not establish whole-core coverage.
- DIVW probes: typed commit count 138. Konata reports 140 retirements over
  855 event cycles. These sources have different tail scopes. No count is adjusted.
- Generated checks: 25 inserted, zero firings on each of two CSR programs.
  Both instrumented traces match Spike strictly: 49 and 26 instructions.
  The independent scratch read check activates four times. A zero firing count
  does not prove checks whose antecedents did not activate.
- CSR catalog: RV64 `mstatus` SD/SXL/UXL and `satp` MODE/ASID/PPN field views.
  This is catalog metadata, separate from runtime WARL readback qualification.
- Formal ISA: actual RV64 observer RTL, 32-cycle ADDW/SLLIW/MULW attempts,
  15 seconds per check. All are inconclusive. Activation did not close.
  No bounded or unbounded ISA proof is claimed.
- Divider security pair: complete strict match on each raw trace, zero masks
  and synchronization. The case-window observations are 42 versus 138 cycles.
  The contract reports a timing violation. The design has no asserted
  constant-time divider guarantee. This is a timing witness, not an ISA defect.

The source changes remove these width limits:

1. Formal observer data, memory masks and IXL used RV32 constants. They now
   follow XLEN. PC widening uses the core's canonical-address expansion.
   The observer recognizes OP-IMM-32 and OP-32 operand use.
2. The CSR runtime and independent scratch model required 32 bits. They now
   follow the selected model's XLEN. The separate CSR bank remains RV32 only.
3. Security ELF builds forced ILP32. They now select the integer ABI by ISA.
4. Security setup truncated secrets to 32 bits. RV64 uses a fixed 15-instruction
   byte construction for each register. The RV32 path remains unchanged.
5. The mapped security harness explicitly supports RV32 only. The new generic
   C1 adapter supplies the RV64 pair path through the existing contract command.

Three Scala tests elaborate RV32IM, RV64IMA and RV64 Sv39 observer and CSR widths.
Python tests check full-width setup, ABI selection, timing, completion scope
and rejection of partial, synchronized or masked captures. The legacy mapped
RTL security harness and the CSR bank are not claimed to support RV64.
