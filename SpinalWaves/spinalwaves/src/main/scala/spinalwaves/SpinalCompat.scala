package spinalwaves

import spinal.core.Mem
import spinal.core.internals.Expression
import spinal.core.sim.{SimCompiled, SpinalSimConfig}
import java.io.File

/** Calls that differ between the SpinalHDL versions the libraries are built against (see
  * `scripts/sbt/SpinalAxis.scala`). Older versions miss the member; the fallback is stated. */
object SpinalCompat {
  private def member(o: AnyRef, name: String): Option[AnyRef] =
    o.getClass.getMethods.find(m => m.getName == name && m.getParameterCount == 0).map(_.invoke(o))

  /** `SpinalSimConfig._waveFilePrefix`; older versions have no prefix. */
  def waveFilePrefix(c: SpinalSimConfig): Option[String] = member(c, "_waveFilePrefix").flatMap(Option(_)).map(_.toString)

  /** The old Verilator backend uses _wavePath; newer backends use getTestPath. */
  def waveFile(c: SimCompiled[_], test: String): File = {
    val config = c.simConfig
    if (config.getClass.getMethods.exists(_.getName == "_waveFilePrefix")) {
      val prefix = waveFilePrefix(config).map(_.replace("$TEST", test) + "_").getOrElse("")
      new File(config.getTestPath(test), prefix + "wave.vcd")
    } else {
      val path = member(config, "_wavePath").get.toString.replace("$TEST", test)
      new File(s"${c.compiledPath.getPath}/$path/wave.vcd")
    }
  }

  /** Fields of a `MemReadAsyncWrite` port (memory, address, width); None for other nodes, and
    * always None in older versions, which have no such port. */
  def memReadAsyncWrite(node: AnyRef): Option[(Mem[_], Expression, Int)] =
    if (node.getClass.getSimpleName != "MemReadAsyncWrite") None
    else Some((member(node, "mem").get.asInstanceOf[Mem[_]], member(node, "address").get.asInstanceOf[Expression],
      member(node, "getWidth").get.asInstanceOf[Integer].intValue))
}
