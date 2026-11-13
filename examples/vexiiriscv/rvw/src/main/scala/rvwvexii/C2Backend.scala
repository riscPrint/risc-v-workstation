package rvwvexii

import java.io.File
import rvls.spinal.{TraceBackend, TraceIo}
import riscvsim.{RvfiRecord, RvfiTraceWriter, RvfiFpState}
import scala.collection.mutable

/** Turns the upstream VexiiRiscvProbe events into C2 retirement records and trap events.
  *
  * The probe reports, in retirement order: the committed register, load and store effects of one
  * micro-op, then `commit(pc, insn)`, or `trap(interrupt, code)` for a trap. Register numbers and
  * source operands come from the instruction bits and a shadow register file that only the
  * core's own committed writes update. `pc_next` is the pc of the next retirement, or the trap's
  * xepc when a trap follows. The last record of a run uses the decoded fall-through target. */
class C2Backend(xlen: Int, cycle: () => Long, mode: () => Int, nextTrap: () => (BigInt, BigInt),
                sink: RvfiRecord => Unit, trapSink: (Long, BigInt, BigInt, Boolean) => Unit,
                onStore: (BigInt, Int, BigInt) => Unit,
                resolveAddress: (Boolean, Long, Long) => Long = (_, _, address) => address,
                fpSnapshot: Option[() => (BigInt, BigInt)] = None,
                instructionAt: Option[BigInt => Long] = None,
                lateFlags: () => BigInt = () => BigInt(0)) extends TraceBackend {
  private val mask = (BigInt(1) << xlen) - 1
  val regs: Array[BigInt] = Array.fill(32)(BigInt(0))
  var retired = 0L
  var traps = 0L
  private var order = BigInt(0)
  private var handler = false
  private var pending: Option[RvfiRecord] = None
  def pendingCycle: Option[Long] = pending.map(_.cycle)
  /** The upstream return retires before its CSR state machine finishes. */
  def returnStatus(value: BigInt): Unit = pending match {
    case Some(r) if r.insn == 0x30200073L => pending = Some(r.copy(csrState = Map(0x300 -> value)))
    case _ => throw new IllegalStateException("return state update without a pending mret")
  }

  private var fdData: Option[BigInt] = None
  private var rdData: Option[BigInt] = None
  private val loads = mutable.LongMap.empty[(Long, Long, BigInt)]
  private val stores = mutable.LongMap.empty[(Long, Long, BigInt)]
  private var load: Option[(Long, Long, BigInt)] = None
  private var store: Option[(Long, Long, BigInt)] = None
  private val physicalStores = mutable.LongMap.empty[Long]
  private var storePhysical: Option[Long] = None
  private val io = mutable.Queue.empty[(Boolean, Long, Int, BigInt)]

  private def bytes(data: Array[Byte], len: Long): BigInt =
    (0 until len.toInt).foldLeft(BigInt(0))((v, i) => v | (BigInt(data(i) & 0xff) << (8 * i)))

  private def emit(next: BigInt): Unit = {
    pending.foreach(r => sink(r.copy(pcNext = next & mask)))
    pending = None
  }

  /** Writes the buffered record with its decoded fall-through target. Call at the end of a run. */
  def drain(): Unit = pending.foreach(r => emit(C2Backend.fallThrough(r, xlen)))

  def resetState(): Unit = {
    pending = None; fdData = None; rdData = None; load = None; store = None; storePhysical = None
    loads.clear(); stores.clear(); physicalStores.clear(); io.clear()
    regs.indices.foreach(i => regs(i) = BigInt(0))
    handler = false
  }

  override def commit(hartId: Int, pc: Long, instruction: Long): Unit = {
    val insn = instruction & 0xffffffffL
    val pcValue = BigInt(pc) & mask
    emit(pcValue)
    val (rs1, rs2) = C2Backend.sources(insn)
    val rdField = ((insn >> 7) & 31).toInt
    val (rd, wdata) = rdData match {
      case Some(v) if rdField != 0 => (rdField, v & mask)
      case _ => (0, BigInt(0))
    }
    if (load.isEmpty && store.isEmpty && io.nonEmpty && Set(0x03L, 0x23L)(insn & 0x7f)) {
      val (write, address, size, data) = io.dequeue()
      val expectedWrite = (insn & 0x7f) == 0x23
      val raw = if (expectedWrite) ((insn >> 25) << 5) | ((insn >> 7) & 31) else insn >> 20
      val immediate = (raw.toInt << 20) >> 20
      require(write == expectedWrite && (BigInt(address) & mask) == ((regs(rs1) + immediate) & mask),
        "I/O observation does not match retiring instruction")
      if (write) { store = Some((address, size.toLong, data)); storePhysical = Some(address) } else load = Some((address, size.toLong, data))
    }
    val (memAddr, rmask, rdataMem, wmask, wdataMem) = (load, store) match {
      case (Some((a, n, d)), None) => ((BigInt(a) & mask), ((1 << n) - 1).toInt, d, 0, BigInt(0))
      case (None, Some((a, n, d))) => ((BigInt(a) & mask), 0, BigInt(0), ((1 << n) - 1).toInt, d)
      case (None, None) => (BigInt(0), 0, BigInt(0), 0, BigInt(0))
      case (Some((a, n, d)), Some((sa, sn, sd))) =>
        require(a == sa && n == sn, "atomic read/write addresses differ")
        ((BigInt(a) & mask), ((1 << n) - 1).toInt, d, ((1 << sn) - 1).toInt, sd)
    }
    val snapshot = fpSnapshot.map { sample =>
      val (fcsr, status) = sample()
      // The real flags writeback can follow the probe's result retirement.
      val raised = if (Set(0x43L, 0x47L, 0x4bL, 0x4fL, 0x53L)(insn & 0x7f)) lateFlags() else BigInt(0)
      (fcsr | raised, status)
    }
    val fp = snapshot.map { case (fcsr, _) =>
      RvfiFpState(fdData.nonEmpty, if (fdData.nonEmpty) rdField else 0,
        fdData.getOrElse(BigInt(0)), fcsr & 31, fcsr)
    }
    val r = RvfiRecord(order, cycle(), instructionAt.map(_(pcValue)).getOrElse(insn), trap = false, halt = false, intr = handler, mode = mode(), ixl = (if (xlen == 64) 2 else 1),
      rs1 = rs1, rs1Rdata = regs(rs1), rs2 = rs2, rs2Rdata = regs(rs2), rd = rd, rdWdata = wdata,
      pc = pcValue, pcNext = 0, memAddr = memAddr, memRmask = rmask, memWmask = wmask,
      memRdata = rdataMem, memWdata = wdataMem, memFault = false, csrState = snapshot.map(s => Map(0x300 -> s._2)).getOrElse(Map.empty), fpState = fp)
    if (rd != 0) regs(rd) = wdata
    order += 1
    retired += 1
    handler = false
    fdData = None; rdData = None; load = None
    pending = Some(r)
    store.foreach { case (a, n, d) => onStore(BigInt(storePhysical.getOrElse(throw new IllegalStateException("store has no physical address"))) & mask, Integer.numberOfTrailingZeros(n.toInt), d) }
    store = None; storePhysical = None
  }

  override def trap(hartId: Int, interrupt: Boolean, code: Int): Unit = {
    val (epc, tval) = nextTrap()
    emit(epc)
    val cause = if (interrupt) (BigInt(1) << (xlen - 1)) | code else BigInt(code)
    trapSink(cycle(), cause, tval & mask, interrupt)
    traps += 1
    handler = true
    fdData = None; rdData = None; load = None; store = None; storePhysical = None
  }

  override def writeRf(hartId: Int, rfKind: Int, address: Int, data: Array[Byte]): Unit =
    if (rfKind == 0) rdData = Some(bytes(data, xlen / 8))
    else if (rfKind == 1) fdData = Some(bytes(data, 8))
  override def loadExecute(hartId: Int, id: Long, addr: Long, len: Long, data: Array[Byte]): Unit =
    loads(id) = (resolveAddress(true, id, addr), len, bytes(data, len))
  override def loadCommit(hartId: Int, id: Long): Unit = load = loads.remove(id)
  override def storeExecute(hartId: Int, id: Long, addr: Long, len: Long, data: Array[Byte]): Unit = {
    stores(id) = (resolveAddress(false, id, addr), len, bytes(data, len))
    physicalStores(id) = addr
  }
  override def storeCommit(hartId: Int, id: Long): Unit = {
    store = stores.remove(id)
    storePhysical = physicalStores.remove(id)
  }
  override def storeConditional(hartId: Int, failure: Boolean): Unit =
    if (failure) store = None
  override def ioAccess(hartId: Int, access: TraceIo): Unit =
    if (!access.error) io.enqueue((access.write, access.address, access.size, bytes(access.data, access.size)))

  override def newCpuMemoryView(viewId: Int, readIds: Long, writeIds: Long): Unit = ()
  override def newCpu(hartId: Int, isa: String, priv: String, physWidth: Int, pmpNum: Int, triggerCount: Int,
                      asidWidth: Int, memoryViewId: Int): Unit = ()
  override def loadElf(offset: Long, path: File): Unit = ()
  override def loadBin(offset: Long, path: File): Unit = ()
  override def loadBytes(offset: Long, bytes: Array[Byte]): Unit = ()
  override def setPc(hartId: Int, pc: Long): Unit = ()
  override def setRegister(hartId: Int, id: Int, value: Long): Unit = ()
  override def readRf(hardId: Int, rfKind: Int, address: Int, data: Array[Byte]): Unit = ()
  override def setInterrupt(hartId: Int, intId: Int, value: Boolean): Unit = ()
  override def addRegion(hartId: Int, kind: Int, base: Long, size: Long): Unit = ()
  override def loadFlush(hartId: Int): Unit = ()
  override def storeBroadcast(hartId: Int, id: Long): Unit = ()
  override def time(value: Long): Unit = ()
  override def flush(): Unit = ()
  override def close(): Unit = ()
}

