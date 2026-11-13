package rvwvexii

import spinal.core._
import spinal.core.sim._
import spinal.lib.misc.plugin.FiberPlugin
import vexiiriscv.{Global}
import vexiiriscv.decode.{Decode, DecodePipelinePlugin, DecoderPlugin}
import vexiiriscv.execute._
import vexiiriscv.misc.{PipelineBuilderPlugin, PrivilegedPlugin, TrapPlugin}
import vexiiriscv.regfile.RegFileWriterService
import vexiiriscv.riscv.{IntRegFile, RS1, RS2}

/** Passive single-lane observer. Its pending retirement and write tags are RTL
  * state, so the bridge restores them with the core. The host supplies memory
  * effects from the accepted native bus commands, keyed by the full uop ID. */
class BootTraceTap extends FiberPlugin {
  val logic = during setup new Area {
    val hold = retains(host[PipelineBuilderPlugin].elaborationLock)
    awaitBuild()
    val xlen = vexiiriscv.riscv.Riscv.XLEN.get
    val lanes = host.list[ExecuteLaneService]
    require(lanes.size == 1, "boot trace supports one execute lane")
    val lane = lanes.head
    val c = lane.execute(host[TrapPlugin].trapAt)
    val commit = c.down.isFiring && c.down(Global.COMMIT)
    val id = c(Decode.UOP_ID)
    val expanded = c(Decode.UOP).asBits.resize(32)
    // Dispatch does not carry the pre-decompression instruction. Keep it by
    // full uop tag from decode until retirement instead of reconstructing it.
    val decoded = host[DecodePipelinePlugin].ctrl(host[DecoderPlugin].decodeAt).lane(0)
    val rawWords = Vec.fill(64)(Reg(Bits(32 bits)))
    val rawTags = Vec.fill(64)(Reg(UInt(Decode.UOP_ID_WIDTH bits)))
    when(decoded.up.transactionSpawn) {
      rawWords(decoded(Decode.UOP_ID).resize(6)) := decoded(Decode.INSTRUCTION_RAW).asBits.resize(32)
      rawTags(decoded(Decode.UOP_ID).resize(6)) := decoded(Decode.UOP_ID)
    }
    val raw = rawWords(id.resize(6))
    val instruction = Mux(raw(1 downto 0) === B(3,2 bits), raw, raw(15 downto 0).resize(32))
    val pc = Global.expendPc(c(Global.PC), xlen).asBits
    val source1 = c(lane(IntRegFile, RS1))
    val source2 = c(lane(IntRegFile, RS2))
    val opcode = expanded(6 downto 0)
    val csrRegister = opcode === B(0x73,7 bits) && expanded(14 downto 12) =/= 0 && !expanded(14)
    val use1 = opcode === B(0x03,7 bits) || opcode === B(0x23,7 bits) || opcode === B(0x2f,7 bits) ||
      opcode === B(0x13,7 bits) || opcode === B(0x1b,7 bits) || opcode === B(0x33,7 bits) ||
      opcode === B(0x3b,7 bits) || opcode === B(0x63,7 bits) || opcode === B(0x67,7 bits) || csrRegister
    val use2 = opcode === B(0x33,7 bits) || opcode === B(0x3b,7 bits) || opcode === B(0x63,7 bits) ||
      opcode === B(0x23,7 bits) || opcode === B(0x2f,7 bits)
    val hasRd = opcode === B(0x37,7 bits) || opcode === B(0x17,7 bits) || opcode === B(0x6f,7 bits) ||
      opcode === B(0x67,7 bits) || opcode === B(0x03,7 bits) || opcode === B(0x2f,7 bits) ||
      opcode === B(0x13,7 bits) || opcode === B(0x1b,7 bits) || opcode === B(0x33,7 bits) ||
      opcode === B(0x3b,7 bits) || (opcode === B(0x73,7 bits) && expanded(14 downto 12) =/= 0)
    val memory = opcode === B(0x03,7 bits) || opcode === B(0x23,7 bits) || opcode === B(0x2f,7 bits)
    val writers = host.list[RegFileWriterService].flatMap(_.getRegFileWriters()).filter(_.payload.rfSpec == IntRegFile)
    val values = Vec.fill(64)(Reg(Bits(xlen bits)))
    val tags = Vec.fill(64)(Reg(UInt(Decode.UOP_ID_WIDTH bits)))
    val known = Vec.fill(64)(RegInit(False))
    val dispatch = lane.ctrl(0)
    when(dispatch.down.transactionSpawn) { known(dispatch(Decode.UOP_ID).resize(6)) := False }
    for (w <- writers) when(w.valid) {
      values(w.uopId.resize(6)) := w.data; tags(w.uopId.resize(6)) := w.uopId; known(w.uopId.resize(6)) := True
    }
    val cycles = Reg(UInt(64 bits)) init(0)
    cycles := cycles + 1
    val pending = RegInit(False)
    val pendingId = Reg(UInt(Decode.UOP_ID_WIDTH bits))
    val pendingOrder = Reg(UInt(64 bits))
    val pendingCycle = Reg(UInt(64 bits))
    val pendingInsn = Reg(Bits(32 bits))
    val pendingPc = Reg(Bits(xlen bits))
    val pendingA, pendingB = Reg(Bits(xlen bits))
    val pendingAddress = Reg(Bits(xlen bits))
    val lsu = host[vexiiriscv.execute.lsu.LsuCachelessPlugin].logic
    val pendingRs1, pendingRs2, pendingRd = Reg(Bits(5 bits))
    val pendingMode = Reg(Bits(2 bits))
    val pendingMemory, pendingIntr = Reg(Bool())
    val handler = RegInit(False)
    val trap = host[TrapPlugin].logic.harts(0).trap
    val trapEvent = trap.whitebox.trap
    val boundary = commit || trapEvent
    val result = Bits(xlen bits)
    val resultKnown = Bool()
    result := values(pendingId.resize(6))
    resultKnown := known(pendingId.resize(6)) && tags(pendingId.resize(6)) === pendingId
    for (w <- writers) when(w.valid && w.uopId === pendingId) { result := w.data; resultKnown := True }
    val count = Reg(UInt(64 bits)) init(0)
    val port = out(new Bundle {
      val valid = Bool()
      val order = Bits(64 bits)
      val insn = Bits(32 bits)
      val trap, halt, intr = Bool()
      val mode, ixl = Bits(2 bits)
      val rs1_addr, rs2_addr, rd_addr = Bits(5 bits)
      val rs1_rdata, rs2_rdata, rd_wdata = Bits(xlen bits)
      val pc_rdata, pc_wdata = Bits(xlen bits)
      val mem_addr, mem_rdata, mem_wdata = Bits(xlen bits)
      val mem_rmask, mem_wmask = Bits(xlen/8 bits)
      val mem_fault = Bool()
      val uop_id = UInt(Decode.UOP_ID_WIDTH bits)
      val record_cycle = UInt(64 bits)
      val retired_count = UInt(64 bits)
      val needs_memory, result_known, raw_known, counter_input, overlap = Bool()
    }).setName("rvw_boot_trace").simPublic()
    port.valid := pending && boundary
    port.order := pendingOrder.asBits; port.insn := pendingInsn
    port.trap := False; port.halt := False; port.intr := pendingIntr
    port.mode := pendingMode; port.ixl := (if (xlen == 64) 2 else 1)
    port.rs1_addr := pendingRs1; port.rs2_addr := pendingRs2; port.rd_addr := pendingRd
    port.rs1_rdata := pendingA; port.rs2_rdata := pendingB
    port.rd_wdata := Mux(pendingRd =/= 0, result, B(0,xlen bits))
    port.pc_rdata := pendingPc
    port.pc_wdata := Mux(trapEvent, Global.expendPc(trap.pending.pc,xlen).asBits, pc)
    port.mem_addr := Mux(pendingMemory, pendingAddress, B(0,xlen bits)); port.mem_rdata := 0; port.mem_wdata := 0
    port.mem_rmask := 0; port.mem_wmask := 0; port.mem_fault := False
    port.uop_id := pendingId; port.record_cycle := pendingCycle; port.needs_memory := pendingMemory
    port.retired_count := count
    val csr = pendingInsn(31 downto 20).asUInt
    port.counter_input := pendingRd =/= 0 && pendingInsn(6 downto 0) === B(0x73,7 bits) &&
      pendingInsn(13) && pendingInsn(19 downto 15) === 0 &&
      ((csr & U(0xf60,12 bits)) === U(0xc00,12 bits) || (csr & U(0xf60,12 bits)) === U(0xb00,12 bits))
    port.result_known := resultKnown
    val pendingRawKnown = Reg(Bool())
    port.raw_known := pendingRawKnown
    port.overlap := commit && trapEvent
    when(commit) {
      count := count + 1; pendingOrder := count
      pending := True; pendingId := id; pendingCycle := cycles
      pendingInsn := instruction; pendingPc := pc
      pendingRawKnown := rawTags(id.resize(6)) === id
      pendingRs1 := Mux(use1, expanded(19 downto 15), B(0,5 bits))
      pendingRs2 := Mux(use2, expanded(24 downto 20), B(0,5 bits))
      pendingRd := Mux(hasRd, expanded(11 downto 7), B(0,5 bits))
      pendingA := Mux(use1 && expanded(19 downto 15) =/= 0, source1, B(0,xlen bits))
      pendingB := Mux(use2 && expanded(24 downto 20) =/= 0, source2, B(0,xlen bits))
      pendingMode := host[PrivilegedPlugin].logic.harts(0).privilege.asBits.resize(2)
      pendingAddress := c(lsu.onAddress.RAW_ADDRESS).asBits.resize(xlen)
      pendingMemory := memory; pendingIntr := handler; handler := False
    }
    when(trapEvent) { pending := False; handler := True }
    hold.release()
  }
}

/** Elaboration control for the simulation-only observer. */
object BootTraceElaborate {
  def main(args: Array[String]): Unit = {
    require(args.length == 1, "output directory required")
    VexiiTop.spinalConfig.copy(targetDirectory=args(0)).generateVerilog {
      val plugins = VexiiTop.param("rv64imacsu_linux").plugins()
      plugins += new TrapTapPlugin
      plugins += new BootTraceTap
      vexiiriscv.ParamSimple.setPma(plugins)
      vexiiriscv.VexiiRiscv(plugins)
    }
  }
}
