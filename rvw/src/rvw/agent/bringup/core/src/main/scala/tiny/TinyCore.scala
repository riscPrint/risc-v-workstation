package tiny

import spinal.core._

/** A tiny multi-cycle RV32I core (no CSRs, no traps) with one memory port and RVFI outputs.
  * Memory: the core drives `mem_valid` with `mem_addr`; read data arrives in `mem_rdata` the
  * next cycle. A store drives `mem_we` and `mem_wmask` for one cycle. Reset PC 0x80000000. */
class TinyCore extends Component {
  val resetPc = 0x80000000L
  val io = new Bundle {
    val mem_valid = out Bool()
    val mem_we = out Bool()
    val mem_addr = out UInt(32 bits)
    val mem_wdata = out Bits(32 bits)
    val mem_wmask = out Bits(4 bits)
    val mem_rdata = in Bits(32 bits)
    val rvfi_valid = out Bool()
    val rvfi_order = out UInt(64 bits)
    val rvfi_insn = out Bits(32 bits)
    val rvfi_pc_rdata, rvfi_pc_wdata = out UInt(32 bits)
    val rvfi_rs1_addr, rvfi_rs2_addr, rvfi_rd_addr = out UInt(5 bits)
    val rvfi_rs1_rdata, rvfi_rs2_rdata, rvfi_rd_wdata = out Bits(32 bits)
    val rvfi_mem_addr = out UInt(32 bits)
    val rvfi_mem_rmask, rvfi_mem_wmask = out Bits(4 bits)
    val rvfi_mem_rdata, rvfi_mem_wdata = out Bits(32 bits)
    val rvfi_trap = out Bool()
  }
  val regs = Vec.fill(32)(Reg(Bits(32 bits)) init(0))
  val pc = Reg(UInt(32 bits)) init(resetPc)
  val insn = Reg(Bits(32 bits)) init(0)
  val order = Reg(UInt(64 bits)) init(0)
  val state = Reg(UInt(2 bits)) init(0) // 0 fetch, 1 execute, 2 load request, 3 load write-back
  val loadAddr = Reg(UInt(32 bits)) init(0)

