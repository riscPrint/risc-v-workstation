package ooomini

import spinal.core._
import spinal.lib._
import spinalprobes.Probe

case class Retire() extends Bundle {
  val valid, trap, halt, intr = Bool()
  val order = UInt(64 bits)
  val insn = Bits(32 bits)
  val mode = UInt(2 bits)
  val ixl = UInt(2 bits)
  val rs1_addr, rs2_addr, rd_addr = UInt(5 bits)
  val rs1_rdata, rs2_rdata, rd_wdata = Bits(32 bits)
  val pc_rdata, pc_wdata, mem_addr = UInt(32 bits)
  val mem_rmask, mem_wmask = Bits(4 bits)
  val mem_rdata, mem_wdata = Bits(32 bits)
}

/** Cacheless RV32IM. The ROB also holds the issue and memory queues.
  * Slots retain physical source tags until commit. A ready bit wakes dependents.
  * Stores change memory only at commit. Recovery restores the committed map.
  */
class Core(val entries: Int = 8, val physicalCount: Int = 48) extends Component {
  require(isPow2(entries) && entries >= 4)
  require(physicalCount >= 32 + entries)
  val tagWidth = log2Up(physicalCount)
  val slotWidth = log2Up(entries)
  val io = new Bundle {
    val boot = in UInt(32 bits)
    val fetch = out UInt(32 bits)
    val instruction = in Bits(32 bits)
    val loadAddress = out UInt(32 bits)
    val loadData = in Bits(32 bits) // aligned little-endian word
    val store = out Bool()
    val storeAddress = out UInt(32 bits)
    val storeMask = out Bits(4 bits)
    val storeData = out Bits(32 bits)
    val retire = out(Retire())
  }
  val started = Reg(Bool()).init(False)
  val pc = Reg(UInt(32 bits)).init(0)
  when(!started) { pc := io.boot; started := True }
  io.fetch := pc
  val head, tail = Reg(UInt(slotWidth bits)).init(0)
  val count = Reg(UInt(log2Up(entries + 1) bits)).init(0)
  val handlerPending = Reg(Bool()).init(False)
  val sequence = Reg(UInt(64 bits)).init(0)
  val map = Vec((0 until 32).map(i => Reg(UInt(tagWidth bits)).init(i)))
  val committed = Vec((0 until 32).map(i => Reg(UInt(tagWidth bits)).init(i)))
  val free = Reg(Bits(physicalCount bits)).init(((BigInt(1) << physicalCount) - 1) ^ ((BigInt(1) << 32) - 1))
  val ready = Vec((0 until physicalCount).map(i => Reg(Bool()).init(i < 32)))
  val values = Vec.fill(physicalCount)(Reg(Bits(32 bits)).init(0))
  val valid, done, issued = Vec.fill(entries)(Reg(Bool()).init(False))
  def tags() = Vec.fill(entries)(Reg(UInt(tagWidth bits)).init(0))
  val src1, src2, dest, old = tags()
  val insn = Vec.fill(entries)(Reg(Bits(32 bits)).init(0))
  val pcs, predicted, nextPc = Vec.fill(entries)(Reg(UInt(32 bits)).init(0))
  val result, operand1, operand2 = Vec.fill(entries)(Reg(Bits(32 bits)).init(0))
  val address = Vec.fill(entries)(Reg(UInt(32 bits)).init(0))
  val memoryData = Vec.fill(entries)(Reg(Bits(32 bits)).init(0))
  val faults = Vec.fill(entries)(Reg(Bool()).init(False))
  val causes = Vec.fill(entries)(Reg(UInt(5 bits)).init(0))
  val tvals = Vec.fill(entries)(Reg(Bits(32 bits)).init(0))
  val writes = Vec.fill(entries)(Reg(Bool()).init(False))
  val isLoad, isStore, isBranch, isSystem = Vec.fill(entries)(Reg(Bool()).init(False))
  val rs1s, rs2s, rds = Vec.fill(entries)(Reg(UInt(5 bits)).init(0))
  val masks = Vec.fill(entries)(Reg(Bits(4 bits)).init(0))
  val csrAddress = Vec.fill(entries)(Reg(UInt(12 bits)).init(0))
  val csrData = Vec.fill(entries)(Reg(Bits(32 bits)).init(0))
  val csrWrite = Vec.fill(entries)(Reg(Bool()).init(False))
  val mstatus, mtvec, mepc, mcause, mtval, mscratch, mie = Reg(Bits(32 bits)).init(0)
  val cycles = Reg(UInt(64 bits)).init(0)
  cycles := cycles + 1

