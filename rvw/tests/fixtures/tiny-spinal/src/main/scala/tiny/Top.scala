package tiny

import spinal.core._

/** Small sequential RV32I test core. No CSR, interrupts, misalignment or trap handler.
  * A fixture for project integration, not a production core or ISA qualification. */
class Top extends Component {
  val valid = out Bool()
  val ready = in Bool()
  val address = out UInt(32 bits)
  val wdata = out Bits(32 bits)
  val mask = out Bits(4 bits)
  val rdata = in Bits(32 bits)
  val rvfi_valid = out(Reg(Bool()) init False)
  val rvfi_order = out(Reg(UInt(64 bits)) init 0)
  val rvfi_insn = out(Reg(Bits(32 bits)) init 0)
  val rvfi_trap = out Bool(); rvfi_trap := False
  val rvfi_halt = out Bool(); rvfi_halt := False
  val rvfi_intr = out Bool(); rvfi_intr := False
  val rvfi_mode = out UInt(2 bits); rvfi_mode := 3
  val rvfi_rs1_addr = out(Reg(UInt(5 bits)) init 0)
  val rvfi_rs2_addr = out(Reg(UInt(5 bits)) init 0)
  val rvfi_rs1_rdata = out(Reg(Bits(32 bits)) init 0)
  val rvfi_rs2_rdata = out(Reg(Bits(32 bits)) init 0)
  val rvfi_rd_addr = out(Reg(UInt(5 bits)) init 0)
  val rvfi_rd_wdata = out(Reg(Bits(32 bits)) init 0)
  val rvfi_pc_rdata = out(Reg(UInt(32 bits)) init 0)
  val rvfi_pc_wdata = out(Reg(UInt(32 bits)) init 0)
  val rvfi_mem_addr = out(Reg(UInt(32 bits)) init 0)
  val rvfi_mem_rmask = out(Reg(Bits(4 bits)) init 0)
  val rvfi_mem_wmask = out(Reg(Bits(4 bits)) init 0)
  val rvfi_mem_rdata = out(Reg(Bits(32 bits)) init 0)
  val rvfi_mem_wdata = out(Reg(Bits(32 bits)) init 0)

