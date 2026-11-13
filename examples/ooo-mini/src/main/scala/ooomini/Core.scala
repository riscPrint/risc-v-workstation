package ooomini

import spinal.core._
import spinal.core.sim._
import spinal.lib._
import spinalprobes.Probe
import spinalchecks._

case class Retire() extends Bundle {
  val valid, trap, halt, intr, mem_fault = Bool()
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
    val interrupts = in Bits(32 bits)
    val interruptTaken = out Bool()
    val interruptCause = out Bits(32 bits)
    val fetch = out UInt(32 bits)
    val instruction = in Bits(32 bits)
    val load = out Bool()
    val loadAddress = out UInt(32 bits)
    val loadData = in Bits(32 bits) // four little-endian bytes at loadAddress
    val store = out Bool()
    val storeAddress = out UInt(32 bits)
    val storeMask = out Bits(4 bits)
    val storeData = out Bits(32 bits)
    val retire = out(Retire())
  }
  val started = Reg(Bool()).init(False)
  val pc = Reg(UInt(32 bits)).init(0)
  when(!started) { pc := io.boot; started := True }
  val privilege = Reg(UInt(2 bits)).init(3)
  val pmpConfig = Vec.fill(4)(Reg(Bits(8 bits)).init(0))
  val pmpAddress = Vec.fill(4)(Reg(UInt(32 bits)).init(0))
  val mcounteren = Reg(Bits(32 bits)).init(0)
  val fetchAllowed = Pmp.allowed(pmpConfig,pmpAddress,pc,U(4,3 bits),privilege === 3,2)
  io.fetch := Mux(fetchAllowed,pc,U(0,32 bits))
  val head, tail = Reg(UInt(slotWidth bits)).init(0)
  val count = Reg(UInt(log2Up(entries + 1) bits)).init(0)
  val handlerPending = Reg(Bool()).init(False)
  val nextId = Reg(UInt(32 bits)).init(0)
  val ids = Vec.fill(entries)(Reg(UInt(32 bits)).init(0))
  val predictedDirections = Vec.fill(entries)(Reg(Bool()).init(False))
  val takenDirections = Vec.fill(entries)(Reg(Bool()).init(False))
  val sequence = Reg(UInt(64 bits)).init(0)
  val retiredCount = Reg(UInt(64 bits)).init(0)
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
  val fetchFault = Vec.fill(entries)(Reg(Bool()).init(False))
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
  val mstatus = Reg(Bits(32 bits)).init(0x1800)
  val mtvec, mepc, mcause, mtval, mscratch, mie = Reg(Bits(32 bits)).init(0)
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
  val pendingInterrupts = io.interrupts & mie & B(0x888,32 bits)
  val interruptCode = UInt(5 bits)
  interruptCode := 7
  when(pendingInterrupts(3)) { interruptCode := 3 }
  when(pendingInterrupts(11)) { interruptCode := 11 }
  // Select a boundary before the completed head. No instruction retires on this edge.
  val interrupt = started && count =/= 0 && done(head) && (privilege =/= 3 || mstatus(3)) && pendingInterrupts.orR
  io.interruptTaken := interrupt
  io.interruptCause := B(0x80000000L,32 bits) | interruptCode.asBits.resize(32)
  val interruptTarget = (mtvec.asUInt & U(0xfffffffcL,32 bits)) +
    Mux(mtvec(1 downto 0) === B(1,2 bits),(interruptCode.resize(32) << 2).resize(32),U(0,32 bits))
  val pop = started && count =/= 0 && done(head) && !interrupt
  val fenceInstruction = insn(head)(6 downto 0) === B(0xf,7 bits) && insn(head)(14 downto 12) === B(1,3 bits)
  val systemRedirect = pop && !faults(head) && (insn(head) === B(0x30200073,32 bits) ||
    (csrWrite(head) && (csrAddress(head) === 0x300 || csrAddress(head) === 0x3a0 ||
      (csrAddress(head) >= 0x3b0 && csrAddress(head) < 0x3b4))))
  val redirect = systemRedirect || interrupt || (pop && (faults(head) || nextPc(head) =/= predicted(head) || fenceInstruction))
  val push = started && count < entries && (!writeRd || free.orR) && !redirect
  val allocatedMask = Mux(push && writeRd, B(1,physicalCount bits) |<< allocation, B(0,physicalCount bits))
  val releasedMask = Mux(pop && writes(head) && !faults(head), B(1,physicalCount bits) |<< old(head), B(0,physicalCount bits))
  free := (free | releasedMask) & ~allocatedMask
  when(push) {
    ids(tail) := nextId; nextId := nextId + 1
    predictedDirections(tail) := predictTaken
    valid(tail) := True; done(tail) := False; issued(tail) := False
    insn(tail) := instruction; pcs(tail) := pc; predicted(tail) := prediction
    nextPc(tail) := pc + 4
    rs1s(tail) := Mux(read1, instruction(19 downto 15).asUInt, U(0,5 bits))
    rs2s(tail) := Mux(read2, instruction(24 downto 20).asUInt, U(0,5 bits))
    src1(tail) := Mux(read1, map(instruction(19 downto 15).asUInt), U(0,tagWidth bits))
    src2(tail) := Mux(read2, map(instruction(24 downto 20).asUInt), U(0,tagWidth bits))
    rds(tail) := Mux(writeRd, rd, U(0,5 bits)); writes(tail) := writeRd
    dest(tail) := Mux(writeRd, allocation, U(0,tagWidth bits)); old(tail) := map(rd)
    fetchFault(tail) := !fetchAllowed
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
  val accessBytes = UInt(3 bits)
  accessBytes := 4
  when(funct(1 downto 0) === 0) { accessBytes := 1 }
  when(funct(1 downto 0) === 1) { accessBytes := 2 }
  val memoryMachine = privilege === 3 && (!mstatus(17) || mstatus(12 downto 11) === B(3,2 bits))
  val readAllowed = Pmp.allowed(pmpConfig,pmpAddress,effective,accessBytes,memoryMachine,0)
  val writeAllowed = Pmp.allowed(pmpConfig,pmpAddress,effective,accessBytes,memoryMachine,1)
  io.load := issue && isLoad(selected) && readAllowed && !fetchFault(selected)
  io.loadAddress := Mux(io.load,effective,U(0,32 bits))
  val ageValid = valid.asBits.setName("ageValid")
  val ageOlder = Bits(entries*entries bits).setName("ageOlder")
  for(i <- 0 until entries;j <- 0 until entries)
    ageOlder(i*entries+j) := valid(i) && valid(j) && (U(i,slotWidth bits)-head) < (U(j,slotWidth bits)-head)
  ageValid.simPublic(); ageOlder.simPublic()
  val forwardSelect = Vec(Bits(entries bits),4)
  val forwardOlder = Bits(entries bits).setName("forwardOlder")
  val forwardValid = Bits(entries bits).setName("forwardValid")
  for(i <- 0 until entries) {
    forwardOlder(i) := (U(i,slotWidth bits)-head) < selectAge
    forwardValid(i) := valid(i) && done(i) && isStore(i) && !faults(i)
  }
  forwardOlder.simPublic(); forwardValid.simPublic()
  val loadWord = Bits(32 bits)
  // Each byte takes the youngest older matching store. Partial stores merge.
  for (byte <- 0 until 4) {
    val choices = Vec(Bits(8 bits), entries + 1)
    val selections = Vec(Bits(entries bits),entries+1)
    selections(0) := 0
    val matches = Bits(entries bits).setName("forwardMatch"+byte)
    val storeBytes = Bits(entries*8 bits).setName("forwardData"+byte)
    for(i <- 0 until entries) {
      matches(i) := False
      storeBytes(i*8+7 downto i*8) := 0
      for(lane <- 0 until 4) when(address(i)+lane === effective+byte && masks(i)(lane)) {
        matches(i) := True
        storeBytes(i*8+7 downto i*8) := memoryData(i)(lane*8+7 downto lane*8)
      }
    }
    matches.simPublic(); storeBytes.simPublic()
    choices(0) := Mux(readAllowed,io.loadData(byte*8+7 downto byte*8),B(0,8 bits))
    for (age <- 0 until entries) {
      val s = (head + age).resize(slotWidth)
      choices(age+1) := choices(age)
      selections(age+1) := selections(age)
      for (lane <- 0 until 4) {
        when(U(age,slotWidth bits) < selectAge && valid(s) && done(s) && isStore(s) && !faults(s) &&
            address(s) + lane === effective + byte && masks(s)(lane)) {
          selections(age+1) := B(1,entries bits) |<< s
          choices(age+1) := memoryData(s)(lane*8+7 downto lane*8)
        }
      }
    }
    forwardSelect(byte) := selections(entries)
    val selectedByte = Bits(entries bits).setName("forwardSelected"+byte)
    selectedByte := selections(entries)
    val forwarded = Bool().setName("forwarded"+byte)
    forwarded := selections(entries).orR
    val observed = Bits(8 bits).setName("forwardObserved"+byte)
    observed := choices(entries)
    selectedByte.simPublic(); forwarded.simPublic(); observed.simPublic()
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
    is(0x300) { csrRead := mstatus }; is(0x301) { csrRead := B(0x40101100L,32 bits) }
    is(0x304) { csrRead := mie }; is(0x305) { csrRead := mtvec }; is(0x340) { csrRead := mscratch }
    is(0x341) { csrRead := mepc }; is(0x342) { csrRead := mcause }; is(0x343) { csrRead := mtval }
    is(0x306) { csrRead := mcounteren }
    is(0x3a0) { csrRead := pmpConfig.asBits }
    is(0x3b0,0x3b1,0x3b2,0x3b3) { csrRead := pmpAddress(csr(1 downto 0)).asBits }
    is(0x344) { csrRead := io.interrupts & B(0x888,32 bits) }
    is(0xf11,0xf12,0xf13,0xf14,0x3a1,0x3a2,0x3a3,0x3b4,0x3b5,0x3b6,0x3b7,0x3b8,0x3b9,0x3ba,0x3bb,0x3bc,0x3bd,0x3be,0x3bf) { csrRead := 0 }
    is(0xc00,0xb00) { csrRead := cycles(31 downto 0).asBits }
    is(0xc80,0xb80) { csrRead := cycles(63 downto 32).asBits }
    is(0xc02,0xb02) { csrRead := retiredCount(31 downto 0).asBits }
    is(0xc82,0xb82) { csrRead := retiredCount(63 downto 32).asBits }
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
      when((isLoad(selected) && !readAllowed) || (isStore(selected) && !writeAllowed)) {
        execution := 0; exception := True; cause := Mux(isStore(selected),U(7,5 bits),U(5,5 bits)); tval := effective.asBits
      }
      
    }
    is(0xf) { } // FENCE.I discards younger ROB slots at commit.
    is(0x73) {
      execution := csrRead
      when(funct === 0) {
        when(inst === B(0x30200073L,32 bits)) { target := mepc.asUInt }
        .elsewhen(inst === B(0x10500073L,32 bits)) { } // WFI may complete as a hint; enabled pending interrupts still trap.
        .otherwise { exception := True; cause := Mux(inst(20),U(3,5 bits),Mux(privilege === 3,U(11,5 bits),U(8,5 bits))) }
      } otherwise {
        when(!csrKnown || csr(9 downto 8) > privilege || (csr(11 downto 10) === 3 && csrWillWrite) ||
          (privilege === 0 && (csr === 0xc00 || csr === 0xc80) && !mcounteren(0)) ||
          (privilege === 0 && (csr === 0xc02 || csr === 0xc82) && !mcounteren(2))) { exception := True; cause := 2; tval := inst }
      }
    }
    default { exception := True; cause := 2; tval := inst }
  }
  when(target(1 downto 0) =/= 0 && isBranch(selected)) { exception := True; cause := 0; tval := target.asBits }
  val legalEncoding = Bool()
  legalEncoding := True
  val function7 = inst(31 downto 25)
  switch(op) {
    is(0x33) { legalEncoding := function7 === B(0,7 bits) || function7 === B(1,7 bits) || (function7 === B(0x20,7 bits) && (funct === 0 || funct === 5)) }
    is(0x13) {
      when(funct === 1) { legalEncoding := function7 === B(0,7 bits) }
      when(funct === 5) { legalEncoding := function7 === B(0,7 bits) || function7 === B(0x20,7 bits) }
    }
    is(3) { legalEncoding := funct === 0 || funct === 1 || funct === 2 || funct === 4 || funct === 5 }
    is(0x23) { legalEncoding := funct === 0 || funct === 1 || funct === 2 }
    is(0x63) { legalEncoding := funct === 0 || funct === 1 || funct === 4 || funct === 5 || funct === 6 || funct === 7 }
    is(0x67) { legalEncoding := funct === 0 }
    is(0xf) { legalEncoding := funct === 0 || funct === 1 }
    is(0x73) {
      legalEncoding := funct =/= 4
      when(funct === 0) { legalEncoding := inst === B(0x73,32 bits) || inst === B(0x100073,32 bits) || inst === B(0x30200073,32 bits) || inst === B(0x10500073,32 bits) }
      when(inst === B(0x100073,32 bits)) { tval := pcs(selected).asBits }
    }
  }
  when(!legalEncoding) { exception := True; cause := 2; tval := inst }
  when(privilege =/= 3 && (inst === B(0x30200073,32 bits) ||
      (inst === B(0x10500073,32 bits) && mstatus(21)))) {
    exception := True; cause := 2; tval := inst
  }
  when(fetchFault(selected)) { exception := True; cause := 1; tval := pcs(selected).asBits }
  val multiply = op === B(0x33,7 bits) && inst(31 downto 25) === B(1,7 bits)
  mulDiv.io.start := issue && multiply
  mulDiv.io.flush := redirect
  mulDiv.io.a := a
  mulDiv.io.b := b
  mulDiv.io.funct := funct.asUInt
  when(issue) {
    issued(selected) := True; operand1(selected) := a; operand2(selected) := b
    takenDirections(selected) := Mux(op === B(0x63,7 bits),branchTaken,isBranch(selected))
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
  r.mem_fault := pop && faults(head) && (causes(head) === 1 || causes(head) === 5 || causes(head) === 7)
  r.valid := pop; r.trap := faults(head); r.halt := False; r.intr := handlerPending
  r.order := sequence; r.insn := insn(head); r.mode := privilege; r.ixl := 1
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
  when(pop && !faults(head)) { retiredCount := retiredCount + 1 }
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
        is(0x300) {
          mstatus := (csrData(head) & B(0x220088,32 bits)) |
            Mux(csrData(head)(12 downto 11) === B(3,2 bits),B(0x1800,32 bits),B(0,32 bits))
        }; is(0x304) { mie := csrData(head) }
        is(0x305) { mtvec := (csrData(head) & B(0xfffffffcL,32 bits)) | Mux(csrData(head)(1 downto 0) === B(1,2 bits),B(1,32 bits),B(0,32 bits)) }; is(0x340) { mscratch := csrData(head) }
        is(0x341) { mepc := csrData(head) & B(0xfffffffcL,32 bits) }
        is(0x306) { mcounteren := csrData(head) & B(5,32 bits) }
        is(0x3a0) {
          for(i <- 0 until 4) when(!pmpConfig(i)(7)) {
            val incoming = csrData(head)(i*8+7 downto i*8)
            pmpConfig(i) := incoming & B(0x9f,8 bits)
            when(!incoming(0) && incoming(1)) { pmpConfig(i)(1) := False }
          }
        }
        is(0x3b0,0x3b1,0x3b2,0x3b3) {
          for(i <- 0 until 4) {
            val nextLockedTor = if(i == 3) False else pmpConfig(i+1)(7) && pmpConfig(i+1)(4 downto 3) === B(1,2 bits)
            when(csrAddress(head)(1 downto 0) === i && !pmpConfig(i)(7) && !nextLockedTor) { pmpAddress(i) := csrData(head).asUInt }
          }
        }
        is(0x342) { mcause := csrData(head) }; is(0x343) { mtval := csrData(head) }
      }
    }
    when(faults(head)) {
      mepc := pcs(head).asBits; mcause := causes(head).asBits.resize(32); mtval := tvals(head)
      mstatus(7) := mstatus(3); mstatus(3) := False
      mstatus(12 downto 11) := privilege.asBits; privilege := 3
    }
    when(!faults(head) && insn(head) === B(0x30200073,32 bits)) {
      mstatus(3) := mstatus(7); mstatus(7) := True
      privilege := mstatus(12 downto 11).asUInt; mstatus(12 downto 11) := 0
      when(mstatus(12 downto 11) =/= B(3,2 bits)) { mstatus(17) := False }
    }
  }
  when(push && !pop) { count := count+1 }
  when(pop && !push) { count := count-1 }
  val recoveryMap = Vec(UInt(tagWidth bits),32)
  for (i <- 0 until 32) recoveryMap(i) := Mux(pop && writes(head) && !faults(head) && rds(head) === i,dest(head),committed(i))
  val live = recoveryMap.map(t => B(1,physicalCount bits) |<< t).reduce(_ | _)
  when(redirect) {
    pc := Mux(interrupt,interruptTarget,r.pc_wdata); head := 0; tail := 0; count := 0
    free := ~live
    for (i <- 0 until 32) map(i) := recoveryMap(i)
    for (i <- 0 until entries) { valid(i) := False; done(i) := False; issued(i) := False }
  }
  when(interrupt) {
    mepc := pcs(head).asBits; mcause := io.interruptCause; mtval := 0
    mstatus(7) := mstatus(3); mstatus(3) := False
      mstatus(12 downto 11) := privilege.asBits; privilege := 3
    handlerPending := True
  }
  assert(count <= entries, "ROB occupancy")
  assert(!free(0), "x0 must never be free")
  when(pop) { assert(valid(head) && issued(head), "commit must own an issued ROB slot") }
  when(push && writeRd) { assert(free(allocation), "rename must allocate a free tag") }
  when(io.store) { assert(done(head) && !faults(head), "store must commit precisely") }
  // These properties live with the RTL. The same predicates feed native monitors
  // and the Scala property builder. Generation does not itself establish proof.
  val observedToken = ids(head).setName("observedToken")
  observedToken.simPublic()
  val loadFire = (issue && isLoad(selected)).setName("loadFire")
  loadFire.simPublic()
  val commitBytes = Mux(masks(head)(3),U(4,3 bits),Mux(masks(head)(1),U(2,3 bits),U(1,3 bits)))
  val commitStoreAllowed = Pmp.allowed(pmpConfig,pmpAddress,address(head),commitBytes,memoryMachine,1)
  val propertySignals = Seq(
    "privilege_supported" -> (privilege === 0 || privilege === 3),
    "store_permission" -> (!io.store || commitStoreAllowed),
    "rob_bound" -> (count <= entries),
    "rob_count" -> (count === CountOne(valid.asBits)),
    "zero_map" -> (map(0) === 0),
    "zero_committed" -> (committed(0) === 0),
    "zero_not_free" -> !free(0),
    "zero_value" -> (values(0) === 0),
    "zero_ready" -> ready(0),
    "rename_capacity" -> (!push || count < entries),
    "rename_allocation" -> (!(push && writeRd) || free(allocation)),
    "issue_live" -> (!issue || (valid(selected) && !issued(selected))),
    "issue_operands" -> (!issue || (ready(src1(selected)) && ready(src2(selected)))),
    "commit_ready" -> (!pop || (valid(head) && done(head) && issued(head))),
    "protection_precise" -> (!r.mem_fault || (r.trap && !io.store && r.rd_addr === 0)),
    "load_permission" -> (!io.load || readAllowed),
    "interrupt_precise" -> (!interrupt || (!pop && !io.store && !push && !issue)),
    "store_precise" -> (!io.store || (pop && isStore(head) && !faults(head))),
    "map_owned" -> !map.map(t => free(t)).reduce(_ || _)
  ).map { case(name,condition) =>
    val signal = Bool().setName("property_" + name)
    signal := condition
    signal.simPublic()
    DeclaredChecks.rule("ooo.property",name,name,trigger = True)(!signal)
    name -> signal
  }
  val properties = propertySignals.map { case(name,signal) => name -> Sva.signal(signal).sequence.strong }
  QueueChecks.fifo("rob",entries,push,pop,redirect,nextId.asBits,ids(head).asBits,count)
  val liveTags = committed.map(t => B(1,physicalCount bits) |<< t).reduce(_ | _) |
    (0 until entries).map(i => Mux(valid(i) && writes(i),B(1,physicalCount bits) |<< dest(i),B(0,physicalCount bits))).reduce(_ | _)
  DeclaredChecks.rule("freelist.conservation","rename","free and owned tags partition the register file",trigger = True)(free =/= ~liveTags)
  DeclaredChecks.rule("execution.operands","issue","both physical sources are ready",trigger = issue)(issue && (!ready(src1(selected)) || !ready(src2(selected))))
  if(Probe.isEnabled) {
    Probe.custom("speculative_fault",issue && exception && selected =/= head,
      "cause" -> cause,"pc" -> pcs(selected),"id" -> ids(selected))
    val forwardedBytes = Bits(4 bits)
    for(i <- 0 until 4) forwardedBytes(i) := forwardSelect(i).orR
    val olderRecovery = (0 until entries).map { i =>
      valid(i) && done(i) && isBranch(i) && !faults(i) && nextPc(i) =/= predicted(i) &&
        (U(i,slotWidth bits)-head) < selectAge
    }.reduce(_ || _)
    Probe.custom("forwarding",loadFire,"bytes" -> forwardedBytes,"pending_recovery" -> olderRecovery)
    Probe.counter("forward_pending_recovery",loadFire && forwardedBytes.orR && olderRecovery)
    Probe.counter("interrupt_rob_full",interrupt && count === entries)
    val sinceRecovery = Reg(UInt(4 bits)).init(15)
    val seenRecovery = Reg(Bool()).init(False)
    when(sinceRecovery =/= 15) { sinceRecovery := sinceRecovery+1 }
    when(redirect) { sinceRecovery := 0; seenRecovery := True }
    Probe.counter("recoveries_within_8",redirect && seenRecovery && sinceRecovery < 8)
    Probe.custom("recovery_spacing",redirect && seenRecovery,"gap" -> (sinceRecovery.resize(5)+1))
  }
  Probe.stageAt("rename","Rn",push,nextId,Some(pc),first = true)
  Probe.stageAt("issue","Is",issue,ids(selected),Some(pcs(selected)))
  Probe.stageAt("commit","Cm",pop,ids(head),Some(pcs(head)))
  // No LSU attempt can be rejected: loads wait before issue, byte forwarding always
  // merges, RAM is combinational, and there is no translation. Declare zero support
  // explicitly. Do not turn pre-issue waits into retry events.
  for (cause <- Seq("memory_order_violation", "store_forward_miss", "cache_miss_retry", "tlb_miss"))
    Probe.lsuRetry(cause,False,ids(selected),cause)
  Probe.retire("commit",pop && !faults(head),ids(head))
  Probe.flushYounger("recovery",redirect,ids(head),faults(head) || interrupt)
  Probe.custom("flush_reason",redirect,"reason" -> Mux(interrupt,U(3,2 bits),Mux(faults(head),U(1,2 bits),U(2,2 bits))))
  Probe.custom("protection_fault",pop && r.mem_fault,"cause" -> causes(head),"pc" -> pcs(head),"address" -> tvals(head),"privilege" -> privilege)
  Probe.custom("interrupt",interrupt,"cause" -> io.interruptCause,"pc" -> pcs(head),"occupancy" -> count)
  Probe.branch("predictor",pop && isBranch(head) && !faults(head),pcs(head),takenDirections(head),nextPc(head),
    predictedTaken = Some(predictedDirections(head)),predictedTarget = Some(predicted(head)),id = Some(ids(head)))
  Probe.custom("occupancy",True,"rob" -> count,"iq" -> CountOne((0 until entries).map(i => valid(i) && !issued(i))),
    "lsq" -> CountOne((0 until entries).map(i => valid(i) && (isLoad(i) || isStore(i)))))
  Probe.stall("rename","rob_full",started && count === entries)
  Probe.stall("rename","physical_full",started && writeRd && !free.orR)
  // Commit-slot accounting. Waiting at a nonempty ROB head is backend-bound.
  // This does not attribute execution cycles to each squashed instruction.
  Probe.counter("topdown_slots",started)
  Probe.counter("topdown_retiring",started && pop && !faults(head))
  Probe.counter("topdown_bad_speculation",started && pop && faults(head))
  Probe.counter("topdown_backend_bound",started && !pop && count =/= 0)
  Probe.counter("topdown_frontend_bound",started && count === 0)
  liveTags.simPublic()
  Probe.counter("commits",pop && !faults(head))
  Probe.counter("ooo_issues",issue && selected =/= head)
  Probe.faultSite("rename_map1",map(1))
  Probe.faultSite("rob_head",head)
  Probe.faultSite("rob_count",count)
}

object Generate extends App {
  val config = SpinalConfig(targetDirectory = "rvw/out/rtl",defaultConfigForClockDomains = ClockDomainConfig(resetKind = SYNC))
  val (cfg,_) = SpinalChecks.install(config,ChecksConfig(mode = Mode.Assert,enable = Seq("ooo.*","queue.*","freelist.*","execution.*")))
  val report = Probe.enabled(true) { cfg.includeFormal.generateVerilog(new Core()) }
  Sva.write(java.nio.file.Paths.get("rvw/out/rtl/properties.sv"),report.toplevel.properties.map { case(name,p) => p.assertOn(name,Sva.signal("clk"),Some(Sva.signal("reset"))) })
}