  // A direct-mapped BTB and two-bit direction table. Train at commit.
  val btbValid = Vec.fill(16)(Reg(Bool()).init(False))
  val btbTag = Vec.fill(16)(Reg(UInt(26 bits)).init(0))
  val btbTarget = Vec.fill(16)(Reg(UInt(32 bits)).init(0))
  val direction = Vec.fill(16)(Reg(UInt(2 bits)).init(1))
  val pi = pc(5 downto 2)
  val predictTaken = btbValid(pi) && btbTag(pi) === pc(31 downto 6) && direction(pi)(1)
  val prediction = Mux(predictTaken, btbTarget(pi), pc + 4)
  val allocation = UInt(tagWidth bits)
  allocation := 0
  for (i <- physicalCount - 1 to 1 by -1) when(free(i)) { allocation := i }
  val instruction = io.instruction
  val opcode = instruction(6 downto 0)
  val rd = instruction(11 downto 7).asUInt
  val read1 = opcode === B(0x33,7 bits) || opcode === B(0x13,7 bits) || opcode === B(3,7 bits) || opcode === B(0x23,7 bits) || opcode === B(0x63,7 bits) || opcode === B(0x67,7 bits) || (opcode === B(0x73,7 bits) && !instruction(14))
  val read2 = opcode === B(0x33,7 bits) || opcode === B(0x23,7 bits) || opcode === B(0x63,7 bits)
  val writeRd = rd =/= 0 && (opcode === B(0x33,7 bits) || opcode === B(0x13,7 bits) || opcode === B(3,7 bits) || opcode === B(0x37,7 bits) || opcode === B(0x17,7 bits) || opcode === B(0x6f,7 bits) || opcode === B(0x67,7 bits) || (opcode === B(0x73,7 bits) && instruction(14 downto 12) =/= 0))
  val pop = started && count =/= 0 && done(head)
  val redirect = pop && (faults(head) || nextPc(head) =/= predicted(head))
  val push = started && count < entries && (!writeRd || free.orR) && !redirect
  val allocatedMask = Mux(push && writeRd, B(1,physicalCount bits) |<< allocation, B(0,physicalCount bits))
  val releasedMask = Mux(pop && writes(head) && !faults(head), B(1,physicalCount bits) |<< old(head), B(0,physicalCount bits))
  free := (free | releasedMask) & ~allocatedMask
  when(push) {
    valid(tail) := True; done(tail) := False; issued(tail) := False
    insn(tail) := instruction; pcs(tail) := pc; predicted(tail) := prediction
    nextPc(tail) := pc + 4
    rs1s(tail) := Mux(read1, instruction(19 downto 15).asUInt, U(0,5 bits))
    rs2s(tail) := Mux(read2, instruction(24 downto 20).asUInt, U(0,5 bits))
    src1(tail) := Mux(read1, map(instruction(19 downto 15).asUInt), U(0,tagWidth bits))
    src2(tail) := Mux(read2, map(instruction(24 downto 20).asUInt), U(0,tagWidth bits))
    rds(tail) := Mux(writeRd, rd, U(0,5 bits)); writes(tail) := writeRd
    dest(tail) := Mux(writeRd, allocation, U(0,tagWidth bits)); old(tail) := map(rd)
    faults(tail) := False; causes(tail) := U(0,5 bits); tvals(tail) := B(0,32 bits)
    masks(tail) := B(0,4 bits); address(tail) := U(0,32 bits); memoryData(tail) := B(0,32 bits); csrWrite(tail) := False
    isLoad(tail) := opcode === B(3,7 bits); isStore(tail) := opcode === B(0x23,7 bits)
    isBranch(tail) := opcode === B(0x63,7 bits) || opcode === B(0x6f,7 bits) || opcode === B(0x67,7 bits)
    isSystem(tail) := opcode === B(0x73,7 bits) || opcode === B(0xf,7 bits)
    when(writeRd) { map(rd) := allocation; ready(allocation) := False }
    tail := tail + 1; pc := prediction
  }

