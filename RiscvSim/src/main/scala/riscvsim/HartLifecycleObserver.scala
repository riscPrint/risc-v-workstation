package riscvsim

import scala.collection.mutable

/** Project-normalized HSM lifecycle and shared interrupt-resource checks.
  * This checks observed transitions, not SBI firmware implementation details. */
final class HartLifecycleObserver(harts: Set[Int], bootHarts: Set[Int], transitionBound: Long,
    fairness: String, onReset: Int => Unit = _ => (), requireClaimsDrained: Boolean = true, resetClearsIpi: Boolean = false) {
  require(harts.nonEmpty && bootHarts.subsetOf(harts))
  private val states = mutable.Map(harts.toSeq.map(h => h -> (if (bootHarts(h)) "started" else "stopped")): _*)
  private val epochs = mutable.Map(harts.toSeq.map(_ -> 0): _*)
  private val entries = mutable.Map.empty[Int, (BigInt, BigInt)]
  private val ipis = mutable.Set.empty[Int]
  private val owners = mutable.Map.empty[Int, Int]
  private val progress = new ProgressMonitor(transitionBound, harts.size, fairness)
  private var last = -1L
  private def at(cycle: Long): Unit = { require(cycle >= 0 && cycle >= last); last = cycle; progress.check(cycle) }
  private def known(h: Int): Unit = require(harts(h), "unknown hart")
  def state(hart: Int): String = { known(hart); states(hart) }
  def epoch(hart: Int): Int = { known(hart); epochs(hart) }
  def start(caller: Int, hart: Int, entry: BigInt, opaque: BigInt, cycle: Long): Unit = {
    at(cycle); known(caller); known(hart)
    require(states(caller) == "started" && states(hart) == "stopped", "invalid HSM start")
    require(entry >= 0 && entry % 2 == 0 && opaque >= 0)
    entries(hart) = entry -> opaque
    progress.request(s"hsm-$hart", cycle); states(hart) = "start_pending"
  }
  def started(hart: Int, pc: BigInt, opaque: BigInt, cycle: Long): Unit = {
    at(cycle); known(hart)
    require(states(hart) == "start_pending" && entries(hart) == (pc -> opaque), "hart start entry or opaque mismatch")
    progress.complete(s"hsm-$hart", cycle); states(hart) = "started"
  }
  def stop(hart: Int, cycle: Long): Unit = {
    at(cycle); known(hart); require(states(hart) == "started", "invalid HSM stop")
    require(!requireClaimsDrained || !owners.values.toSet.contains(hart), "hart stopped with claimed shared interrupt")
    progress.request(s"hsm-$hart", cycle); states(hart) = "stop_pending"
  }
  def stopped(hart: Int, cycle: Long): Unit = {
    at(cycle); known(hart); require(states(hart) == "stop_pending", "unsolicited hart stop")
    progress.complete(s"hsm-$hart", cycle); states(hart) = "stopped"
  }
  /** Independent reset ends the pending lifecycle request. Shared IPI state is
    * retained unless the project explicitly declares resetClearsIpi.
    * The adapter callback must clear reservations and other hart-local observers. */
  def reset(hart: Int, cycle: Long, startedAfterReset: Boolean = false): Unit = {
    at(cycle); known(hart)
    require(!requireClaimsDrained || !owners.values.toSet.contains(hart), "reset with outstanding shared interrupt claim")
    if (Set("start_pending", "stop_pending")(states(hart))) progress.complete(s"hsm-$hart", cycle)
    epochs(hart) += 1; states(hart) = (if (startedAfterReset) "started" else "stopped"); entries.remove(hart)
    if (resetClearsIpi) ipis -= hart
    onReset(hart)
  }
  def sendIpi(caller: Int, targets: Set[Int], cycle: Long): Unit = {
    at(cycle); known(caller)
    require(states(caller) == "started" && targets.nonEmpty && targets.subsetOf(harts))
    ipis ++= targets
  }
  def observeIpi(hart: Int, level: Boolean, cycle: Long): Unit = {
    at(cycle); known(hart); require(level == ipis(hart), "cross-hart IPI input mismatch")
  }
  def clearIpi(hart: Int, cycle: Long): Unit = { at(cycle); known(hart); ipis -= hart }
  def claim(hart: Int, source: Int, cycle: Long): Unit = {
    at(cycle); known(hart)
    require(states(hart) == "started" && source > 0 && !owners.contains(source), "shared source claimed twice")
    owners(source) = hart
  }
  def completeInterrupt(hart: Int, source: Int, cycle: Long): Unit = {
    at(cycle); known(hart)
    require(owners.get(source).contains(hart), "shared interrupt completion by wrong hart")
    owners.remove(source)
  }
  def check(cycle: Long): Unit = at(cycle)
  def finish(cycle: Long, expected: Map[Int, String]): Unit = {
    at(cycle); progress.finish(cycle)
    require(expected.keySet == harts && expected.forall { case (h, s) => states(h) == s }, "hart lifecycle campaign incomplete")
    require(owners.isEmpty, "shared interrupt claims incomplete")
  }
}
