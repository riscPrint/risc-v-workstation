package riscvsim.boom

import spinal.core._
import spinal.core.sim._
import boom.system.BoomSimTop
import boom.common.constants._
import riscvsim._

/** Small has one commit slot. Wider presets need separate per-slot CSR state. */
class BoomState(top: BoomSimTop) extends Area with ScalarOpConstants {
  val c = top.tile.core
  val floatingWrite = RegNext(c.rob.io.commit.arch_valids(0) &&
    c.rob.io.commit.uops(0).dst_rtype === RT_FLT) init(False)
  val destination = RegNext(c.rob.io.commit.uops(0).ldst)
  // ROB debug data is already converted to IEEE by core.scala at FP writeback.
  val data = RegNext(c.rob.io.commit.debug_wdata(0))
  Seq("rvw_fp_write" -> floatingWrite, "rvw_fp_destination" -> destination, "rvw_fp_data" -> data)
    .foreach { case (name, signal) => signal.setName(name); signal.simPublic() }
  c.csr.reg_fflags.simPublic()
  c.csr.reg_frm.simPublic()
  c.csr.reg_mscratch.simPublic()

  def enrich(r: RvfiRecord): RvfiRecord = {
    val flags = c.csr.reg_fflags.toBigInt
    r.copy(csrState = Map(0x340 -> c.csr.reg_mscratch.toBigInt),
      fpState = Some(RvfiFpState(!r.trap && floatingWrite.toBoolean,
        destination.toInt & 31, data.toBigInt, flags, (c.csr.reg_frm.toBigInt << 5) | flags)))
  }
}
