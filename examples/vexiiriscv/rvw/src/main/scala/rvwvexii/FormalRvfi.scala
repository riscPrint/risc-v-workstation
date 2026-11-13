package rvwvexii

import spinal.core._
import spinal.lib._
import spinal.lib.misc.plugin.FiberPlugin
import vexiiriscv.{Global, VexiiRiscv, ParamSimple}
import vexiiriscv.decode.Decode
import vexiiriscv.execute._
import vexiiriscv.misc.{PipelineBuilderPlugin, TrapPlugin}
import vexiiriscv.regfile.RegFileWriterService
import vexiiriscv.riscv.{IntRegFile, RS1, RS2}

/** Hardware-only committed-instruction observer. It does not observe trap entry.
  * A following commit supplies the previous instruction's next PC. */
class FormalRvfiPlugin extends FiberPlugin {
  val logic = during setup new Area {
    val hold = retains(host[PipelineBuilderPlugin].elaborationLock)
    awaitBuild()
    val lanes = host.list[ExecuteLaneService]
    require(lanes.size == 1, "formal observer supports one execute lane")
    val lane = lanes.head
    val c = lane.execute(host[TrapPlugin].trapAt)
    val fire = c.down.isFiring && c.down(Global.COMMIT)
    val id = c(Decode.UOP_ID)
    val insn = c(Decode.UOP).asBits.resize(32)
    val pc = c(Global.PC).asBits.resize(32)
    val source1 = c(lane(IntRegFile, RS1))
    val source2 = c(lane(IntRegFile, RS2))
    val writers = host.list[RegFileWriterService].flatMap(_.getRegFileWriters()).filter(_.payload.rfSpec == IntRegFile)
    val values = Vec.fill(64)(Reg(Bits(32 bits)))
    val tags = Vec.fill(64)(Reg(UInt(Decode.UOP_ID_WIDTH bits)))
    val slot = id.resize(6)
    val written = Vec.fill(values.size)(Reg(Bool()) init(False))
    // Clear on dispatch so a recycled micro-op ID cannot retain an old write.
    val dispatch = lane.ctrl(0)
    when(dispatch.down.transactionSpawn) { written(dispatch(Decode.UOP_ID).resize(6)) := False }
    for(w <- writers) when(w.valid) { values(w.uopId.resize(6)) := w.data; tags(w.uopId.resize(6)) := w.uopId; written(w.uopId.resize(6)) := True }
    val result = Bits(32 bits)
    val ready = Bool()
    result := values(slot); ready := written(slot) && tags(slot) === id
    for(w <- writers) when(w.valid && w.uopId === id) { result := w.data; ready := True }

    def output(width: Int, name: String) = out(Bits(width bits)).setName("rvfi_" + name)
    val valid = out(Bool()).setName("rvfi_valid")
    val order = output(64,"order")
    val instruction = output(32,"insn")
    val trap = out(Bool()).setName("rvfi_trap")
    val halt = out(Bool()).setName("rvfi_halt")
    val intr = out(Bool()).setName("rvfi_intr")
    val mode = output(2,"mode"); val ixl = output(2,"ixl")
    val rs1 = output(5,"rs1_addr"); val rs2 = output(5,"rs2_addr"); val rd = output(5,"rd_addr")
    val rs1data = output(32,"rs1_rdata"); val rs2data = output(32,"rs2_rdata"); val rddata = output(32,"rd_wdata")
    val pcBefore = output(32,"pc_rdata"); val pcAfter = output(32,"pc_wdata")
    val memAddr = output(32,"mem_addr"); val memRmask = output(4,"mem_rmask"); val memWmask = output(4,"mem_wmask")
    val memRdata = output(32,"mem_rdata"); val memWdata = output(32,"mem_wdata")
    // This first observer checks arithmetic and control-flow only. It refuses a
    // memory commit instead of emitting an invented memory transaction.
    val opcode = insn(6 downto 0)
    val isMemory = opcode === B(0x03,7 bits) || opcode === B(0x23,7 bits)
    val useRs1 = !(opcode === B(0x37,7 bits) || opcode === B(0x17,7 bits) || opcode === B(0x6f,7 bits))
    val useRs2 = opcode === B(0x33,7 bits) || opcode === B(0x63,7 bits) || opcode === B(0x23,7 bits)
    val hasRd = !(opcode === B(0x63,7 bits) || opcode === B(0x23,7 bits))
    val pending = Reg(Bool()) init(False)
    val count = Reg(UInt(64 bits)) init(0)
    val bufferedInsn = Reg(Bits(32 bits)); val bufferedPc = Reg(Bits(32 bits))
    val bufferedRs1 = Reg(Bits(5 bits)); val bufferedRs2 = Reg(Bits(5 bits)); val bufferedRd = Reg(Bits(5 bits))
    val bufferedA = Reg(Bits(32 bits)); val bufferedB = Reg(Bits(32 bits)); val bufferedResult = Reg(Bits(32 bits))
    valid := fire && pending
    order := count.asBits
    instruction := bufferedInsn; pcBefore := bufferedPc; pcAfter := pc
    rs1 := bufferedRs1; rs2 := bufferedRs2; rd := bufferedRd
    rs1data := bufferedA; rs2data := bufferedB; rddata := bufferedResult
    trap := False; halt := False; intr := False; mode := 3; ixl := 1
    memAddr := 0; memRmask := 0; memWmask := 0; memRdata := 0; memWdata := 0
    when(fire) {
      assert(!isMemory, "memory commits need a transaction observer")
      when(hasRd && insn(11 downto 7) =/= 0) { assert(ready, "destination write not observed at commit") }
      when(pending) { count := count + 1 }
      pending := True
      bufferedInsn := insn; bufferedPc := pc
      bufferedRs1 := Mux(useRs1,insn(19 downto 15),B(0,5 bits))
      bufferedRs2 := Mux(useRs2,insn(24 downto 20),B(0,5 bits))
      bufferedRd := Mux(hasRd,insn(11 downto 7),B(0,5 bits))
      bufferedA := Mux(useRs1 && insn(19 downto 15) =/= 0,source1,B(0,32 bits))
      bufferedB := Mux(useRs2 && insn(24 downto 20) =/= 0,source2,B(0,32 bits))
      bufferedResult := Mux(hasRd && insn(11 downto 7) =/= 0,result,B(0,32 bits))
    }
    hold.release()
  }
}

object FormalRvfi {
  def main(args: Array[String]): Unit = {
    require(args.length == 1, "provide output directory")
    val p = new ParamSimple
    p.xlen = 32
    p.addISA("m")
    p.fixIsaParams()
    SpinalConfig(targetDirectory=args(0)).generateVerilog {
      val plugins = p.plugins()
      plugins += new FormalRvfiPlugin
      ParamSimple.setPma(plugins)
      VexiiRiscv(plugins)
    }
  }
}
