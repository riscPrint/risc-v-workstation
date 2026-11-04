package riscvsim

/** Full input levels, applied after the named sampled edge. Software device levels are
  * replaced while a schedule is selected. The immutable text is part of C1 and replay. */
case class InterruptSchedule(changes: Vector[(Long, BigInt)]) {
  val mask: BigInt = changes.map(_._2).foldLeft(BigInt(0))(_ | _)
  def levelsAt(cycle: Long): BigInt = changes.reverseIterator.find(_._1 <= cycle).map(_._2).getOrElse(BigInt(0))
  def text: String = changes.map { case (c, v) => s"$c:0x${v.toString(16)}" }.mkString(",")
}
object InterruptSchedule {
  def parse(text: String): InterruptSchedule = {
    def bad(): Nothing = throw new Cli.UsageError("--irq-schedule needs increasing CYCLE:0xLEVELS pairs, starting at 1")
    val changes = text.split(",", -1).toVector.map { entry =>
      val pair = entry.split(":", -1)
      if (pair.length != 2 || !pair(0).matches("[0-9]+") || !pair(1).matches("0x[0-9a-fA-F]+")) bad()
      val cycle = try pair(0).toLong catch { case _: NumberFormatException => bad() }
      val levels = BigInt(pair(1).drop(2), 16)
      if (cycle < 1 || levels.bitLength > 64) bad()
      (cycle, levels)
    }
    if (changes.head._1 != 1 || changes.sliding(2).exists(p => p.length == 2 && p(0)._1 >= p(1)._1)) bad()
    InterruptSchedule(changes)
  }
}