  // Age-ordered selection. An unresolved older store blocks a load.
  val mulDiv = new MulDiv
  val mdBusy = mulDiv.io.busy
  val mdSlot = Reg(UInt(slotWidth bits)).init(0)
  val candidates = Bits(entries bits)
  for (age <- 0 until entries) {
    val slot = (head + age).resize(slotWidth)
    val olderStorePending = (0 until age).map { a =>
      val s = (head + a).resize(slotWidth)
      valid(s) && isStore(s) && !done(s)
    }.foldLeft(False)(_ || _)
    val multiply = insn(slot)(6 downto 0) === B(0x33,7 bits) && insn(slot)(25)
    candidates(age) := valid(slot) && !issued(slot) && ready(src1(slot)) && ready(src2(slot)) &&
      (!isLoad(slot) || !olderStorePending) && (!isSystem(slot) || slot === head) && (!multiply || !mdBusy)
  }
  val selectAge = OHToUInt(OHMasking.first(candidates))
  val selected = (head + selectAge).resize(slotWidth)
  val issue = candidates.orR && !redirect
  val a = values(src1(selected)); val b = values(src2(selected))
  val inst = insn(selected); val op = inst(6 downto 0); val funct = inst(14 downto 12)
  val immI = inst(31 downto 20).asSInt.resize(32).asBits
  val immS = (inst(31 downto 25) ## inst(11 downto 7)).asSInt.resize(32).asBits
  val immB = (inst(31) ## inst(7) ## inst(30 downto 25) ## inst(11 downto 8) ## False).asSInt.resize(32).asUInt
  val immJ = (inst(31) ## inst(19 downto 12) ## inst(20) ## inst(30 downto 21) ## False).asSInt.resize(32).asUInt
  val rhs = Mux(op === B(0x13,7 bits), immI, b)
  val arithmetic = Bits(32 bits)
  arithmetic := (a.asUInt + rhs.asUInt).asBits
  switch(funct) {
    is(0) { when(op === B(0x33,7 bits) && inst(30)) { arithmetic := (a.asUInt - b.asUInt).asBits } }
    is(1) { arithmetic := (a |<< rhs(4 downto 0).asUInt) }
    is(2) { arithmetic := (a.asSInt < rhs.asSInt).asBits.resize(32) }
    is(3) { arithmetic := (a.asUInt < rhs.asUInt).asBits.resize(32) }
    is(4) { arithmetic := a ^ rhs }
    is(5) { arithmetic := (a |>> rhs(4 downto 0).asUInt); when(inst(30)) { arithmetic := (a.asSInt >> rhs(4 downto 0).asUInt).asBits } }
    is(6) { arithmetic := a | rhs }
    is(7) { arithmetic := a & rhs }
  }
  val branchTaken = Bool()
  branchTaken := False
  switch(funct) {
    is(0) { branchTaken := a === b }; is(1) { branchTaken := a =/= b }
    is(4) { branchTaken := a.asSInt < b.asSInt }; is(5) { branchTaken := a.asSInt >= b.asSInt }
    is(6) { branchTaken := a.asUInt < b.asUInt }; is(7) { branchTaken := a.asUInt >= b.asUInt }
  }
  val effective = a.asUInt + Mux(isStore(selected), immS, immI).asUInt
  io.loadAddress := effective
  val loadWord = Bits(32 bits)
  // Each byte takes the youngest older matching store. Partial stores merge.
  for (byte <- 0 until 4) {
    val choices = Vec(Bits(8 bits), entries + 1)
    choices(0) := io.loadData(byte*8+7 downto byte*8)
    for (age <- 0 until entries) {
      val s = (head + age).resize(slotWidth)
      choices(age+1) := choices(age)
      for (lane <- 0 until 4) {
        when(U(age,slotWidth bits) < selectAge && valid(s) && done(s) && isStore(s) &&
            address(s) + lane === effective + byte && masks(s)(lane)) {
          choices(age+1) := memoryData(s)(lane*8+7 downto lane*8)
        }
      }
    }
    loadWord(byte*8+7 downto byte*8) := choices(entries)
  }
  val shifted = loadWord
  val loaded = Bits(32 bits)
  loaded := shifted
  switch(funct) {
    is(0) { loaded := shifted(7 downto 0).asSInt.resize(32).asBits }
    is(1) { loaded := shifted(15 downto 0).asSInt.resize(32).asBits }
    is(4) { loaded := shifted(7 downto 0).resize(32) }
    is(5) { loaded := shifted(15 downto 0).resize(32) }
  }
  val mask = Bits(4 bits)
  mask := B"1111"
  switch(funct(1 downto 0)) { is(0) { mask := B"0001" }; is(1) { mask := B"0011" } }
  val misaligned = (funct(1 downto 0) === 1 && effective(0)) || (funct(1 downto 0) === 2 && effective(1 downto 0) =/= 0)
  val execution = Bits(32 bits)
  val target = UInt(32 bits)
  val exception = Bool(); val cause = UInt(5 bits); val tval = Bits(32 bits)
  execution := arithmetic; target := pcs(selected) + 4; exception := False; cause := 0; tval := 0
  val csr = inst(31 downto 20).asUInt
  val csrRead = Bits(32 bits); val csrKnown = Bool()
  csrRead := 0; csrKnown := True
  switch(csr) {
    is(0x300) { csrRead := mstatus }; is(0x301) { csrRead := B(0x40001100L,32 bits) }
    is(0x304) { csrRead := mie }; is(0x305) { csrRead := mtvec }; is(0x340) { csrRead := mscratch }
    is(0x341) { csrRead := mepc }; is(0x342) { csrRead := mcause }; is(0x343) { csrRead := mtval }
    is(0x344,0xf11,0xf12,0xf13,0xf14,0x3a0,0x3a1,0x3a2,0x3a3,0x3b0,0x3b1,0x3b2,0x3b3,0x3b4,0x3b5,0x3b6,0x3b7,0x3b8,0x3b9,0x3ba,0x3bb,0x3bc,0x3bd,0x3be,0x3bf) { csrRead := 0 }
    is(0xc00,0xb00) { csrRead := cycles(31 downto 0).asBits }
    is(0xc80,0xb80) { csrRead := cycles(63 downto 32).asBits }
    is(0xc02,0xb02) { csrRead := sequence(31 downto 0).asBits }
    is(0xc82,0xb82) { csrRead := sequence(63 downto 32).asBits }
    default { csrKnown := False }
  }
  val csrSource = Mux(inst(14), inst(19 downto 15).resize(32), a)
  val csrNew = Bits(32 bits); csrNew := csrSource
  switch(funct(1 downto 0)) { is(2) { csrNew := csrRead | csrSource }; is(3) { csrNew := csrRead & ~csrSource } }
  val csrWillWrite = funct(1 downto 0) === 1 || csrSource.orR
  switch(op) {
    is(0x37) { execution := inst(31 downto 12) ## B(0,12 bits) }
    is(0x17) { execution := (pcs(selected) + (inst(31 downto 12) ## B(0,12 bits)).asUInt).asBits }
    is(0x13,0x33) { }
    is(0x6f) { execution := (pcs(selected)+4).asBits; target := pcs(selected)+immJ }
    is(0x67) { execution := (pcs(selected)+4).asBits; target := (a.asUInt+immI.asUInt) & U(0xfffffffeL,32 bits) }
    is(0x63) { when(branchTaken) { target := pcs(selected)+immB } }
    is(3,0x23) {
      execution := loaded
      
    }
    is(0xf) { } // No caches or speculative instruction buffer.
    is(0x73) {
      execution := csrRead
      when(funct === 0) {
        when(inst === B(0x30200073L,32 bits)) { target := mepc.asUInt }
        .elsewhen(inst === B(0x10500073L,32 bits)) { } // WFI is a hint without interrupts.
        .otherwise { exception := True; cause := Mux(inst(20),U(3,5 bits),U(11,5 bits)) }
      } otherwise {
        when(!csrKnown || (csr(11 downto 10) === 3 && csrWillWrite)) { exception := True; cause := 2; tval := inst }
      }
    }
    default { exception := True; cause := 2; tval := inst }
  }
  when(target(1 downto 0) =/= 0 && isBranch(selected)) { exception := True; cause := 0; tval := target.asBits }
  val multiply = op === B(0x33,7 bits) && inst(31 downto 25) === B(1,7 bits)
  mulDiv.io.start := issue && multiply
  mulDiv.io.flush := redirect
  mulDiv.io.a := a
  mulDiv.io.b := b
  mulDiv.io.funct := funct.asUInt
  when(issue) {
    issued(selected) := True; operand1(selected) := a; operand2(selected) := b
    nextPc(selected) := target; faults(selected) := exception; causes(selected) := cause; tvals(selected) := tval
    address(selected) := effective
    masks(selected) := mask
    memoryData(selected) := Mux(isStore(selected), b, loadWord)
    csrAddress(selected) := csr; csrData(selected) := csrNew
    csrWrite(selected) := isSystem(selected) && funct =/= 0 && csrWillWrite
    when(multiply) {
      mdSlot := selected
    } otherwise {
      done(selected) := True; result(selected) := execution
      when(writes(selected)) { values(dest(selected)) := execution; ready(dest(selected)) := True }
    }
  }
  when(mulDiv.io.done) {
    done(mdSlot) := True
    result(mdSlot) := mulDiv.io.result
    when(writes(mdSlot)) {
      values(dest(mdSlot)) := mulDiv.io.result
      ready(dest(mdSlot)) := True
    }
  }

  io.store := pop && isStore(head) && !faults(head)
  io.storeAddress := address(head)
  io.storeMask := masks(head); io.storeData := memoryData(head)
  val r = io.retire
  r.valid := pop; r.trap := faults(head); r.halt := False; r.intr := handlerPending
  r.order := sequence; r.insn := insn(head); r.mode := 3; r.ixl := 1
  r.rs1_addr := rs1s(head); r.rs2_addr := rs2s(head)
  r.rs1_rdata := operand1(head); r.rs2_rdata := operand2(head)
  r.rd_addr := Mux(writes(head) && !faults(head),rds(head),U(0,5 bits))
  r.rd_wdata := Mux(writes(head) && !faults(head),result(head),B(0,32 bits))
  r.pc_rdata := pcs(head); r.pc_wdata := Mux(faults(head),mtvec.asUInt & U(0xfffffffcL,32 bits),nextPc(head))
  r.mem_addr := Mux(isLoad(head) || isStore(head),address(head),U(0,32 bits))
  // C2 uses byte masks relative to the effective address, not the bus word.
  r.mem_rmask := Mux(isLoad(head) && !faults(head),masks(head),B(0,4 bits))
  r.mem_wmask := Mux(isStore(head) && !faults(head),masks(head),B(0,4 bits))
  r.mem_rdata := memoryData(head)
  r.mem_wdata := operand2(head)
  when(pop) {
    valid(head) := False; head := head+1; sequence := sequence+1
    handlerPending := faults(head)
    when(writes(head) && !faults(head)) { committed(rds(head)) := dest(head) }
    when(isBranch(head) && !faults(head)) {
      val index = pcs(head)(5 downto 2)
      val taken = nextPc(head) =/= pcs(head)+4
      btbValid(index) := True; btbTag(index) := pcs(head)(31 downto 6); btbTarget(index) := nextPc(head)
      when(taken && direction(index) =/= 3) { direction(index) := direction(index)+1 }
      when(!taken && direction(index) =/= 0) { direction(index) := direction(index)-1 }
    }
    when(csrWrite(head) && !faults(head)) {
      switch(csrAddress(head)) {
        is(0x300) { mstatus := csrData(head) }; is(0x304) { mie := csrData(head) }
        is(0x305) { mtvec := csrData(head) }; is(0x340) { mscratch := csrData(head) }
        is(0x341) { mepc := csrData(head) & B(0xfffffffcL,32 bits) }
        is(0x342) { mcause := csrData(head) }; is(0x343) { mtval := csrData(head) }
      }
    }
    when(faults(head)) { mepc := pcs(head).asBits; mcause := causes(head).asBits.resize(32); mtval := tvals(head) }
  }
  when(push && !pop) { count := count+1 }
  when(pop && !push) { count := count-1 }
  val recoveryMap = Vec(UInt(tagWidth bits),32)
  for (i <- 0 until 32) recoveryMap(i) := Mux(pop && writes(head) && !faults(head) && rds(head) === i,dest(head),committed(i))
  val live = recoveryMap.map(t => B(1,physicalCount bits) |<< t).reduce(_ | _)
  when(redirect) {
    pc := r.pc_wdata; head := 0; tail := 0; count := 0
    free := ~live
    for (i <- 0 until 32) map(i) := recoveryMap(i)
    for (i <- 0 until entries) { valid(i) := False; done(i) := False; issued(i) := False }
  }
  assert(count <= entries, "ROB occupancy")
  assert(!free(0), "x0 must never be free")
  when(pop) { assert(valid(head) && issued(head), "commit must own an issued ROB slot") }
  when(push && writeRd) { assert(free(allocation), "rename must allocate a free tag") }
  when(io.store) { assert(done(head) && !faults(head), "store must commit precisely") }
  Probe.custom("rob_occupancy",True,"count" -> count)
  Probe.stall("rename","capacity",started && !push)
}

object Generate extends App {
  SpinalConfig(targetDirectory = "rvw/out/rtl").generateVerilog(new Core())
}
