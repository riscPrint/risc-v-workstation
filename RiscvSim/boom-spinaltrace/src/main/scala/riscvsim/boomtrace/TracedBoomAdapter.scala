package riscvsim.boomtrace

import java.io.File
import java.nio.file.{Files, StandardCopyOption}
import java.security.MessageDigest

import scala.collection.concurrent.TrieMap

import spinal.core.sim._

import boom.common.SpinalBoomConfig
import boom.sim.BoomSim
import boom.system.BoomSimTop

import riscvsim._
import riscvsim.boom.BoomAdapter
import spinaltrace.{OnFailure, SpinalTraceSim, SpinalTraceSimOptions}

/**
 * BOOM's adapter with a SpinalTrace-instrumented model: the naming phase keeps the wires the
 * tracer reads (no logic is added, so a seed reproduces the plain model's run), and the model's
 * `pdg.json` is recorded as `details.pdg` in result.json. Everything else is BoomAdapter's.
 *
 * The model always has wave tracing compiled in; a run without `--wave` records none (the window
 * starts after the end), so use `--wave --wave-from A --wave-to B` around the cycles to trace.
 */
object TracedBoomAdapter extends CoreAdapter {
  type Model = SimCompiled[BoomSimTop]
  private val pdgs = TrieMap[AnyRef, File]()

  def core = BoomAdapter.core
  def configs = BoomAdapter.configs
  def xlen = BoomAdapter.xlen
  def isa(config: String) = BoomAdapter.isa(config)
  def sourceDir: File = BoomAdapter.sourceDir
  override def replayEnv = BoomAdapter.replayEnv
  override def generatedVerilog(m: Model): Seq[File] = BoomAdapter.generatedVerilog(m)

  def compile(key: ModelKey, work: File, cache: File): Model = {
    implicit val p = BoomSim.params(BoomAdapter.tile(key.config), key.rvfi)
    val formal = new File(BoomAdapter.boomDir, "formal")
    val k = key.copy(wave = true)
    val cfg = RiscvSimConfig(k, new File(work, "st"), cache, SpinalBoomConfig())
    val traced = SpinalTraceSim.compile(cfg, SpinalTraceSimOptions(onFailure = OnFailure.Print))(
      new BoomSimTop(BoomSim.resetVector, if (key.rvfi) Some(formal.getPath) else None, key.konata))
    // The process workspace goes away after the run: keep the PDG next to the shared cache.
    val md = MessageDigest.getInstance("SHA-256")
    for (f <- BoomAdapter.generatedVerilog(traced.compiled).sortBy(_.getName)) md.update(Files.readAllBytes(f.toPath))
    val hash = md.digest().take(8).map("%02x".format(_)).mkString
    val keep = new File(cache.getParentFile, s"spinaltrace/${k.name}-$hash.pdg.json")
    if (!keep.exists()) {
      keep.getParentFile.mkdirs()
      Files.copy(traced.pdg.toPath, keep.toPath, StandardCopyOption.REPLACE_EXISTING)
    }
    pdgs(traced.compiled) = keep
    traced.compiled
  }

  def run(m: Model, job: RunJob, ctx: RunContext): RunOutcome = {
    val j = if (job.wave) job else job.copy(wave = true, waveFrom = Some(Long.MaxValue), waveTo = None)
    val o = BoomAdapter.run(m, j, ctx)
    for (p <- pdgs.get(m)) o.details("pdg") = p.getPath
    o.details("spinaltrace") = true
    o
  }
}

object Main {
  def main(args: Array[String]): Unit = new Driver(TracedBoomAdapter).main(args)
}
