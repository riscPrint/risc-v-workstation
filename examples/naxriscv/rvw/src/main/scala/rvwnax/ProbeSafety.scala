package rvwnax

import java.io.File
import java.nio.file.Files
import java.security.MessageDigest

/** Synthesis safety: with probes disabled, NaxRiscv with the ProbeTapPlugin must give the same
  * Verilog as without it. Prints one JSON line; exit 1 when they differ.
  * `ProbeSafety --probes DIR` instead writes the Verilog with probes enabled into DIR. */
object ProbeSafety {
  def verilog(config: String, probeTap: Boolean, probes: Boolean, dir: File): String = {
    spinalprobes.Probe.enabled(probes) {
      val c = NaxTop.spinalConfig.includeSimulation.copy(targetDirectory = dir.getPath)
      if (probes) c.addTransformationPhase(new spinal.core.sim.SimVerilatorPhase)
      c.generateVerilog(NaxTop(config, probeTap))
    }
    new String(Files.readAllBytes(new File(dir, "NaxRiscv.v").toPath), "UTF-8")
  }
  def sha(s: String): String = MessageDigest.getInstance("SHA-256").digest(s.getBytes("UTF-8")).map(b => f"${b & 255}%02x").mkString
  def main(args: Array[String]): Unit = {
    val config = NaxTop.configs.head
    if (args.headOption.contains("--probes")) { verilog(config, probeTap = true, probes = true, new File(args(1))); return }
    def temp = Files.createTempDirectory("rvwnax-probe-safety").toFile
    val (a, b) = (verilog(config, probeTap = true, probes = false, temp), verilog(config, probeTap = false, probes = false, temp))
    println(s"""{"core":"naxriscv","config":"$config","with_probe_tap_sha256":"${sha(a)}","without_probe_tap_sha256":"${sha(b)}","identical":${a == b}}""")
    if (a != b) sys.exit(1)
  }
}
