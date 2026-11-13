package rvwsmp

import java.io.File
import rvls.spinal.{TraceBackend, TraceIo}
import vexiiriscv.test.VexiiRiscvProbe
import riscvsim.{RvfiRecord, RvfiTraceWriter}
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
                onStore: (BigInt, Int, BigInt) => Unit, onCommit: RvfiRecord => Unit = _ => ()) extends TraceBackend {
  private val mask = (BigInt(1) << xlen) - 1
  val regs: Array[BigInt] = Array.fill(32)(BigInt(0))
  var retired = 0L
  var traps = 0L
  private var order = BigInt(0)
  private var handler = false
  private var pending: Option[RvfiRecord] = None
  def pendingCycle: Option[Long] = pending.map(_.cycle)

  private var rdData: Option[BigInt] = None
  private val loads = mutable.LongMap.empty[(Long, Long, BigInt)]
  private val stores = mutable.LongMap.empty[(Long, Long, BigInt)]
  private var load: Option[(Long, Long, BigInt)] = None
  private var store: Option[(Long, Long, BigInt)] = None

  private def bytes(data: Array[Byte], len: Long): BigInt =
    (0 until len.toInt).foldLeft(BigInt(0))((v, i) => v | (BigInt(data(i) & 0xff) << (8 * i)))

  private def emit(next: BigInt): Unit = {
    pending.foreach(r => sink(r.copy(pcNext = next & mask)))
    pending = None
  }

  /** Writes the buffered record with its decoded fall-through target. Call at the end of a run. */
  def drain(): Unit = pending.foreach(r => emit(C2Backend.fallThrough(r, xlen)))

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
    val (memAddr, rmask, rdataMem, wmask, wdataMem) = (load, store) match {
      case (Some((a, n, d)), None) => (BigInt(a), ((1 << n) - 1).toInt, d, 0, BigInt(0))
      case (None, Some((a, n, d))) => (BigInt(a), 0, BigInt(0), ((1 << n) - 1).toInt, d)
      case (None, None) => (BigInt(0), 0, BigInt(0), 0, BigInt(0))
      case (Some((a, n, d)), Some((b, m, w))) =>
        require(a == b && n == m, "atomic effects disagree")
        (BigInt(a), ((1 << n) - 1).toInt, d, ((1 << m) - 1).toInt, w)
    }
    val r = RvfiRecord(order, cycle(), insn, trap = false, halt = false, intr = handler, mode = mode(), ixl = 2,
      rs1 = rs1, rs1Rdata = regs(rs1), rs2 = rs2, rs2Rdata = regs(rs2), rd = rd, rdWdata = wdata,
      pc = pcValue, pcNext = 0, memAddr = memAddr, memRmask = rmask, memWmask = wmask,
      memRdata = rdataMem, memWdata = wdataMem, memFault = false)
    if (rd != 0) regs(rd) = wdata
    order += 1
    retired += 1
    handler = false
    rdData = None; load = None
    pending = Some(r)
    onCommit(r)
    store.foreach { case (a, n, d) => onStore(BigInt(a), Integer.numberOfTrailingZeros(n.toInt), d) }
    store = None
  }

  override def trap(hartId: Int, interrupt: Boolean, code: Int): Unit = {
    val (epc, tval) = nextTrap()
    emit(epc)
    val cause = if (interrupt) (BigInt(1) << (xlen - 1)) | code else BigInt(code)
    trapSink(cycle(), cause, tval & mask, interrupt)
    traps += 1
    handler = true
    rdData = None; load = None; store = None
  }

  override def writeRf(hartId: Int, rfKind: Int, address: Int, data: Array[Byte]): Unit =
    if (rfKind == 0) rdData = Some(bytes(data, xlen / 8))
  override def loadExecute(hartId: Int, id: Long, addr: Long, len: Long, data: Array[Byte]): Unit =
    loads(id) = (addr, len, bytes(data, len))
  override def loadCommit(hartId: Int, id: Long): Unit = load = loads.remove(id)
  override def storeExecute(hartId: Int, id: Long, addr: Long, len: Long, data: Array[Byte]): Unit =
    stores(id) = (addr, len, bytes(data, len))
  override def storeCommit(hartId: Int, id: Long): Unit = store = stores.remove(id)
  override def storeConditional(hartId: Int, failure: Boolean): Unit =
    if (failure) store = None
  override def ioAccess(hartId: Int, access: TraceIo): Unit =
    access match {
      case observed: VexiiRiscvProbe#ProbeTraceLsu =>
        require(!observed.error, "faulting MMIO capture is unsupported")
        if(!observed.write) loads(observed.uopId & 0xF) =
          (observed.address, observed.size.toLong, bytes(observed.data, observed.size))
      case _ => throw new IllegalArgumentException("expected upstream observed LSU transaction")
    }

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
