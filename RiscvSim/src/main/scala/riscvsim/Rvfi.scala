package riscvsim

import java.io.{BufferedWriter, File, FileWriter, PrintWriter}

import spinal.core._
import spinal.core.sim._

/** Architectural floating-point state after one retirement. FLEN is 64. */
case class RvfiFpState(valid: Boolean, destination: Int, data: BigInt, flags: BigInt, fcsr: BigInt) {
  require(destination >= 0 && destination < 32)
  require(flags >= 0 && flags < 32 && fcsr >= 0 && fcsr < 256 && (fcsr & 31) == flags)
  def fields: ujson.Obj = ujson.Obj("fd_valid" -> valid, "fd" -> destination,
    "fd_wdata" -> Hex(data), "fflags" -> Hex(flags), "fcsr" -> Hex(fcsr))
}

/** One RVFI retirement record (riscv-formal names, without the rvfi_ prefix). */
case class RvfiRecord(order: BigInt, cycle: Long, insn: Long, trap: Boolean, halt: Boolean, intr: Boolean,
                      mode: Int, ixl: Int,
                      rs1: Int, rs1Rdata: BigInt, rs2: Int, rs2Rdata: BigInt, rd: Int, rdWdata: BigInt,
                      pc: BigInt, pcNext: BigInt,
                      memAddr: BigInt, memRmask: Int, memWmask: Int, memRdata: BigInt, memWdata: BigInt,
                      memFault: Boolean, csrState: Map[Int, BigInt] = Map.empty, fpState: Option[RvfiFpState] = None,
                      extra: Seq[(String, ujson.Value)] = Nil) {
  require(extra.forall { case (k, _) => k.nonEmpty && !k.contains('"') && !k.contains('\\') }, "invalid extra C2 field name")
  /** One C2 (`rvw.rvfi/1`) JSONL line. */
  def toJson: String = {
    val sb = new StringBuilder(400)
    sb ++= "{\"order\": " ++= order.toString ++= ", \"cycle\": " ++= cycle.toString
    sb ++= ", \"pc\": \"" ++= Hex(pc) ++= "\", \"pc_next\": \"" ++= Hex(pcNext)
    sb ++= "\", \"insn\": \"" ++= Hex(insn) ++= "\", \"mode\": " ++= mode.toString
    sb ++= ", \"trap\": " ++= trap.toString ++= ", \"intr\": " ++= intr.toString ++= ", \"halt\": " ++= halt.toString
    sb ++= ", \"rs1\": " ++= rs1.toString ++= ", \"rs1_rdata\": \"" ++= Hex(rs1Rdata)
    sb ++= "\", \"rs2\": " ++= rs2.toString ++= ", \"rs2_rdata\": \"" ++= Hex(rs2Rdata)
    sb ++= "\", \"rd\": " ++= rd.toString ++= ", \"rd_wdata\": \"" ++= Hex(rdWdata)
    sb ++= "\", \"mem_addr\": \"" ++= Hex(memAddr) ++= "\", \"mem_rmask\": " ++= memRmask.toString
    sb ++= ", \"mem_wmask\": " ++= memWmask.toString ++= ", \"mem_rdata\": \"" ++= Hex(memRdata)
    sb ++= "\", \"mem_wdata\": \"" ++= Hex(memWdata) ++= "\", \"mem_fault\": " ++= memFault.toString ++= "}"
    if (csrState.nonEmpty) {
      sb.setLength(sb.length - 1)
      sb ++= ", \"csr_state\": {"
      sb ++= csrState.toSeq.sortBy(_._1).map { case (address, value) =>
        "\"" + Hex(BigInt(address)) + "\": \"" + Hex(value) + "\""
      }.mkString(", ")
      sb ++= "}}"
    }
    if (extra.nonEmpty) {
      // Optional C2 fields that the adapter observed (for example `mmu_walks`), appended in order.
      sb.setLength(sb.length - 1)
      extra.foreach { case (k, v) => sb ++= ", \"" ++= k ++= "\": " ++= ujson.write(v) }
      sb ++= "}"
    }
    fpState match {
      case None => sb.toString
      case Some(fp) =>
        val row = ujson.read(sb.toString).obj
        fp.fields.obj.foreach { case (k, v) => row(k) = v }
        ujson.write(ujson.Obj.from(row))
    }
  }
}

