package riscvsim

import scala.collection.mutable

/** Checks accepted actions at a project-declared serialized memory boundary.
  * Operands and initial bytes must come from independent stimulus/reference state.
  * aq/rl ordering requires a separate execution-graph check. */
final class AtomicMemoryObserver(initial: Seq[Byte], harts: Set[Int], reservationBytes: Int,
                                 maxSpurious: Int, serviceAssumption: String) {
  require(initial.nonEmpty && harts.nonEmpty && reservationBytes >= 8 &&
    (reservationBytes & (reservationBytes - 1)) == 0 && maxSpurious >= 0 && serviceAssumption.trim.nonEmpty)
  private val image = new MemoryImage(initial.size)
  image.write(0, initial, (BigInt(1) << initial.size) - 1)
  private val reservations = mutable.Map.empty[Int, (Int, Int)]
  private val failures = mutable.Map.empty[Int, Int].withDefaultValue(0)
  private var next = 0L
  private def begin(serial: Long, hart: Int, address: Int, width: Int): Unit = {
    require(serial == next && harts(hart), "atomic acceptance order or hart")
    require(Set(4, 8)(width) && address % width == 0, "atomic alignment or width")
    image.read(address, width)
  }
  private def mask(width: Int): BigInt = (BigInt(1) << (8*width)) - 1
  private def value(address: Int, width: Int): BigInt =
    image.read(address, width).zipWithIndex.map { case (b, i) => BigInt(b & 255) << (8*i) }.sum
  private def signed(v: BigInt, width: Int): BigInt =
    if (v.testBit(width*8-1)) v - (BigInt(1) << (width*8)) else v
  private def commit(address: Int, width: Int, data: BigInt): Unit = {
    image.write(address, (0 until width).map(i => ((data >> (8*i)) & 255).toByte), (BigInt(1) << width)-1)
    reservations.keys.toVector.foreach { h =>
      val (start, _) = reservations(h)
      val base = start & -reservationBytes
      if (address.toLong < base.toLong + reservationBytes && base.toLong < address.toLong + width) {
        reservations.remove(h); failures(h) = 0
      }
    }
  }
  def loadReserved(serial: Long, hart: Int, address: Int, width: Int, observed: BigInt): Unit = {
    begin(serial, hart, address, width)
    require((observed & mask(width)) == value(address, width), "LR read mismatch")
    reservations(hart) = address -> width; next += 1
  }
  /** Failed SC must expose unchanged bytes. Success must match a live LR address/width.
    * A bounded service claim applies only to explicitly certified constrained loops. */
  def storeConditional(serial: Long, hart: Int, address: Int, width: Int,
      operand: BigInt, success: Boolean, observedAfter: BigInt, constrained: Boolean): Unit = {
    begin(serial, hart, address, width)
    val live = reservations.get(hart).contains(address -> width)
    require(!success || live, "SC succeeded without valid reservation")
    val wanted = if (success) operand & mask(width) else value(address, width)
    require(observedAfter == wanted, "SC byte effects")
    if (!success && live && constrained) {
      require(failures(hart) < maxSpurious, s"SC bounded service exceeded: $serviceAssumption")
      failures(hart) += 1
    }
    reservations.remove(hart)
    if (success) { commit(address, width, wanted); failures(hart) = 0 }
    next += 1
  }
  def store(serial: Long, hart: Int, address: Int, width: Int, operand: BigInt, observedAfter: BigInt): Unit = {
    begin(serial, hart, address, width)
    require(observedAfter == (operand & mask(width)), "store byte effects")
    commit(address, width, operand); next += 1
  }
  def amo(serial: Long, hart: Int, address: Int, width: Int, operation: String,
          operand: BigInt, observedOld: BigInt, observedAfter: BigInt): Unit = {
    begin(serial, hart, address, width)
    val old = value(address, width); val arg = operand & mask(width)
    val result = operation match {
      case "swap" => arg
      case "add" => old + arg
      case "xor" => old ^ arg
      case "and" => old & arg
      case "or" => old | arg
      case "min" => if (signed(old, width) < signed(arg, width)) old else arg
      case "max" => if (signed(old, width) > signed(arg, width)) old else arg
      case "minu" => old.min(arg)
      case "maxu" => old.max(arg)
      case _ => throw new IllegalArgumentException("unknown AMO operation")
    }
    require((observedOld & mask(width)) == old && observedAfter == (result & mask(width)), "AMO atomic byte effects")
    commit(address, width, result); next += 1
  }
  def compareSwap(serial: Long, hart: Int, address: Int, width: Int, compare: BigInt,
      replacement: BigInt, observedOld: BigInt, observedAfter: BigInt): Unit = {
    // Q-width Zacas is checked here without treating it as a base AMO width.
    require(Set(4, 8, 16)(width) && address % width == 0 && serial == next && harts(hart))
    val old = value(address, width)
    val wanted = if (old == (compare & mask(width))) replacement & mask(width) else old
    require((observedOld & mask(width)) == old && observedAfter == wanted, "CAS atomic byte effects")
    if (old == (compare & mask(width))) commit(address, width, wanted)
    next += 1
  }
  def bytes(address: Int, count: Int): Vector[Byte] = image.read(address, count)
}
