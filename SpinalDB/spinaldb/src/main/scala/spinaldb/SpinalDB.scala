package spinaldb

import java.io.File

import spinal.core._
import spinal.core.internals._

import scala.collection.mutable.ArrayBuffer

/** One elaboration of a Spinal design, written as a design database (`rvw.designdb/20`, SQLite).
  *
  * {{{
  * SpinalDB.generate(SpinalConfig(targetDirectory = "rtl"), new File("design.db"))(new MyTop)
  * }}}
  * The elaboration runs twice (SpinalWaves' two-pass scheme, so every statement has a Scala source
  * location) with SpinalTrace's naming phase (so `when` conditions and mux selects are named wires the
  * PDG can refer to). The RTL is generated as usual into `config.targetDirectory`. The same report
  * feeds the netlist tables, the SpinalTrace PDG, the SpinalBlocks diagram and the SpinalWaves HGLDD. */
object SpinalDB {

  /** Two-pass elaboration; with `traceNaming` (needed for the PDG) SpinalTrace's naming phase is added.
    * Either way, the signals Spinal names after a source line (`when_File_l12`, `switch_File_l40`,
    * name priority `REMOVABLE`) are tagged `SpinalGeneratedNameTag` before Spinal makes every name
    * strong, so the extractor can tell them from a user signal that only looks like one. */
  def elaborate[T <: Component](config: SpinalConfig, traceNaming: Boolean = true)(gen: => T): SpinalReport[T] = {
    val userHooks = EmissionConfig.capture(config)
    val report = if (traceNaming) spinaltrace.SpinalTrace.elaborate(InlineCapture.instrument(config))(gen)
      else spinalwaves.SpinalWaves.elaborateWithLocations(markGeneratedNames(InlineCapture.instrument(config.copy(genLineComments = true))))(gen)
    EmissionConfig.remember(report, userHooks)
    report
  }

  /** Copy of `config` with [[GeneratedNamePhase]] right after Spinal's enum naming (where SpinalTrace's
    * naming phase, which tags the same signals, also runs). */
  def markGeneratedNames(config: SpinalConfig): SpinalConfig = {
    val inserters = ArrayBuffer[(ArrayBuffer[Phase]) => Unit]() ++ config.phasesInserters
    inserters += { phases =>
      val at = phases.indexWhere(_.isInstanceOf[PhaseCollectAndNameEnum])
      require(at >= 0, "SpinalDB: PhaseCollectAndNameEnum not found in the Spinal phase list")
      phases.insert(at + 1, new GeneratedNamePhase)
    }
    config.copy(phasesInserters = inserters, transformationPhases = ArrayBuffer[Phase]() ++ config.transformationPhases,
      memBlackBoxers = ArrayBuffer[Phase]() ++ config.memBlackBoxers)
  }

  /** Writes the database of an already elaborated design (elaborated with [[elaborate]] for locations). */
  def write(report: SpinalReport[_ <: Component], out: File, opts: DbOptions = DbOptions()): File = {
    val target = out.toPath.toAbsolutePath
    java.nio.file.Files.createDirectories(target.getParent)
    val temporary = java.nio.file.Files.createTempFile(target.getParent, ".spinaldb-", ".db")
    try {
      val db = new DbWriter(temporary.toFile)
      try {
        new Extractor(report, opts).write(db)
        db.finish(Schema.indexes)
      } finally db.close()
      java.nio.file.Files.move(temporary, target, java.nio.file.StandardCopyOption.ATOMIC_MOVE,
        java.nio.file.StandardCopyOption.REPLACE_EXISTING)
    } finally java.nio.file.Files.deleteIfExists(temporary)
    opts.log(s"wrote ${out.getAbsolutePath} (${out.length() / 1024} KiB)")
    out
  }

  /** Elaborates `gen`, generates the RTL and writes the database to `out`. */
  def generate[T <: Component](config: SpinalConfig, out: File, opts: DbOptions = DbOptions())(gen: => T): SpinalReport[T] = {
    val t0     = System.nanoTime()
    val report = elaborate(config, traceNaming = opts.pdg)(gen)
    val secs   = (System.nanoTime() - t0) / 1e9
    opts.log(f"elaborated ${report.toplevelName} in $secs%.1f s")
    write(report, out, opts.copy(meta = opts.meta ++ Seq(
      "elaboration_s" -> f"$secs%.1f", "rtl_dir" -> new File(config.targetDirectory).getAbsolutePath)))
    report
  }
}

/** Tags every signal that still holds a Spinal auto-name of priority `REMOVABLE` (the `when_`/`switch_`
  * line names) with `SpinalGeneratedNameTag`, as SpinalTrace's naming phase does. Later phases give
  * every name `DATAMODEL_STRONG`, so the priority cannot be read at extraction time. No logic changes;
  * the tag is in `Extractor.IgnoredTags`. */
class GeneratedNamePhase extends PhaseNetlist {
  override def impl(pc: PhaseContext): Unit = pc.walkStatements {
    case bt: BaseType if bt.isNamed && SpinalTraceAccess.namePriority(bt) == Nameable.REMOVABLE =>
      if (!bt.hasTag(spinaltrace.SpinalGeneratedNameTag)) bt.addTag(spinaltrace.SpinalGeneratedNameTag)
    case _ =>
  }
}