/**
 * Reads RVFI channels from a running simulation. Each channel is any Spinal Bundle whose
 * fields use riscv-formal's names, with or without the `rvfi_` prefix (`valid`, `order`,
 * `insn`, `pc_rdata`, `rd_wdata`, ...). `mem_fault` and `ixl` are optional.
 */
class RvfiProbe(channels: Seq[Bundle], csrSlots: Seq[Map[Int, Data]] = Seq.empty) {
  require(csrSlots.isEmpty || csrSlots.size == channels.size,
    "CSR observations require one map per RVFI slot")
  require(csrSlots.isEmpty || csrSlots.map(_.keySet).distinct.size == 1,
    "all RVFI slots must expose the same CSR set")
  require(csrSlots.forall(_.keys.forall(a => a >= 0 && a < 4096)), "invalid CSR address")

  private class Channel(b: Bundle, csrs: Map[Int, Data]) {
    private val byName: Map[String, Data] = b.elements.map { case (n, d) => n.stripPrefix("rvfi_") -> d }.toMap
    private def get(n: String): Data = byName.getOrElse(n, throw new IllegalArgumentException(
      s"RVFI channel ${b.getName()} has no field '$n' (fields: ${byName.keys.mkString(", ")})"))
    private def opt(n: String): Option[Data] = byName.get(n)
    val valid = get("valid").asInstanceOf[Bool]
    private val fields = Seq("order", "insn", "trap", "halt", "intr", "mode", "rs1_addr", "rs2_addr", "rs1_rdata",
      "rs2_rdata", "rd_addr", "rd_wdata", "pc_rdata", "pc_wdata", "mem_addr", "mem_rmask", "mem_wmask", "mem_rdata",
      "mem_wdata").map(n => n -> get(n)).toMap
    private val memFault = opt("mem_fault")
    private val ixl = opt("ixl")

    private def big(d: Data): BigInt = d match {
      case b: Bool => if (b.toBoolean) 1 else 0
      case v: BitVector => v.toBigInt
    }
    private def bool(n: String) = big(fields(n)) != 0
    private def int(n: String) = big(fields(n)).toInt
    private def num(n: String) = big(fields(n))

    def read(cycle: Long): RvfiRecord = RvfiRecord(
      order = num("order"), cycle = cycle, insn = num("insn").toLong, trap = bool("trap"), halt = bool("halt"),
      intr = bool("intr"), mode = int("mode"), ixl = ixl.map(d => big(d).toInt).getOrElse(0),
      rs1 = int("rs1_addr"), rs1Rdata = num("rs1_rdata"), rs2 = int("rs2_addr"), rs2Rdata = num("rs2_rdata"),
      rd = int("rd_addr"), rdWdata = num("rd_wdata"), pc = num("pc_rdata"), pcNext = num("pc_wdata"),
      memAddr = num("mem_addr"), memRmask = int("mem_rmask"), memWmask = int("mem_wmask"),
      memRdata = num("mem_rdata"), memWdata = num("mem_wdata"), memFault = memFault.exists(d => big(d) != 0),
      csrState = csrs.map { case (address, signal) => address -> big(signal) })
  }

  private val chans = channels.zipWithIndex.map { case (channel, slot) =>
    new Channel(channel, if (csrSlots.isEmpty) Map.empty else csrSlots(slot))
  }

  /** The records retiring this cycle, in `order`. */
  def sample(cycle: Long): Seq[RvfiRecord] = {
    var out = List.empty[RvfiRecord]
    for (c <- chans) if (c.valid.toBoolean) out ::= c.read(cycle)
    if (out.lengthCompare(1) > 0) out.sortBy(_.order) else out
  }
}

/**
 * Writes a C2 RVFI trace (`rvw.rvfi/1` JSONL): a header line, then one record per retired
 * instruction in `order`, with optional `"event"` records (trap, irq, end) in between.
 * Counts records and order gaps (an order that is not the previous one plus one).
 * Cycles never decrease in the file (C2 requires it); a write that would break this fails.
 */
