package rvwvexii

import riscvsim.Hex

/** Compact reference inputs. This is not a retirement trace. Ordinary RAM
  * traffic and deterministic register writes are not retained. */
final class BootInputs(restored: Option[ujson.Value], requested: Option[Boolean]) {
  private val value = restored.getOrElse(ujson.Obj("schema" -> "rvw.boot-reference-inputs/1",
    "enabled" -> ujson.Bool(requested.getOrElse(false)), "next_seq" -> "0", "last_levels" -> ujson.Null,
    "external" -> ujson.Arr(), "counters" -> ujson.Arr(), "traps" -> ujson.Arr()))
  require(value("schema").str == "rvw.boot-reference-inputs/1")
  val enabled = value("enabled").bool
  require(requested.forall(_ == enabled), "reference input capture must keep its reset-time setting")
  private val external = value("external").arr
  private var sequence = value("next_seq").str.toLong
  private var levels: Option[String] = if (value("last_levels") == ujson.Null) None else Some(value("last_levels").str)
  def snapshot: ujson.Value = value
  private def event(cycle: Long, order: BigInt, kind: String, fields: (String,ujson.Value)*): ujson.Value = {
    val row = ujson.Obj.from(Seq("event" -> ujson.Str("external_interrupt"),
      "seq" -> ujson.Num(sequence), "cycle" -> ujson.Num(cycle), "before_order" -> ujson.Num(order.toLong),
      "kind" -> ujson.Str(kind)) ++ fields)
    if (enabled) {
      external += row; sequence += 1; value("next_seq") = sequence.toString
    }
    row
  }
  def pins(cycle: Long, order: BigInt, bits: BigInt): Option[ujson.Value] = {
    val text = Hex(bits)
    if (levels.contains(text)) None else {
      levels = Some(text)
      value("last_levels") = text
      Some(event(cycle,order,"pins","levels" -> ujson.Str(text)))
    }
  }
  def trap(cycle: Long, order: BigInt, epc: BigInt, cause: BigInt, tval: BigInt): Option[ujson.Value] = {
    if (enabled) value("traps").arr += ujson.Obj("cycle" -> cycle.toString,"order" -> order.toString,
      "epc" -> Hex(epc), "cause" -> Hex(cause), "tval" -> Hex(tval))
    if (cause.testBit(63)) Some(event(cycle,order,"taken","cause" -> ujson.Str(Hex(cause)))) else None
  }
  def mmio(cycle: Long, order: BigInt, pc: BigInt, insn: Long, physical: Long,
           address: BigInt, read: BigInt, write: BigInt, rmask: Int, wmask: Int): ujson.Value = {
    require((rmask == 0) != (wmask == 0), "reference MMIO needs one direction")
    val size = Integer.bitCount(rmask | wmask)
    event(cycle,order,"mmio", "address" -> ujson.Str(Hex(BigInt(physical))),
      "virtual_address" -> ujson.Str(Hex(address)), "value" -> ujson.Str(Hex(if (wmask != 0) write else read)),
      "write" -> ujson.Bool(wmask != 0), "bytes" -> ujson.Num(size),
      "pc" -> ujson.Str(Hex(pc)), "insn" -> ujson.Str(Hex(insn)))
  }
  def counter(cycle: Long, order: BigInt, pc: BigInt, insn: Long, rd: Int, data: BigInt): Unit =
    if (enabled) value("counters").arr += ujson.Obj("cycle" -> cycle.toString,"order" -> order.toString,
      "pc" -> Hex(pc), "insn" -> Hex(insn), "rd" -> rd, "value" -> Hex(data))
}
