package rvwvexii

import spinal.core._
import spinal.lib._
import spinal.lib.misc.plugin.FiberPlugin
import vexiiriscv.{Global, VexiiRiscv, ParamSimple}
import vexiiriscv.decode.Decode
import vexiiriscv.execute._
import vexiiriscv.misc.{PipelineBuilderPlugin, TrapPlugin, PrivilegedPlugin}
import vexiiriscv.regfile.RegFileWriterService
import vexiiriscv.test.WhiteboxerPlugin
import vexiiriscv.riscv.{IntRegFile, RS1, RS2}

/** Hardware-only observer for the single-lane cacheless profiles.
  * Commit or trap boundaries supply the preceding instruction's next PC.
  * Tagged observations retain register and memory results until emission. */
class FormalRvfiPlugin extends FiberPlugin {
  val logic = during setup new Area {
    val hold = retains(host[PipelineBuilderPlugin].elaborationLock)
    awaitBuild()
    val xlen = vexiiriscv.riscv.Riscv.XLEN.get
    val maskWidth = xlen / 8
    val lanes = host.list[ExecuteLaneService]
    require(lanes.size == 1, "formal observer supports one execute lane")
    val lane = lanes.head
    val c = lane.execute(host[TrapPlugin].trapAt)
    val fire = c.down.isFiring && c.down(Global.COMMIT)
    val id = c(Decode.UOP_ID)
    val insn = c(Decode.UOP).asBits.resize(32)
    val pc = Global.expendPc(c(Global.PC), xlen).asBits
    val source1 = c(lane(IntRegFile, RS1))
    val source2 = c(lane(IntRegFile, RS2))
    val writers = host.list[RegFileWriterService].flatMap(_.getRegFileWriters()).filter(_.payload.rfSpec == IntRegFile)
    val values = Vec.fill(64)(Reg(Bits(xlen bits)))
    val tags = Vec.fill(64)(Reg(UInt(Decode.UOP_ID_WIDTH bits)))
    val written = Vec.fill(values.size)(Reg(Bool()) init(False))
    // Clear on dispatch so a recycled micro-op ID cannot retain an old write.
    val dispatch = lane.ctrl(0)
    when(dispatch.down.transactionSpawn) { written(dispatch(Decode.UOP_ID).resize(6)) := False }
    for(w <- writers) when(w.valid) { values(w.uopId.resize(6)) := w.data; tags(w.uopId.resize(6)) := w.uopId; written(w.uopId.resize(6)) := True }
    // Memory observations are keyed by the full micro-op ID. The low bits
    // select storage only. Tags prevent reuse from selecting an older access.
    val wb = host[WhiteboxerPlugin].logic
    wb.await()
    val memTags = Vec.fill(64)(Reg(UInt(Decode.UOP_ID_WIDTH bits)))
    val memKnown = Vec.fill(64)(Reg(Bool()) init(False))
    val addresses = Vec.fill(64)(Reg(Bits(xlen bits)))
    val readData = Vec.fill(64)(Reg(Bits(xlen bits)))
    val writeData = Vec.fill(64)(Reg(Bits(xlen bits)))
    val readMasks = Vec.fill(64)(Reg(Bits(maskWidth bits)))
    val writeMasks = Vec.fill(64)(Reg(Bits(maskWidth bits)))
    when(dispatch.down.transactionSpawn) { memKnown(dispatch(Decode.UOP_ID).resize(6)) := False }
    val load = wb.loadExecute
    val store = wb.storeCommit
    when(load.fire) {
      val slot = load.uopId.resize(6)
      memKnown(slot) := True; memTags(slot) := load.uopId
      addresses(slot) := load.address.asBits.resize(xlen)
      readData(slot) := load.data.resize(xlen); writeData(slot) := B(0,xlen bits)
      readMasks(slot) := ((U(1,maskWidth+1 bits) |<< (U(1,4 bits) |<< load.size)).resize(maskWidth)-1).asBits
      writeMasks(slot) := B(0,maskWidth bits)
    }
    when(store.fire) {
      val slot = store.uopId.resize(6)
      memKnown(slot) := True; memTags(slot) := store.uopId
      addresses(slot) := store.address.asBits.resize(xlen)
      writeData(slot) := store.data.resize(xlen); readData(slot) := B(0,xlen bits)
      writeMasks(slot) := ((U(1,maskWidth+1 bits) |<< (U(1,4 bits) |<< store.size)).resize(maskWidth)-1).asBits
      readMasks(slot) := B(0,maskWidth bits)
    }

    def output(width: Int, name: String) = out(Bits(width bits)).setName("rvfi_" + name)
    val valid = out(Bool()).setName("rvfi_valid")
    val order = output(64,"order")
    val instruction = output(32,"insn")
    val trap = out(Bool()).setName("rvfi_trap")
    val halt = out(Bool()).setName("rvfi_halt")
    val intr = out(Bool()).setName("rvfi_intr")
    val mode = output(2,"mode"); val ixl = output(2,"ixl")
    val rs1 = output(5,"rs1_addr"); val rs2 = output(5,"rs2_addr"); val rd = output(5,"rd_addr")
    val rs1data = output(xlen,"rs1_rdata"); val rs2data = output(xlen,"rs2_rdata"); val rddata = output(xlen,"rd_wdata")
    val pcBefore = output(xlen,"pc_rdata"); val pcAfter = output(xlen,"pc_wdata")
    val memAddr = output(xlen,"mem_addr"); val memRmask = output(maskWidth,"mem_rmask"); val memWmask = output(maskWidth,"mem_wmask")
    val memRdata = output(xlen,"mem_rdata"); val memWdata = output(xlen,"mem_wdata")
    // Classify architectural operands. CSR immediates are not register reads.
    val opcode = insn(6 downto 0)
    val isMemory = opcode === B(0x03,7 bits) || opcode === B(0x23,7 bits)
    val csrRegister = opcode === B(0x73,7 bits) && insn(14 downto 12) =/= 0 && !insn(14)
    val useRs1 = opcode === B(0x03,7 bits) || opcode === B(0x23,7 bits) || opcode === B(0x13,7 bits) || opcode === B(0x1b,7 bits) || opcode === B(0x33,7 bits) || opcode === B(0x3b,7 bits) || opcode === B(0x63,7 bits) || opcode === B(0x67,7 bits) || csrRegister
    val useRs2 = opcode === B(0x33,7 bits) || opcode === B(0x3b,7 bits) || opcode === B(0x63,7 bits) || opcode === B(0x23,7 bits)
    val hasRd = opcode === B(0x37,7 bits) || opcode === B(0x17,7 bits) || opcode === B(0x6f,7 bits) || opcode === B(0x67,7 bits) || opcode === B(0x03,7 bits) || opcode === B(0x13,7 bits) || opcode === B(0x1b,7 bits) || opcode === B(0x33,7 bits) || opcode === B(0x3b,7 bits) || (opcode === B(0x73,7 bits) && insn(14 downto 12) =/= 0)
    val pending = Reg(Bool()) init(False)
    val bufferedId = Reg(UInt(Decode.UOP_ID_WIDTH bits))
    val bufferedMemory = Reg(Bool())
    val bufferedIntr = Reg(Bool())
    val bufferedMode = Reg(Bits(2 bits))
    val currentMode = host[PrivilegedPlugin].logic.harts(0).privilege.asBits.resize(2)
    val handler = Reg(Bool()) init(False)
    val trapState = host[TrapPlugin].logic.harts(0).trap
    val trapEvent = trapState.whitebox.trap
    // A trap ends the preceding normal PC chain at xepc. It must not splice
    // the preceding instruction to the first handler instruction.
    val boundary = fire || trapEvent
    when(trapEvent) { handler := True; pending := False }
    // This core issues its trap redirect before the architectural trap pulse.
    val lastTrapTarget = Reg(Bits(xlen bits))
    val trapTargetKnown = Reg(Bool()) init(False)
    when(trapState.pcPort.valid) {
      lastTrapTarget := Global.expendPc(trapState.pcPort.pc, xlen).asBits
      trapTargetKnown := True
    }
    val faultTarget = Reg(Bits(xlen bits))
    val faultKnown = Reg(Bool()) init(False)
    val faultMode = Reg(Bits(2 bits))
    val faultWaiting = Reg(Bool()) init(False)
    val faultInsn = Reg(Bits(32 bits)); val faultPc = Reg(Bits(xlen bits))
    val faultA = Reg(Bits(xlen bits)); val faultB = Reg(Bits(xlen bits))
    val faultRs1 = Reg(Bits(5 bits)); val faultRs2 = Reg(Bits(5 bits))
    when(c.down.isFiring && c(Global.TRAP)) {
      when(!trapState.pcPort.valid) { trapTargetKnown := False }
      faultKnown := True; faultInsn := insn; faultPc := pc; faultMode := currentMode
      faultRs1 := Mux(useRs1,insn(19 downto 15),B(0,5 bits))
      faultRs2 := Mux(useRs2,insn(24 downto 20),B(0,5 bits))
      faultA := Mux(useRs1 && insn(19 downto 15) =/= 0,source1,B(0,xlen bits))
      faultB := Mux(useRs2 && insn(24 downto 20) =/= 0,source2,B(0,xlen bits))
    }
    when(trapEvent && !trapState.whitebox.interrupt) {
      assert(faultKnown && faultPc === Global.expendPc(trapState.pending.pc, xlen).asBits, "fault instruction is not aligned to xepc")
      assert(!faultWaiting, "fault completion slot overflow")
      assert(trapTargetKnown || trapState.pcPort.valid, "trap redirect target is not observed")
      faultTarget := Mux(trapState.pcPort.valid,Global.expendPc(trapState.pcPort.pc, xlen).asBits,lastTrapTarget)
      faultWaiting := True
    }
    val faultEmit = faultWaiting

    val count = Reg(UInt(64 bits)) init(0)
    val bufferedInsn = Reg(Bits(32 bits)); val bufferedPc = Reg(Bits(xlen bits))
    val bufferedRs1 = Reg(Bits(5 bits)); val bufferedRs2 = Reg(Bits(5 bits)); val bufferedRd = Reg(Bits(5 bits))
    val bufferedA = Reg(Bits(xlen bits)); val bufferedB = Reg(Bits(xlen bits))
    val bufferedSlot = bufferedId.resize(6)
    val completedResult = Bits(xlen bits)
    val completedKnown = Bool()
    completedResult := values(bufferedSlot)
    completedKnown := written(bufferedSlot) && tags(bufferedSlot) === bufferedId
    for(w <- writers) when(w.valid && w.uopId === bufferedId) { completedResult := w.data; completedKnown := True }
    valid := (boundary && pending) || faultEmit
    order := count.asBits
    instruction := bufferedInsn; pcBefore := bufferedPc; pcAfter := Mux(trapEvent,Global.expendPc(trapState.pending.pc, xlen).asBits,pc)
    rs1 := bufferedRs1; rs2 := bufferedRs2; rd := bufferedRd
    rs1data := bufferedA; rs2data := bufferedB; rddata := Mux(bufferedRd =/= 0,completedResult,B(0,xlen bits))
    trap := False; halt := False; intr := bufferedIntr; mode := bufferedMode; ixl := (if(xlen == 64) 2 else 1)
    memAddr := 0; memRmask := 0; memWmask := 0; memRdata := 0; memWdata := 0
    val completedMemoryKnown = Bool()
    completedMemoryKnown := memKnown(bufferedSlot) && memTags(bufferedSlot) === bufferedId
    when(valid) { count := count + 1 }
    when(boundary && pending) {
      when(bufferedRd =/= 0) { assert(completedKnown, "destination write not observed at emission") }
      when(bufferedMemory) {
        assert(completedMemoryKnown, "retired memory effect not observed")
      }
    }
    when(bufferedMemory) {
      memAddr := addresses(bufferedSlot)
      memRmask := readMasks(bufferedSlot); memWmask := writeMasks(bufferedSlot)
      memRdata := readData(bufferedSlot); memWdata := writeData(bufferedSlot)
    }
    when(bufferedMemory && load.fire && load.uopId === bufferedId) {
      completedMemoryKnown := True
      memAddr := load.address.asBits.resize(xlen)
      memRdata := load.data.resize(xlen); memWdata := 0
      memRmask := ((U(1,maskWidth+1 bits) |<< (U(1,4 bits) |<< load.size)).resize(maskWidth)-1).asBits
      memWmask := 0
    }
    when(bufferedMemory && store.fire && store.uopId === bufferedId) {
      completedMemoryKnown := True
      memAddr := store.address.asBits.resize(xlen)
      memWdata := store.data.resize(xlen); memRdata := 0
      memWmask := ((U(1,maskWidth+1 bits) |<< (U(1,4 bits) |<< store.size)).resize(maskWidth)-1).asBits
      memRmask := 0
    }
    when(faultEmit) {
      assert(!(boundary && pending), "normal and fault completions collide")
      faultWaiting := False; faultKnown := False
      instruction := faultInsn; pcBefore := faultPc
      pcAfter := faultTarget
      trap := True; intr := False; mode := faultMode
      rs1 := faultRs1; rs2 := faultRs2; rs1data := faultA; rs2data := faultB
      rd := 0; rddata := 0
      memAddr := 0; memRmask := 0; memWmask := 0; memRdata := 0; memWdata := 0
    }
    when(fire) {
      assert(!trapEvent, "commit and trap boundary need ordered completion")
      bufferedId := id; bufferedMemory := isMemory
      bufferedIntr := handler; bufferedMode := currentMode; handler := False
      pending := True
      bufferedInsn := insn; bufferedPc := pc
      bufferedRs1 := Mux(useRs1,insn(19 downto 15),B(0,5 bits))
      bufferedRs2 := Mux(useRs2,insn(24 downto 20),B(0,5 bits))
      bufferedRd := Mux(hasRd,insn(11 downto 7),B(0,5 bits))
      bufferedA := Mux(useRs1 && insn(19 downto 15) =/= 0,source1,B(0,xlen bits))
      bufferedB := Mux(useRs2 && insn(24 downto 20) =/= 0,source2,B(0,xlen bits))
    }
    hold.release()
  }
}

object FormalRvfi {
  def main(args: Array[String]): Unit = {
    require(args.length >= 1 && args.length <= 2, "provide output directory and optional config")
    val p = VexiiTop.param(if(args.length == 2) args(1) else "rv32im")
    SpinalConfig(targetDirectory=args(0)).generateVerilog {
      val plugins = p.plugins()
      if(!plugins.exists(_.isInstanceOf[WhiteboxerPlugin])) plugins += new WhiteboxerPlugin(false)
      plugins += new FormalRvfiPlugin
      ParamSimple.setPma(plugins)
      VexiiRiscv(plugins)
    }
  }
}
