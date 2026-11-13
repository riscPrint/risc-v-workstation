package rvwvex

import java.nio.file.Files
import java.security.MessageDigest

/** Synthesis safety: with probes disabled, VexTop with the ProbePlugin must give the same
  * Verilog as VexTop without it. Prints one JSON line; exit 1 when they differ. */
object ProbeSafety {
  def verilog(probePlugin: Boolean): String = {
    val dir = Files.createTempDirectory("rvwvex-probe-safety").toFile
    spinalprobes.Probe.enabled(false) {
      VexTop.spinalConfig.copy(targetDirectory = dir.getPath).generateVerilog(new VexTop(VexTop.configuration(probePlugin)))
    }
    new String(Files.readAllBytes(new java.io.File(dir, "VexTop.v").toPath))
  }
  def sha(s: String): String = MessageDigest.getInstance("SHA-256").digest(s.getBytes("UTF-8")).map(b => f"${b & 255}%02x").mkString
  def main(args: Array[String]): Unit = {
    val (a, b) = (verilog(probePlugin = true), verilog(probePlugin = false))
    println(s"""{"core":"vexriscv","with_probe_plugin_sha256":"${sha(a)}","without_probe_plugin_sha256":"${sha(b)}","identical":${a == b}}""")
    if (a != b) sys.exit(1)
  }
}
