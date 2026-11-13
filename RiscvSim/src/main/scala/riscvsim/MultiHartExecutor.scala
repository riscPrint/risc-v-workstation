package riscvsim

/** Project bindings for one shared memory and a fixed set of independently observed harts.
  * step ends at the project's stable RVFI capture point for the next cycle.
  * completion must mean all earlier effects are drained. park prevents later effects.
  * Boot vectors must be set while reset is held. No callback infers global memory order. */
trait MultiHartBackend {
  def holdReset(hart: Int): Unit
  def writeMemory(address: Long, data: Array[Byte]): Unit
  def boot(hart: Int, entry: Long): Unit
  def release(hart: Int): Unit
  def step(cycle: Long): Unit
  def completion(hart: Int): Option[Status]
  def park(hart: Int): Unit
  /** Optional accepted boundary events. Capture order remains separate from serialization. */
  def observe(cycle: Long, session: MultiHartSession): Unit = ()
}

/** Generic production-harness loop. A project supplies only its signal and memory bindings.
  * The fixed boot-to-completion profile does not implement dynamic HSM transitions. */
object MultiHartExecutor {
  def run(ctx: RunContext, probes: Map[Int, RvfiProbe], backend: MultiHartBackend,
      dependenciesComplete: Boolean = false,
      annotate: (Int, RvfiRecord) => Option[ujson.Obj] = (_, _) => None,
      addressesPhysical: Boolean = false): RunOutcome = {
    val images = ctx.hartImages.getOrElse(throw new IllegalArgumentException("hart images required"))
    val ids = images.harts.map(_._1).sorted
    require(probes.keySet == ids.toSet, "one RVFI probe is required for every image hart")
    require(ctx.job.maxCycles > 0, "positive multi-hart cycle budget required")
    ids.foreach(backend.holdReset)
    // Shared segments load once. No hart can execute while another image is being loaded.
    ctx.loadMemory(backend.writeMemory)
    val session = new MultiHartSession(ctx, probes, dependenciesComplete, annotate, addressesPhysical)
    var cycle = 0L
    val pending = scala.collection.mutable.Set(ids: _*)
    try {
      images.harts.foreach { case (hart, elf) => backend.boot(hart, elf.entry) }
      ids.foreach(session.reset(_, 0))
      ctx.wallClock.start()
      ids.foreach(backend.release)
      def wallExpired: Boolean = ctx.wallClock.expired || ctx.wallClock.over()
      while(pending.nonEmpty && cycle < ctx.job.maxCycles && !wallExpired) {
        cycle += 1
        backend.step(cycle)
        session.sample(cycle)
        backend.observe(cycle, session)
        if(!wallExpired) pending.toSeq.sorted.foreach { hart =>
          backend.completion(hart).foreach { status =>
            backend.park(hart)
            session.complete(hart, cycle, status)
            pending -= hart
          }
        }
      }
      val wallTimeout = pending.nonEmpty && wallExpired
      if(wallTimeout) ctx.wallClock.expired = true
      pending.toSeq.sorted.foreach { hart =>
        backend.park(hart)
        session.complete(hart, cycle, Status.Timeout)
      }
      val outcome = session.outcome(cycle)
      if(wallTimeout) outcome.details("wall_clock_timeout") = true
      outcome
    } finally session.close()
  }
}
