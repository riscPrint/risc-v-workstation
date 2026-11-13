package riscvsim

import scala.collection.mutable

/** Associate observed FP state writes with retirement order.
  * The clock monitor checks actual CSR storage against the observed write ports.
  * The projection uses those checked effects, never reference-simulator values.
  */
class FpCommitState(xlen: Int) {
  require(xlen == 32 || xlen == 64)
  private val fsMask = BigInt(3) << 13
  private val stateMask = fsMask | (BigInt(1) << (xlen - 1))
  private case class Effect(var flags: BigInt = 0, var fcsr: Option[BigInt] = None,
                            var dirty: Boolean = false, var status: Option[BigInt] = None)
  private case class Actions(flags: Seq[(Long, BigInt)], csrs: Seq[(Long, Int, BigInt)], dirty: Seq[Long])
  private val allocated = mutable.Map.empty[Int, Long]
  private val effects = mutable.LongMap.empty[Effect]
  private val retired = mutable.Set.empty[Long]
  private val orders = mutable.Map.empty[BigInt, Long]
  private var serial = 0L
  private var previous = Option.empty[(BigInt, BigInt)]
  private var sealedState = false
  private var projectedFcsr = BigInt(0)
  private var projectedState = BigInt(0)
  private var nextOrder = BigInt(0)

  def allocate(id: Int): Unit = { allocated(id) = serial; serial += 1 }
  private def tag(id: Int): Long = allocated.getOrElse(id,
    throw new IllegalStateException(s"FP effect without allocated micro-op $id"))
  private def effect(id: Long): Effect = effects.getOrElseUpdate(id, Effect())

  def retire(order: BigInt, id: Int): Unit = {
    require(!orders.contains(order), "duplicate FP retirement order")
    orders(order) = tag(id)
    retired += tag(id)
  }

  /** Actual CSR storage and registered write metadata from the same clock edge.
    * Values on the write port must be the core's accepted CSR values.
    */
  def observe(fcsr: BigInt, status: BigInt, flags: Seq[(Int, BigInt)],
              csrs: Seq[(Int, Int, BigInt)], dirty: Seq[Int]): Unit = {
    require(!sealedState, "FP state received after trace seal")
    val actions = Actions(flags.map { case (id, value) => tag(id) -> value },
      csrs.map { case (id, address, value) => (tag(id), address, value) }, dirty.map(tag))
    require(fcsr >= 0 && fcsr < 256)
    require(flags.forall(e => e._2 >= 0 && e._2 < 32))
    previous match {
      case None =>
        require(flags.isEmpty && csrs.isEmpty && dirty.isEmpty, "FP capture started after a state write")
        projectedFcsr = fcsr
        projectedState = status & stateMask
      case Some((before, oldStatus)) =>
        val fcsrWriters = actions.csrs.filter(_._2 != 0x300).map(_._1).toSet
        require(!fcsrWriters.exists(id => actions.flags.exists(_._1 != id)),
          "overlapping CSR and FP writes have no separate physical state snapshot")
        val statusWriters = actions.csrs.filter(_._2 == 0x300).map(_._1).toSet
        require(!statusWriters.exists(id => actions.dirty.exists(_ != id)),
          "overlapping status and dirty writes have no separate physical state snapshot")
        var expected = before
        actions.csrs.foreach { case (_, address, value) => address match {
          case 1 => expected = (expected & ~BigInt(31)) | (value & 31)
          case 2 => expected = (expected & 31) | ((value & 7) << 5)
          case 3 => expected = value & 255
          case 0x300 =>
          case _ => throw new IllegalStateException("unexpected CSR on FP capture port")
        }}
        expected |= actions.flags.foldLeft(BigInt(0))(_ | _._2)
        require(fcsr == expected,
          s"FP storage differs from observed write ports: expected ${Hex(expected)}, actual ${Hex(fcsr)}")
        val writesStatus = actions.csrs.filter(_._2 == 0x300)
        if (actions.dirty.nonEmpty && writesStatus.isEmpty)
          require((status & stateMask) == stateMask, "FS dirty request did not update actual FS and SD storage")
        else if (actions.dirty.isEmpty && writesStatus.isEmpty)
          require((status & stateMask) == (oldStatus & stateMask), "unobserved FS or SD storage change")
        actions.flags.foreach { case (id, value) => effect(id).flags |= value }
        actions.csrs.foreach { case (id, address, _) =>
          if (address == 0x300) effect(id).status = Some(status & stateMask)
          else effect(id).fcsr = Some(fcsr)
        }
        actions.dirty.foreach(id => effect(id).dirty = true)
    }
    previous = Some((fcsr, status))
  }

  def finish(pending: Boolean = false): Unit = {
    require(!pending, "FP state writes are still pending at end of run")
    require(effects.keysIterator.forall(retired.contains), "FP state effect belongs to an unretired micro-op")
    sealedState = true
  }

  def validateFinal(): Unit = previous.foreach { case (fcsr, status) =>
    require(projectedFcsr == fcsr, "projected FCSR differs from final actual storage")
    require(projectedState == (status & stateMask), "projected FS differs from final actual storage")
  }

  /** Call in retirement order after the run has drained the observed writes. */
  def project(record: RvfiRecord): RvfiRecord = {
    require(sealedState, "FP state is not sealed")
    require(record.order == nextOrder, "FP records must be projected in retirement order")
    nextOrder += 1
    val id = orders.remove(record.order).getOrElse(throw new IllegalStateException("missing FP retirement tag"))
    val e = effects.remove(id).getOrElse(Effect())
    projectedFcsr = e.fcsr.getOrElse(projectedFcsr | e.flags)
    if (e.dirty) projectedState = stateMask
    e.status.foreach(value => projectedState = value)
    val raw = record.csrState.getOrElse(0x300, throw new IllegalStateException("FP capture needs mstatus"))
    record.copy(csrState = record.csrState.updated(0x300, (raw & ~stateMask) | projectedState),
      fpState = record.fpState.map(fp => fp.copy(flags = projectedFcsr & 31, fcsr = projectedFcsr)))
  }
}