  val i = Mux(state === 1, io.mem_rdata, insn)
  val opcode = i(6 downto 0)
  val rd = i(11 downto 7).asUInt
  val f3 = i(14 downto 12)
  val rs1 = i(19 downto 15).asUInt
  val rs2 = i(24 downto 20).asUInt
  val f7 = i(31 downto 25)
  val a = Mux(rs1 === 0, B(0, 32 bits), regs(rs1))
  val b = Mux(rs2 === 0, B(0, 32 bits), regs(rs2))
  val immI = S(i(31 downto 20)).resize(32).asBits
  val immS = S(i(31 downto 25) ## i(11 downto 7)).resize(32).asBits
  val immB = S(i(31) ## i(7) ## i(30 downto 25) ## i(11 downto 8) ## B"0").resize(32).asBits
  val immU = i(31 downto 12) ## B(0, 12 bits)
  val immJ = S(i(31) ## i(19 downto 12) ## i(20) ## i(30 downto 21) ## B"0").resize(32).asBits

  def alu(x: Bits, y: Bits, op: Bits, alt: Bool, isOp: Boolean): Bits = {
    val r = Bits(32 bits)
    switch(op) {
      is(0) { if (isOp) r := Mux(alt, (x.asUInt - y.asUInt).asBits, (x.asUInt + y.asUInt).asBits)
              else r := (x.asUInt + y.asUInt).asBits }
      is(1) { r := (x |<< y(4 downto 0).asUInt) }
      is(2) { r := B(x.asSInt < y.asSInt).resize(32) }
      is(3) { r := B(x.asUInt < y.asUInt).resize(32) }
      is(4) { r := x ^ y }
      is(5) { r := Mux(alt, (x.asSInt >> y(4 downto 0).asUInt).asBits, x |>> y(4 downto 0).asUInt) }
      is(6) { r := x | y }
      default { r := x & y }
    }
    r
  }

  io.mem_valid := False; io.mem_we := False; io.mem_addr := pc; io.mem_wdata := 0; io.mem_wmask := 0
  io.rvfi_valid := False; io.rvfi_order := order; io.rvfi_insn := i; io.rvfi_pc_rdata := pc; io.rvfi_pc_wdata := pc + 4
  io.rvfi_rs1_rdata := a; io.rvfi_rs2_rdata := b
  io.rvfi_rd_addr := 0; io.rvfi_rd_wdata := 0; io.rvfi_mem_addr := 0; io.rvfi_mem_rmask := 0; io.rvfi_mem_wmask := 0
  io.rvfi_mem_rdata := 0; io.rvfi_mem_wdata := 0; io.rvfi_trap := False

  val result = Bits(32 bits); result := 0
  val writes = Bool(); writes := False
  val nextPc = pc + 4
  def retire(): Unit = { io.rvfi_valid := True; order := order + 1; state := 0 }

  switch(state) {
    is(0) { io.mem_valid := True; io.mem_addr := pc; state := 1 }
    is(1) {
      insn := io.mem_rdata
      val target = UInt(32 bits); target := pc + 4
      switch(opcode) {
        is(B"0110111") { result := immU; writes := True }
        is(B"0010111") { result := (pc + immU.asUInt).asBits; writes := True }
        is(B"1101111") { result := (pc + 4).asBits; writes := True; target := pc + immJ.asUInt }
        is(B"1100111") { result := (pc + 4).asBits; writes := True; target := ((a.asUInt + immI.asUInt) & U"xFFFFFFFE") }
        is(B"1100011") {
          val taken = f3.mux(0 -> (a === b), 1 -> (a =/= b), 4 -> (a.asSInt < b.asSInt), 5 -> (a.asSInt >= b.asSInt),
            6 -> (a.asUInt < b.asUInt), 7 -> (a.asUInt >= b.asUInt), default -> False)
          when(taken) { target := pc + immB.asUInt }
        }
        is(B"0010011") { result := alu(a, immI, f3, f3 === 5 && f7(5), isOp = false); writes := True }
        is(B"0110011") { result := alu(a, b, f3, f7(5), isOp = true); writes := True }
        is(B"0000011") { loadAddr := (a.asUInt + immI.asUInt); state := 2 }
        is(B"0100011") {
          val addr = a.asUInt + immS.asUInt
          val lanes = f3.mux(0 -> B"0001", 1 -> B"0011", default -> B"1111") |<< addr(1 downto 0)
          val data = f3.mux(0 -> b(7 downto 0) ## b(7 downto 0) ## b(7 downto 0) ## b(7 downto 0),
            1 -> b(15 downto 0) ## b(15 downto 0), default -> b)
          io.mem_valid := True; io.mem_we := True; io.mem_addr := addr(31 downto 2) @@ U"00"
          io.mem_wdata := data; io.mem_wmask := lanes
          io.rvfi_mem_addr := addr(31 downto 2) @@ U"00"; io.rvfi_mem_wmask := lanes; io.rvfi_mem_wdata := data
        }
        default { io.rvfi_trap := True }
      }
      when(opcode =/= B"0000011") {
        when(writes && rd =/= 0) { regs(rd) := result }
        io.rvfi_rd_addr := Mux(writes, rd, U(0)); io.rvfi_rd_wdata := Mux(writes && rd =/= 0, result, B(0))
        io.rvfi_pc_wdata := target; pc := target
        retire()
      }
    }
    is(2) { io.mem_valid := True; io.mem_addr := loadAddr(31 downto 2) @@ U"00"; state := 3 }
    is(3) {
      val shifted = io.mem_rdata |>> (loadAddr(1 downto 0) @@ U"000")
      val value = f3.mux(0 -> S(shifted(7 downto 0)).resize(32).asBits, 1 -> S(shifted(15 downto 0)).resize(32).asBits,
        4 -> shifted(7 downto 0).resize(32), 5 -> shifted(15 downto 0).resize(32), default -> shifted)
      when(rd =/= 0) { regs(rd) := value }
      io.rvfi_rd_addr := rd; io.rvfi_rd_wdata := Mux(rd =/= 0, value, B(0))
      io.rvfi_mem_addr := loadAddr(31 downto 2) @@ U"00"; io.rvfi_mem_rdata := io.mem_rdata
      io.rvfi_mem_rmask := f3.mux(0 -> B"0001", 1 -> B"0011", 4 -> B"0001", 5 -> B"0011", default -> B"1111") |<< loadAddr(1 downto 0)
      io.rvfi_pc_wdata := pc + 4; pc := pc + 4
      retire()
    }
  }
  io.rvfi_rs2_addr := Mux(opcode === B"0110011" || opcode === B"1100011" || opcode === B"0100011", rs2, U(0))
  io.rvfi_rs1_addr := Mux(opcode === B"0110111" || opcode === B"0010111" || opcode === B"1101111", U(0), rs1)
}

object TinyCore {
  def main(args: Array[String]): Unit = SpinalVerilog(new TinyCore)
}
