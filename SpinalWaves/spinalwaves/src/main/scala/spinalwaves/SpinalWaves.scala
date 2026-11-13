package spinalwaves

import java.nio.file.Files
import scala.collection.mutable
import spinal.core._
import spinal.core.internals.PhaseNameNodesByReflection

object SpinalWaves {
  /** The generator runs twice. Keep generators deterministic and free of external side effects. */
  def elaborateWithLocations[T <: Component](config: SpinalConfig)(gen: => T): SpinalReport[T] = {
    require(config.mode == null || config.mode == Verilog || config.mode == SystemVerilog,
      "SpinalWaves location elaboration supports Verilog and SystemVerilog")
    def generate(c: SpinalConfig): SpinalReport[T] =
      if (c.mode == SystemVerilog) c.generateSystemVerilog(gen) else c.generateVerilog(gen)
    val scratch = Files.createTempDirectory("spinalwaves-locations-")
    try {
      val discoveryInserters = config.phasesInserters.clone()
      discoveryInserters += { phases =>
        // Only discover component classes. A discarded backend pass would rename shared
        // singleton SpinalEnums and their elements before the real elaboration.
        val naming = phases.indexWhere(_.isInstanceOf[PhaseNameNodesByReflection])
        require(naming >= 0, "Spinal 1.15 naming phase missing from discovery pipeline")
        phases.remove(naming, phases.size - naming)
      }
      val first = generate(config.copy(targetDirectory = scratch.toString,
        phasesInserters = discoveryInserters))
      val classes = mutable.HashSet.empty[Class[_]] ++ config.debugComponents
      def collect(c: Component): Unit = { classes += c.getClass; c.children.foreach(collect) }
      collect(first.toplevel)
      generate(config.copy(debugComponents = classes))
    } finally {
      import scala.jdk.CollectionConverters._
      val files = Files.walk(scratch)
      try files.iterator().asScala.toVector.sortBy(_.getNameCount).reverse.foreach(Files.delete(_))
      finally files.close()
    }
  }
}