object C2Backend {
  /** RVFI source register fields for the RV32I/M base opcodes; 0 when the format has no such source. */
  def sources(insn: Long): (Int, Int) = {
    val rs1 = ((insn >> 15) & 31).toInt
    val rs2 = ((insn >> 20) & 31).toInt
    (insn & 0x7f).toInt match {
      case 0x33 | 0x3b | 0x23 | 0x63 | 0x2f => (rs1, rs2)
      case 0x07 | 0x27 => (rs1, 0)
      case 0x53 if Set(0x68L, 0x69L, 0x78L, 0x79L)(insn >> 25) => (rs1, 0)
      case 0x13 | 0x1b | 0x03 | 0x67 => (rs1, 0)
      case 0x73 if Set(1, 2, 3)(((insn >> 12) & 7).toInt) => (rs1, 0)
      case _ => (0, 0)
    }
  }

  private def signed(v: Long, bits: Int): Long = (v << (64 - bits)) >> (64 - bits)

  /** The architectural next pc of `r` from its own bits and source values. */
  def fallThrough(r: RvfiRecord, xlen: Int): BigInt = {
    val insn = r.insn
    val pc = r.pc
    if ((insn & 3) != 3) return pc + 2
    (insn & 0x7f).toInt match {
      case 0x6f =>
        val imm = ((insn >> 31) & 1) << 20 | ((insn >> 12) & 0xff) << 12 | ((insn >> 20) & 1) << 11 | ((insn >> 21) & 0x3ff) << 1
        pc + signed(imm, 21)
      case 0x67 => (r.rs1Rdata + signed(insn >> 20, 12)) & ~BigInt(1)
      case 0x63 =>
        val imm = ((insn >> 31) & 1) << 12 | ((insn >> 7) & 1) << 11 | ((insn >> 25) & 0x3f) << 5 | ((insn >> 8) & 0xf) << 1
        val (a, b) = (r.rs1Rdata, r.rs2Rdata)
        def s(v: BigInt) = if (v.testBit(xlen - 1)) v - (BigInt(1) << xlen) else v
        val taken = ((insn >> 12) & 7).toInt match {
          case 0 => a == b
          case 1 => a != b
          case 4 => s(a) < s(b)
          case 5 => s(a) >= s(b)
          case 6 => a < b
          case 7 => a >= b
          case _ => false
        }
        if (taken) pc + signed(imm, 13) else pc + 4
      case _ => pc + 4
    }
  }
}
