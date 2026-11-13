package spinalwaves

import spinal.core.Mem
import spinal.core.internals.Expression
import spinal.core.sim.SpinalSimConfig

/** Calls that differ between the SpinalHDL versions the libraries are built against (see
  * `scripts/sbt/SpinalAxis.scala`). Older versions miss the member; the fallback is stated. */
object SpinalCompat {
  private def member(o: AnyRef, name: String): Option[AnyRef] =
    o.getClass.getMethods.find(m => m.getName == name && m.getParameterCount == 0).map(_.invoke(o))

  /** `SpinalSimConfig._waveFilePrefix`; older versions have no prefix. */
  def waveFilePrefix(c: SpinalSimConfig): Option[String] = member(c, "_waveFilePrefix").flatMap(Option(_)).map(_.toString)

  /** Fields of a `MemReadAsyncWrite` port (memory, address, width); None for other nodes, and
    * always None in older versions, which have no such port. */
  def memReadAsyncWrite(node: AnyRef): Option[(Mem[_], Expression, Int)] =
    if (node.getClass.getSimpleName != "MemReadAsyncWrite") None
    else Some((member(node, "mem").get.asInstanceOf[Mem[_]], member(node, "address").get.asInstanceOf[Expression],
      member(node, "getWidth").get.asInstanceOf[Integer].intValue))
}
