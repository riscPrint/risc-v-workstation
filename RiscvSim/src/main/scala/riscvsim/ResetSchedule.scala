package riscvsim

/** Repeated reset pulses. The project binds the pin and samples real state.
  * Memory preservation and bus cancellation belong to the adapter callbacks.
  * A requested pulse is never a reference comparison or a reset-state pass.
  */
final class ResetSchedule(assertClocks: Int, delayClocks: Int,
    drive: Boolean => Unit, sample: () => ujson.Obj, prepare: () => Unit,
    released: () => Unit) {
  require(assertClocks >= 2 && assertClocks <= 1024, "reset assert_clocks must be 2..1024")
  require(delayClocks >= 1 && delayClocks <= 1024, "reset delay_clocks must be 1..1024")
  private var pending = Option.empty[(Long, Long)]
  private var releaseAt = Option.empty[Long]
  private var observeRelease = false
  private var samples = ujson.Arr()
  val observations = ujson.Arr()
  def active: Boolean = releaseAt.nonEmpty
  def busy: Boolean = pending.nonEmpty || active || observeRelease
  def request(cycle: Long, step: Long): Unit = {
    require(!busy, "reset pulse already pending")
    pending = Some((cycle + delayClocks, step))
  }
  def tick(cycle: Long): Unit = {
    if (observeRelease) {
      val row = sample()
      row("cycle") = RvwJson.num(cycle)
      row("asserted") = ujson.Bool(false)
      samples.value += row
      observations.value += samples
      observeRelease = false
    }
    pending.foreach { case (due, step) =>
      if (cycle >= due) {
        prepare()
        drive(true)
        samples = ujson.Arr()
        releaseAt = Some(cycle + assertClocks)
        pending = None
      }
    }
    releaseAt.foreach { due =>
      // Samples describe edges after reset was asserted, not the edge that requested it.
      if (cycle > due - assertClocks) {
        val row = sample()
        row("cycle") = RvwJson.num(cycle)
        row("asserted") = ujson.Bool(true)
        samples.value += row
      }
      if (cycle >= due) {
        drive(false)
        releaseAt = None
        released()
        observeRelease = true
      }
    }
  }
}