class RvfiTraceWriter(file: File, header: ujson.Obj,
                      flushEachRecord: Boolean = sys.env.get("RVW_RVFI_FLUSH").contains("1"),
                      resume: Option[ujson.Value] = None,
                      observe: Option[String => Unit] = None) extends AutoCloseable {
  require(resume.isEmpty || (!sys.env.contains("RVW_COSIM_PORT") && observe.isEmpty),
    "lockstep cannot resume without a reference checkpoint")
  // Validate the captured prefix before opening or replacing the output.
  private val restored = resume.map(RvfiWriterCheckpoint.decode(_, header))
  file.getAbsoluteFile.getParentFile.mkdirs()
  restored.foreach(s => java.nio.file.Files.write(file.toPath, s.prefix))
  private val w = new PrintWriter(new java.io.OutputStreamWriter(
    new java.io.FileOutputStream(file, restored.nonEmpty), java.nio.charset.StandardCharsets.UTF_8))
  private val lockstep = sys.env.get("RVW_COSIM_PORT").filter(_ => observe.isEmpty).map(p => new Lockstep(p.toInt))
  private def emit(line: String): Unit = {
    w.println(line)
    if (flushEachRecord || lockstep.nonEmpty || observe.nonEmpty) w.flush()
    lockstep.foreach(_.observe(line))
    observe.foreach(_(line))
  }
  private val snapshot = header.value.get("csr_snapshot").map(_.arr.map(_.str).toSet).getOrElse(Set.empty[String])
  private val schema = if (snapshot.nonEmpty || header.value.get("capabilities").exists(_.arr.contains(ujson.Str("state")))) "rvw.rvfi/2" else "rvw.rvfi/1"
  require(!header.value.contains("schema"), "trace writer selects the schema")
  private val supplied = if (snapshot.nonEmpty && !header.value.contains("capabilities"))
    header.value.toSeq :+ ("capabilities" -> ujson.Arr("csr")) else header.value.toSeq
  if (restored.isEmpty)
    emit(ujson.write(ujson.Obj.from(Seq("schema" -> ujson.Str(schema)) ++ supplied)))
  if (flushEachRecord) w.flush()
  var records = restored.map(_.records).getOrElse(0L)
  var trapRecords = restored.map(_.traps).getOrElse(0L)
  var orderGaps = restored.map(_.gaps).getOrElse(0L)
  private var nextOrder: BigInt = restored.map(_.nextOrder).getOrElse(BigInt(-1))
  private var lastCycle = restored.map(_.lastCycle).getOrElse(-1L)
  private var pending: Option[(Long, BigInt, Boolean)] = restored.flatMap(_.pending)
  private var ended = false

  /** Call only while the adapter has stopped all writers at a cycle boundary.
    * Prefix bytes and pending late-tval events belong to the same snapshot. */
  def checkpoint(): ujson.Value = {
    require(!ended, "cannot checkpoint an ended C2 writer")
    w.flush()
    require(!w.checkError(), "C2 flush failed")
    val bytes = java.nio.file.Files.readAllBytes(file.toPath)
    ujson.Obj("schema" -> "rvw.rvfi-writer/1", "header" -> header,
      "prefix" -> java.util.Base64.getEncoder.encodeToString(bytes),
      "sha256" -> RvfiWriterCheckpoint.digest(bytes), "position" -> bytes.length.toString,
      "records" -> records.toString, "traps" -> trapRecords.toString,
      "gaps" -> orderGaps.toString, "next_order" -> nextOrder.toString,
      "last_cycle" -> lastCycle.toString,
      "pending" -> pending.map { case (c, cause, intr) =>
        ujson.Arr(c.toString, cause.toString, intr) }.getOrElse(ujson.Null))
  }

  private def at(cycle: Long): Unit = {
    require(!ended, "C2 writer has ended")
    if (cycle < lastCycle) throw new IllegalStateException(s"C2 cycles must not decrease: $cycle after $lastCycle")
    lastCycle = cycle
  }

  def write(r: RvfiRecord): Unit = {
    require(r.fpState.nonEmpty == header.value.get("capabilities").exists(_.arr.contains(ujson.Str("state"))),
      "FP state must match the declared state capability")
    require(r.csrState.keySet.map(a => Hex(BigInt(a))) == snapshot,
      "CSR state must contain exactly the header snapshot set")
    at(r.cycle)
    if (nextOrder >= 0 && r.order != nextOrder) orderGaps += 1
    nextOrder = r.order + 1
    records += 1
    if (r.trap) trapRecords += 1
    emit(r.toJson)
    if (flushEachRecord) w.flush()
  }

  def trap(cycle: Long, cause: BigInt, tval: BigInt, intr: Boolean): Unit = {
    at(cycle)
    emit(s"""{"event": "trap", "cycle": $cycle, "cause": "${Hex(cause)}", "tval": "${Hex(tval)}", "intr": $intr}""")
    if (flushEachRecord) w.flush()
  }

  /** Interrupt input levels (in their `mip` bit positions) the harness drives from `cycle` on. */
  def irq(cycle: Long, levels: BigInt): Unit = {
    at(cycle)
    emit(s"""{"event": "irq", "cycle": $cycle, "levels": "${Hex(levels)}"}""")
    if (flushEachRecord) w.flush()
  }

  /** A trap seen at `cycle` whose tval is only known one cycle later. The next `cycle` call writes it. */
  def trapNextCycle(cycle: Long, cause: BigInt, intr: Boolean): Unit = {
    if (pending.nonEmpty) throw new IllegalStateException("a trap event is already waiting for its tval")
    pending = Some((cycle, cause, intr))
  }

  /**
   * Writes one sampled cycle: first a trap event waiting for its tval (with its own, earlier
   * cycle, and `lateTval` read now), then the records that retired this cycle. Writing the
   * waiting trap first keeps cycles nondecreasing when an instruction retires the cycle after a trap.
   */
  def cycle(records: Seq[RvfiRecord], lateTval: => BigInt): Unit = {
    for ((c, cause, intr) <- pending) trap(c, cause, lateTval, intr)
    pending = None
    records.foreach(write)
  }

  /** Ends the trace. A trap still waiting for its tval is written with `tval` (the run ended first). */
  def end(cycle: Long, status: String, tval: BigInt = 0): Unit = {
    for ((c, cause, intr) <- pending) trap(c, cause, tval, intr)
    pending = None
    at(cycle)
    emit(s"""{"event": "end", "cycle": $cycle, "status": "$status"}""")
    ended = true
    if (flushEachRecord) w.flush()
  }

  def close(): Unit = {
    try w.close() finally lockstep.foreach(_.close())
  }
}

