package example
import spinal.core._
import spinal.lib._
import spinal.lib.bus.amba3.apb._
import rvwsoc.CoreWrapper

/** Tiny RV32 bus exerciser. Supports LUI, ADDI, LW, SW, JAL, CSRRW and MRET.
  * This is a verification stub, not a production or ISA-qualified CPU.
  */
class Stub extends Component with CoreWrapper {
  val io = new Bundle {
    val bus = master(Apb3(Apb3Config(32,32)))
    val interrupts = in Bits(32 bits)
    val debugReset = in Bool()
    val fault = out Bool()
    val retired = out UInt(32 bits)
  }
  def bus = io.bus
  def interrupts = io.interrupts
  def debugReset = io.debugReset
  val regs = Vec.fill(32)(Reg(Bits(32 bits)) init(0))
  val pc = Reg(UInt(32 bits)) init(U(0x80000000L,32 bits))
  val instruction = Reg(Bits(32 bits)) init(0)
  val state = Reg(UInt(3 bits)) init(0)
  val addr = Reg(UInt(32 bits)) init(0)
  val data = Reg(Bits(32 bits)) init(0)
  val load = Reg(Bool()) init(False)
  val dest = Reg(UInt(5 bits)) init(0)
  val fault = Reg(Bool()) init(False)
  val retired = Reg(UInt(32 bits)) init(0)
  val mtvec = Reg(UInt(32 bits)) init(0)
  val mepc = Reg(UInt(32 bits)) init(0)
  val mie = Reg(Bits(32 bits)) init(0)
  val mstatus = Reg(Bits(32 bits)) init(0)
  val mcause = Reg(Bits(32 bits)) init(0)
  val rd = instruction(11 downto 7).asUInt
  val rs1 = regs(instruction(19 downto 15).asUInt)
  val rs2 = regs(instruction(24 downto 20).asUInt)
  regs(0) := 0
  io.fault := fault
  io.retired := retired
  io.bus.PADDR := Mux(state <= 1,pc,addr)
  io.bus.PSEL := B(1,1 bits)
  io.bus.PENABLE := state === 1 || state === 4
  io.bus.PWRITE := state >= 3 && !load
  io.bus.PWDATA := data
  when(state === 2 || fault) { io.bus.PSEL := 0 }
  switch(state) {
    is(0) {
      when(mstatus(3) && (mie & io.interrupts).orR) {
        mepc := pc
        pc := mtvec
        mstatus(3) := False
        mcause := B(0x80000007L,32 bits)
        when(mie(11) && io.interrupts(11)) { mcause := B(0x8000000bL,32 bits) }
      }.otherwise { state := 1 }
    }
    is(1) {
      when(io.bus.PREADY) {
        instruction := io.bus.PRDATA
        fault := io.bus.PSLVERROR
        state := 2
      }
    }
    is(2) {
      val imm = instruction(31 downto 20).asSInt.resize(32).asBits
      state := 0
      pc := pc + 4
      retired := retired + 1
      switch(instruction(6 downto 0)) {
        is(B"0110111") { when(rd =/= 0) { regs(rd) := instruction(31 downto 12) ## B(0,12 bits) } }
        is(B"0010011") {
          when(instruction(14 downto 12) === 0) { when(rd =/= 0) { regs(rd) := (rs1.asUInt + imm.asUInt).asBits } }
            .otherwise { fault := True }
        }
        is(B"0000011", B"0100011") {
          load := !instruction(5)
          val storeImm = (instruction(31 downto 25) ## instruction(11 downto 7)).asSInt.resize(32).asUInt
          addr := rs1.asUInt + Mux(instruction(5),storeImm,imm.asUInt)
          data := rs2
          dest := rd
          state := 3
          retired := retired
          when(instruction(14 downto 12) =/= 2) { fault := True }
        }
        is(B"1101111") {
          val jump = (instruction(31) ## instruction(19 downto 12) ## instruction(20) ## instruction(30 downto 21) ## False).asSInt.resize(32).asUInt
          when(rd =/= 0) { regs(rd) := (pc+4).asBits }
          pc := pc + jump
        }
        is(B"1110011") {
          when(instruction === B(0x30200073L,32 bits)) { pc := mepc; mstatus(3) := True }
          .elsewhen(instruction(14 downto 12) === 1) {
            switch(instruction(31 downto 20)) {
              is(0x300) { when(rd =/= 0) { regs(rd) := mstatus }; mstatus := rs1 }
              is(0x304) { when(rd =/= 0) { regs(rd) := mie }; mie := rs1 }
              is(0x305) { when(rd =/= 0) { regs(rd) := mtvec.asBits }; mtvec := rs1.asUInt }
              is(0x341) { when(rd =/= 0) { regs(rd) := mepc.asBits }; mepc := rs1.asUInt }
              is(0x342) { when(rd =/= 0) { regs(rd) := mcause } }
              default { fault := True }
            }
          }.otherwise { fault := True }
        }
        default { fault := True }
      }
    }
    is(3) { state := 4 }
    is(4) {
      when(io.bus.PREADY) {
        when(load && dest =/= 0) { regs(dest) := io.bus.PRDATA }
        fault := io.bus.PSLVERROR
        retired := retired + 1
        state := 0
      }
    }
  }
  when(io.debugReset) { pc := U(0x80000000L,32 bits); state := 0; fault := False }
}
