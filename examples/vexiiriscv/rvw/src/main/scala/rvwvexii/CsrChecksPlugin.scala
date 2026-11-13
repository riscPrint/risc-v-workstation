package rvwvexii

import spinal.core._
import spinal.lib.misc.plugin.FiberPlugin
import vexiiriscv.execute.CsrAccessPlugin
import vexiiriscv.misc.PipelineBuilderPlugin
import spinalchecks.DeclaredChecks

/** Independent accepted-transaction model. It never observes the CSR RAM as expected state. */
class CsrChecksPlugin(observationFault: Boolean = false) extends FiberPlugin {
  val logic = during setup new Area {
    val buildBefore = retains(host[PipelineBuilderPlugin].elaborationLock)
    awaitBuild()
    val csr = host[CsrAccessPlugin]
    val bus = csr.bus.get
    val expected = Reg(Bits(32 bits)) init(0)
    val known = RegInit(False)
    val read = bus.read.valid && bus.read.moving && bus.read.address === 0x340
    val write = bus.write.valid && bus.write.moving && bus.write.address === 0x340
    val observed = if (observationFault) bus.read.data ^ B(1,32 bits) else bus.read.data
    DeclaredChecks.rule("csr.read", "mscratch", "Accepted CSR reads equal the independently tracked last accepted software write", trigger = read && known) {
      read && known && observed =/= expected
    }
    when(write) { expected := bus.write.bits; known := True }
    buildBefore.release()
  }
}