/** Serialized writer state. The outer native envelope binds this to the model. */
private[riscvsim] object RvfiWriterCheckpoint {
  case class State(prefix: Array[Byte], records: Long, traps: Long, gaps: Long,
                   nextOrder: BigInt, lastCycle: Long, pending: Option[(Long, BigInt, Boolean)])
  def digest(bytes: Array[Byte]): String = java.security.MessageDigest.getInstance("SHA-256")
    .digest(bytes).map(b => f"${b & 0xff}%02x").mkString
  def decode(v: ujson.Value, header: ujson.Obj): State = {
    require(v("schema").str == "rvw.rvfi-writer/1", "unsupported C2 writer snapshot")
    require(v("header") == header, "C2 snapshot header mismatch")
    val prefix = java.util.Base64.getDecoder.decode(v("prefix").str)
    require(prefix.length.toString == v("position").str && digest(prefix) == v("sha256").str,
      "C2 snapshot prefix mismatch")
    val records = v("records").str.toLong
    val traps = v("traps").str.toLong
    val gaps = v("gaps").str.toLong
    require(records >= 0 && traps >= 0 && traps <= records && gaps >= 0 && gaps <= records,
      "invalid C2 snapshot counters")
    val pending = if (v("pending") == ujson.Null) None else {
      val a = v("pending").arr
      require(a.size == 3, "invalid pending C2 trap")
      Some((a(0).str.toLong, BigInt(a(1).str), a(2).bool))
    }
    State(prefix, records, traps, gaps, BigInt(v("next_order").str), v("last_cycle").str.toLong, pending)
  }
}
