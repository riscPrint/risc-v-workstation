package rvwvex

import spinal.core._
import vexriscv.plugin.CsrRead

/** Observation ports only. The VexTop core configuration is unchanged. */
class LifecycleUnit extends VexTop {
  setDefinitionName("LifecycleUnit")
  // Pipeline builds its plugins in an earlier pre-pop task. Observe them afterwards.
  addPrePopTask(() => {
    val observedWfi = out(Bool()).setName("observed_wfi")
    observedWfi := csr.inWfi
    val observedPrivilege = out(csr.privilege.clone()).setName("observed_privilege")
    observedPrivilege := csr.privilege
    val observedEpc = out(Bits(32 bits)).setName("observed_epc").allowOverride
    observedEpc := 0
    for (field <- csr.csrMapping.mapping(0x341).collect { case r: CsrRead => r })
      observedEpc(field.bitOffset, field.that.getBitsWidth bits) := field.that.asBits
    val observedStatus = out(Bits(32 bits)).setName("observed_status").allowOverride
    observedStatus := 0
    for (field <- csr.csrMapping.mapping(0x300).collect { case r: CsrRead => r })
      observedStatus(field.bitOffset, field.that.getBitsWidth bits) := field.that.asBits
  })
}

object LifecycleUnit {
  def main(args: Array[String]): Unit = {
    VexTop.spinalConfig.copy(targetDirectory = args(0)).generateVerilog(new LifecycleUnit)
  }
}