  val regs = Vec(Reg(Bits(32 bits)) init 0, 32)
  val pc = Reg(UInt(32 bits)) init U(0x80000000L, 32 bits)
  val insn = Reg(Bits(32 bits)) init 0
  val state = Reg(UInt(2 bits)) init 0 // fetch, decode, data, retire gap
  val order = Reg(UInt(64 bits)) init 0
  val rs1 = insn(19 downto 15).asUInt
  val rs2 = insn(24 downto 20).asUInt
  val rd = insn(11 downto 7).asUInt
  val a = Mux(rs1 === 0, B(0,32 bits), regs(rs1))
  val b = Mux(rs2 === 0, B(0,32 bits), regs(rs2))
  val immI = insn(31 downto 20).asSInt.resize(32).asBits
  val immS = (insn(31 downto 25) ## insn(11 downto 7)).asSInt.resize(32).asBits
  val immB = (insn(31) ## insn(7) ## insn(30 downto 25) ## insn(11 downto 8) ## B"0").asSInt.resize(32).asUInt
  val immJ = (insn(31) ## insn(19 downto 12) ## insn(20) ## insn(30 downto 21) ## B"0").asSInt.resize(32).asUInt
  val op = insn(6 downto 0)
  val funct = insn(14 downto 12)
  val load = op === B(0x03,7 bits)
  val store = op === B(0x23,7 bits)
  val addr = (a.asUInt + Mux(store,immS,immI).asUInt)
  val lane = addr(1 downto 0)
  val stmask = Bits(4 bits)
  stmask := B"1111"
  when(funct(1 downto 0) === B"00") { stmask := (B"0001" |<< lane).resized }
  when(funct(1 downto 0) === B"01") { stmask := (B"0011" |<< lane).resized }
  valid := state === 0 || state === 2
  address := Mux(state === 0, pc, addr)
  wdata := (b |<< (lane @@ U(0,3 bits))).resized
  mask := Mux(state === 2 && store, stmask, B"0000")
  val rhs = Mux(op === B(0x13,7 bits),immI,b)
  val shamt = rhs(4 downto 0).asUInt
  val alu = Bits(32 bits)
  alu := (a.asUInt + rhs.asUInt).asBits
  switch(funct) {
    is(B"000") { when(op === B(0x33,7 bits) && insn(30)) { alu := (a.asUInt - b.asUInt).asBits } }
    is(B"001") { alu := (a |<< shamt).resized }
    is(B"010") { alu := (a.asSInt < rhs.asSInt).asBits.resize(32) }
    is(B"011") { alu := (a.asUInt < rhs.asUInt).asBits.resize(32) }
    is(B"100") { alu := a ^ rhs }
    is(B"101") { alu := Mux(insn(30),(a.asSInt >> shamt).asBits,(a |>> shamt)) }
    is(B"110") { alu := a | rhs }
    is(B"111") { alu := a & rhs }
  }
  val take = Bool(); take := False
  switch(funct) {
    is(B"000") { take := a === b }; is(B"001") { take := a =/= b }
    is(B"100") { take := a.asSInt < b.asSInt }; is(B"101") { take := a.asSInt >= b.asSInt }
    is(B"110") { take := a.asUInt < b.asUInt }; is(B"111") { take := a.asUInt >= b.asUInt }
  }
  val next = UInt(32 bits); next := pc + 4
  when(op === B(0x63,7 bits) && take) { next := pc + immB }
  when(op === B(0x6f,7 bits)) { next := pc + immJ }
  when(op === B(0x67,7 bits)) { next := (a.asUInt + immI.asUInt) & U(0xfffffffeL,32 bits) }
  val result = Bits(32 bits); result := alu
  when(op === B(0x37,7 bits)) { result := insn(31 downto 12) ## B(0,12 bits) }
  when(op === B(0x17,7 bits)) { result := (pc + (insn(31 downto 12) ## B(0,12 bits)).asUInt).asBits }
  when(op === B(0x6f,7 bits) || op === B(0x67,7 bits)) { result := (pc+4).asBits }
  val shifted = rdata |>> (lane @@ U(0,3 bits))
  when(load) {
    result := rdata
    switch(funct) {
      is(B"000") { result := shifted(7 downto 0).asSInt.resize(32).asBits }
      is(B"001") { result := shifted(15 downto 0).asSInt.resize(32).asBits }
      is(B"100") { result := shifted(7 downto 0).resize(32) }
      is(B"101") { result := shifted(15 downto 0).resize(32) }
    }
  }
  rvfi_valid := False
  when(state === 0 && ready) { insn := rdata; state := 1 }
  when(state === 1 && (load || store)) { state := 2 }
  when((state === 1 && !(load || store)) || (state === 2 && ready)) {
    val writes = !(store || op === B(0x63,7 bits) || op === B(0x0f,7 bits)) && rd =/= 0
    when(writes) { regs(rd) := result }
    rvfi_valid := True
    rvfi_order := order; order := order + 1
    rvfi_insn := insn
    rvfi_rs1_addr := rs1; rvfi_rs2_addr := rs2
    when(op === B(0x37,7 bits) || op === B(0x17,7 bits) || op === B(0x6f,7 bits)) { rvfi_rs1_addr := 0 }
    when(!(store || op === B(0x63,7 bits) || op === B(0x33,7 bits))) { rvfi_rs2_addr := 0 }
    rvfi_rs1_rdata := a; rvfi_rs2_rdata := b
    when(op === B(0x37,7 bits) || op === B(0x17,7 bits) || op === B(0x6f,7 bits)) { rvfi_rs1_rdata := 0 }
    when(!(store || op === B(0x63,7 bits) || op === B(0x33,7 bits))) { rvfi_rs2_rdata := 0 }
    rvfi_rd_addr := Mux(writes,rd,U(0,5 bits)); rvfi_rd_wdata := Mux(writes,result,B(0,32 bits))
    rvfi_pc_rdata := pc; rvfi_pc_wdata := next
    rvfi_mem_addr := addr & U(0xfffffffcL,32 bits)
    rvfi_mem_rmask := Mux(load,stmask,B"0000"); rvfi_mem_wmask := Mux(store,stmask,B"0000")
    rvfi_mem_rdata := rdata; rvfi_mem_wdata := wdata
    pc := next; state := 3
  }
  when(state === 3) { state := 0 }
}
