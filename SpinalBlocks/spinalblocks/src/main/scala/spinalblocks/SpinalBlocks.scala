package spinalblocks

import java.io.File
import java.nio.charset.StandardCharsets.UTF_8
import java.nio.file.{Files, Path, Paths}

import spinal.core._

/** Sigasi-style block diagrams of SpinalHDL designs.
  *
  * {{{
  * SpinalBlocks.generate(SpinalConfig(targetDirectory = "rtl"), new File("gcd.json"))(new Gcd)
  * }}}
  */
object SpinalBlocks {

  /** Elaborates `gen` (twice when `locations`, to record source locations, see SpinalWaves), generates the RTL
    * as usual and writes the diagram JSON to `out`. */
  def generate[T <: Component](config: SpinalConfig, out: File, locations: Boolean = true,
                               sourceRoots: Seq[Path] = defaultRoots)(gen: => T): SpinalReport[T] = {
    val report =
      if (locations) spinalwaves.SpinalWaves.elaborateWithLocations(config)(gen)
      else if (config.mode == SystemVerilog) config.generateSystemVerilog(gen)
      else config.generateVerilog(gen)
    write(report.toplevel, out, sourceRoots)
    report
  }

  def defaultRoots: Seq[Path] = Seq("src/main/scala", "src/test/scala").map(Paths.get(_))

  /** The diagram of an already generated design. */
  def extract(top: Component, sourceRoots: Seq[Path] = defaultRoots): ujson.Value =
    Model.toJson(new Extractor(sourceRoots).extract(top))

  /** Writes the diagram JSON (docs/FORMAT.md); `.json.gz` writes it gzipped. Open it with a SpinalBlocks host. */
  def write(top: Component, out: File, sourceRoots: Seq[Path] = defaultRoots): File = {
    val text = ujson.write(extract(top, sourceRoots))
    Option(out.getAbsoluteFile.getParentFile).foreach(_.mkdirs())
    val bytes = text.getBytes(UTF_8)
    if (out.getName.endsWith(".gz")) {
      val gz = new java.util.zip.GZIPOutputStream(Files.newOutputStream(out.toPath))
      try gz.write(bytes) finally gz.close()
    } else Files.write(out.toPath, bytes)
    println(s"[SpinalBlocks] wrote ${out.getAbsolutePath}")
    out
  }
}
