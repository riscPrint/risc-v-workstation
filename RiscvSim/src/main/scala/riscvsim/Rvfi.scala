package riscvsim

import java.io.{BufferedWriter, File, FileWriter, PrintWriter}

import spinal.core._
import spinal.core.sim._

/** One RVFI retirement record (riscv-formal names, without the rvfi_ prefix). */
case class RvfiRecord(order: BigInt, cycle: Long, insn: Long, trap: Boolean, halt: Boolean, intr: Boolean,
                      mode: Int, ixl: Int,
                      rs1: Int, rs1Rdata: BigInt, rs2: Int, rs2Rdata: BigInt, rd: Int, rdWdata: BigInt,
                      pc: BigInt, pcNext: BigInt,
                      memAddr: BigInt, memRmask: Int, memWmask: Int, memRdata: BigInt, memWdata: BigInt,
                      memFault: Boolean) {
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
    sb.toString
  }
}

/**
 * Reads RVFI channels from a running simulation. Each channel is any Spinal Bundle whose
 * fields use riscv-formal's names, with or without the `rvfi_` prefix (`valid`, `order`,
 * `insn`, `pc_rdata`, `rd_wdata`, ...). `mem_fault` and `ixl` are optional.
 */
class RvfiProbe(channels: Seq[Bundle]) {
  private class Channel(b: Bundle) {
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
      memRdata = num("mem_rdata"), memWdata = num("mem_wdata"), memFault = memFault.exists(d => big(d) != 0))
  }

  private val chans = channels.map(new Channel(_))

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
class RvfiTraceWriter(file: File, header: ujson.Obj) extends AutoCloseable {
  file.getAbsoluteFile.getParentFile.mkdirs()
  private val w = new PrintWriter(new BufferedWriter(new FileWriter(file), 1 << 20))
  w.println(ujson.write(ujson.Obj.from(Seq("schema" -> ujson.Str("rvw.rvfi/1")) ++ header.value)))
  var records = 0L
  var trapRecords = 0L
  var orderGaps = 0L
  private var nextOrder: BigInt = -1
  private var lastCycle = -1L
  private var pending: Option[(Long, BigInt, Boolean)] = None

  private def at(cycle: Long): Unit = {
    if (cycle < lastCycle) throw new IllegalStateException(s"C2 cycles must not decrease: $cycle after $lastCycle")
    lastCycle = cycle
  }

  def write(r: RvfiRecord): Unit = {
    at(r.cycle)
    if (nextOrder >= 0 && r.order != nextOrder) orderGaps += 1
    nextOrder = r.order + 1
    records += 1
    if (r.trap) trapRecords += 1
    w.println(r.toJson)
  }

  def trap(cycle: Long, cause: BigInt, tval: BigInt, intr: Boolean): Unit = {
    at(cycle)
    w.println(s"""{"event": "trap", "cycle": $cycle, "cause": "${Hex(cause)}", "tval": "${Hex(tval)}", "intr": $intr}""")
  }

  /** Interrupt input levels (in their `mip` bit positions) the harness drives from `cycle` on. */
  def irq(cycle: Long, levels: BigInt): Unit = {
    at(cycle)
    w.println(s"""{"event": "irq", "cycle": $cycle, "levels": "${Hex(levels)}"}""")
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
    w.println(s"""{"event": "end", "cycle": $cycle, "status": "$status"}""")
  }

  def close(): Unit = w.close()
}
