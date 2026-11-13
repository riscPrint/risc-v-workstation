package rvwvex

import spinal.core._
import vexriscv.VexRiscv
import vexriscv.plugin._

/** Core-side E-Trace encoder ingress for the `rv32im_trace` configuration (project data, not
  * generic code). Retirement rows come from the write-back stage. Trap rows come one cycle after
  * the CSR trap redirect, from the actual mcause, mtval and mepc storage. M-only: priv is 3. */
class TraceIngressPlugin extends Plugin[VexRiscv] {
  override def build(pipeline: VexRiscv): Unit = {
    import pipeline.config._
    val csr = pipeline.config.get(classOf[CsrPlugin])
    val branch = pipeline.config.get(classOf[BranchPlugin])
    val wb = pipeline.writeBack
    def csrValue(address: Int): Bits = {
      val value = Bits(32 bits).allowOverride
      value := 0
      for (r <- csr.csrMapping.mapping(address).collect { case r: CsrRead => r })
        value(r.bitOffset, r.that.getBitsWidth bits) := r.that.asBits
      value
    }
    val insn = wb.input(INSTRUCTION)
    val opcode = insn(6 downto 0)
    val taken = wb.input(branch.BRANCH_COND_RESULT)
    val xret = wb.input(csr.ENV_CTRL) === csr.EnvCtrlEnum.XRET
    val itype = UInt(3 bits)
    itype := 0
    when(opcode === B"1100011") { itype := (taken ? U(5) | U(4)) }   // conditional branch
    when(opcode === B"1100111" || xret) { itype := 6 }               // jalr, xRET: uninferable
    out(wb.arbitration.isFiring).setName("trace_retire")
    out(itype).setName("trace_itype")
    out(wb.input(PC)).setName("trace_iaddr")
    val returning = wb.arbitration.isValid && xret
    val trap = RegNext(csr.jumpInterface.valid && !returning) init(False)
    val cause = csrValue(0x342)
    out(trap).setName("trace_trap")
    out(cause(31) ? U(2, 3 bits) | U(1, 3 bits)).setName("trace_trap_itype")
    out(cause(30 downto 0)).setName("trace_trap_cause")
    out(csrValue(0x343)).setName("trace_trap_tval")
    out(csrValue(0x341)).setName("trace_trap_iaddr")
  }
}
