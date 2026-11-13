package rvwvexii

import spinal.core._
import spinal.core.sim._
import spinal.lib._
import spinal.lib.misc.pipeline._
import scala.collection.mutable.ArrayBuffer
import vexiiriscv.Global
import vexiiriscv.decode.Decode
import vexiiriscv.execute.CsrAccessPlugin
import vexiiriscv.execute.fpu.{FpuCsrPlugin, FpuFlagsWritebackPlugin}
import vexiiriscv.test.WhiteboxerPlugin

/** Simulation-only readout of the real enabled FP state write ports.
  * The two named FP configs have no H extension: ParamSimple's integer WB is stage 2.
  */
class FpEventTaps(wb: WhiteboxerPlugin#Logic, csr: CsrAccessPlugin,
                  fpu: FpuCsrPlugin, flagsWb: FpuFlagsWritebackPlugin) extends Area {
  require(wb.serializeds.size == 1, "FP capture currently binds one decode lane")
  val allocate = CombInit(wb.serializeds.head.fire).setName("rvw_fp_allocate").simPublic()
  val allocateId = CombInit(wb.serializeds.head.microOpId).setName("rvw_fp_allocate_id").simPublic()
  val bus = csr.bus.get
  val csrWriteNow = bus.write.valid && bus.write.moving &&
    (bus.write.address === 1 || bus.write.address === 2 || bus.write.address === 3 || bus.write.address === 0x300)
  val csrWrite = (RegNext(csrWriteNow) init(False)).setName("rvw_fp_csr_write").simPublic()
  val csrId = RegNext(csr.logic.fsm.interface.uopId).setName("rvw_fp_csr_uop").simPublic()
  val csrAddress = RegNext(bus.write.address).setName("rvw_fp_csr_address").simPublic()
  val csrData = RegNext(bus.write.bits).setName("rvw_fp_csr_data").simPublic()
  val dirty = (RegNext(fpu.api.gotDirty) init(False)).setName("rvw_fp_dirty").simPublic()
  val dirtyId = RegNext(Mux(csrWriteNow && bus.write.address =/= 0x300,
    csr.logic.fsm.interface.uopId, flagsWb.lane.execute(2).up(Decode.UOP_ID))).setName("rvw_fp_dirty_uop").simPublic()
  val pending = CombInit(csrWriteNow || fpu.api.gotDirty ||
    (flagsWb.logic.flagsOr.asBits.orR && !flagsWb.lane.isFreezed())).setName("rvw_fp_pending").simPublic()
  val flagEvents = ArrayBuffer.empty[(Bool, UInt, Bits)]
  private def flag(valid: Bool, id: UInt, value: Bits): Unit = {
    val index = flagEvents.size
    flagEvents += (((RegNext(valid && value.orR) init(False)).setName(s"rvw_fp_flag_valid_$index").simPublic(),
      RegNext(id).setName(s"rvw_fp_flag_uop_$index").simPublic(),
      RegNext(value).setName(s"rvw_fp_flags_$index").simPublic()))
  }
  if (flagsWb.logic.beforeCommit.nonEmpty) {
    val ctrl = flagsWb.lane.execute(2)
    // Use the core's already gated and bypassed pre-commit flags, not an earlier pipeline value.
    flag(!flagsWb.lane.isFreezed(), ctrl.up(Decode.UOP_ID), flagsWb.logic.flagsOrInputs.head.asBits)
  }
  for (spec <- flagsWb.portToSpec.values; (at, index) <- spec.ats.zipWithIndex if at > 2) {
    val ctrl = flagsWb.lane.execute(at)
    flag(ctrl.isValid && ctrl.up(Global.COMMIT) && spec.port.ats(index) && !flagsWb.lane.isFreezed(),
      ctrl.up(Decode.UOP_ID), spec.port.flags.asBits)
  }
}
