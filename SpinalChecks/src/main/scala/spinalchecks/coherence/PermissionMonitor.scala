package spinalchecks.coherence

import spinal.core._

/** Permission projection only. The adapter may collapse several model steps into
  * one sample. This checks neither data values nor TileLink channel ordering.
  * Instantiate in the clock domain that owns both permission inputs. */
class PermissionMonitor(a: UInt, b: UInt) extends Area {
  require(a.getWidth == 2 && b.getWidth == 2)
  val current = UInt(4 bits)
  current := a.resize(4) + (b.resize(4) * 3).resize(4)
  val previous = RegNext(current) init 0
  val legal = (a <= 2 && b <= 2) && PermissionRelation.states.toSeq.sorted
    .map(s => current === s).reduce(_ || _)
  val transition = PermissionRelation.edges.toSeq.sorted
    .map { case (p, n) => previous === p && current === n }.reduce(_ || _)
  val failed = !legal || !transition
  assert(!failed, "coherence permission projection")
}
