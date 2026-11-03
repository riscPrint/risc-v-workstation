package riscvsim

import scala.collection.mutable

/** Bounded watchdog under project-declared arbitration/response fairness.
  * Age starts at request presentation, so lack of acceptance is also checked.
  * Retries and unrelated traffic do not renew a request's deadline. */
final class ProgressMonitor(val boundCycles: Long, val capacity: Int, val fairness: String) {
  require(boundCycles > 0 && capacity > 0 && fairness.trim.nonEmpty)
  private val pending = mutable.Map.empty[String, Long]
  private var lastCycle = -1L
  private def at(cycle: Long): Unit = {
    require(cycle >= 0 && cycle >= lastCycle); lastCycle = cycle
  }
  def request(id: String, cycle: Long): Unit = {
    at(cycle)
    require(id.nonEmpty && !pending.contains(id), "duplicate logical request")
    require(pending.size < capacity, "resource capacity exceeded")
    pending(id) = cycle
  }
  def retry(id: String, cycle: Long): Unit = { at(cycle); require(pending.contains(id)); check(cycle) }
  def complete(id: String, cycle: Long): Unit = {
    at(cycle); require(pending.contains(id), "unknown completion")
    check(cycle); pending.remove(id)
  }
  def check(cycle: Long): Unit = {
    at(cycle)
    val overdue = pending.collect { case (id, start) if cycle - start > boundCycles => id }.toSeq.sorted
    require(overdue.isEmpty, s"bounded forward progress exceeded: ${overdue.mkString(",")}; fairness: $fairness")
  }
  def outstanding: Int = pending.size
  def finish(cycle: Long): Unit = { check(cycle); require(pending.isEmpty, "incomplete coherence requests") }
}
