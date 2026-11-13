package rvwsmp

/** Keep one hart's memory effects visible until all of its requests retire.
  * The in-order core may need to issue its next request to retire the previous
  * one. A different hart cannot enter during that interval. */
class SerialMemoryGate {
  private var owner = Option.empty[Int]
  private var pending = 0
  def canIssue(hart: Int): Boolean = owner.isEmpty || owner.contains(hart)
  def issue(hart: Int): Unit = {
    require(canIssue(hart), "overlapping serialized harts")
    owner = Some(hart)
    pending += 1
  }
  def retire(hart: Int): Unit = {
    require(owner.contains(hart) && pending > 0, "retired memory without ownership")
    pending -= 1
    if(pending == 0) owner = None
  }
}
object SerialMemoryGateChecks {
  def main(args: Array[String]): Unit = {
    val gate = new SerialMemoryGate
    require(gate.canIssue(0) && gate.canIssue(1))
    gate.issue(0); gate.issue(0)
    require(!gate.canIssue(1))
    gate.retire(0); require(!gate.canIssue(1))
    gate.retire(0); require(gate.canIssue(1))
    gate.issue(1)
    require(scala.util.Try(gate.issue(0)).isFailure)
    require(scala.util.Try(gate.retire(0)).isFailure)
    require(!gate.canIssue(0) && gate.canIssue(1))
    gate.retire(1)
    require(scala.util.Try(gate.retire(1)).isFailure)
    println("serial memory gate: 8 checks passed")
  }
}
