package spinaltrace

import java.io.File

import spinal.core._
import spinal.core.internals._
import spinalwaves.SpinalWaves

import scala.collection.mutable.ArrayBuffer

/** Entry points to compile a design with SpinalTrace instrumentation and extract its PDG. */
object SpinalTrace {

  /** Copy of `config` with the SpinalTrace naming phase (opt-in instrumentation) and Spinal's line
    * comments enabled. Only names/keeps existing signals, see [[ProbeNamingPhase]]. */
  def instrument(config: SpinalConfig): SpinalConfig = {
    val inserters = ArrayBuffer[(ArrayBuffer[Phase]) => Unit]() ++ config.phasesInserters
    inserters += { phases =>
      val at = phases.indexWhere(_.isInstanceOf[PhaseCollectAndNameEnum])
      require(at >= 0, "SpinalTrace: PhaseCollectAndNameEnum not found in the Spinal phase list")
      phases.insert(at + 1, new ProbeNamingPhase)
    }
    config.copy(
      genLineComments = true,
      phasesInserters = inserters,
      transformationPhases = ArrayBuffer[Phase]() ++ config.transformationPhases,
      memBlackBoxers = ArrayBuffer[Phase]() ++ config.memBlackBoxers
    )
  }

  /** Two-pass elaboration (SpinalWaves' helper: discover component classes, then elaborate with
    * `debugComponents` so every ScalaLocated has a source location) with SpinalTrace instrumentation. */
  def elaborate[T <: Component](config: SpinalConfig)(gen: => T): SpinalReport[T] =
    SpinalWaves.elaborateWithLocations(instrument(config))(gen)

  /** Two-pass Verilog generation; writes `<targetDirectory>/spinaltrace/pdg.json`. */
  def generateVerilog[T <: Component](config: SpinalConfig = SpinalConfig(), opts: ExtractOptions = ExtractOptions())(gen: => T): (SpinalReport[T], File) = {
    val report = elaborate(config)(gen)
    val pdg    = PdgExtractor.extractTo(report, new File(new File(config.targetDirectory, "spinaltrace"), "pdg.json"), opts)
    (report, pdg)
  }

  private[spinaltrace] def deleteRecursively(f: File): Unit = {
    if (f.isDirectory) Option(f.listFiles()).getOrElse(Array.empty[File]).foreach(deleteRecursively)
    f.delete()
  }
}
