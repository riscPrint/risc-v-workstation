package rvwvexii

import java.nio.file.Files
import java.security.MessageDigest

/** Synthesis safety: with probes disabled, VexiiRiscv with the ProbeTapPlugin must give the same
  * Verilog as without it. Prints one JSON line per config; exit 1 when one differs. */
object ProbeSafety {
  def verilog(config: String, probeTap: Boolean): String = {
    val dir = Files.createTempDirectory("rvwvexii-probe-safety").toFile
    spinalprobes.Probe.enabled(false) {
      VexiiTop.spinalConfig.copy(targetDirectory = dir.getPath).generateVerilog(VexiiTop(config, probeTap))
    }
    new String(Files.readAllBytes(new java.io.File(dir, "VexiiRiscv.v").toPath))
  }
  def sha(s: String): String = MessageDigest.getInstance("SHA-256").digest(s.getBytes("UTF-8")).map(b => f"${b & 255}%02x").mkString
  def main(args: Array[String]): Unit = {
    val configs = if (args.nonEmpty) args.toSeq else Seq("rv32im", "rv32imasu")
    val same = configs.map { c =>
      val (a, b) = (verilog(c, probeTap = true), verilog(c, probeTap = false))
      println(s"""{"core":"vexiiriscv","config":"$c","with_probe_tap_sha256":"${sha(a)}","without_probe_tap_sha256":"${sha(b)}","identical":${a == b}}""")
      a == b
    }
    if (!same.forall(identity)) sys.exit(1)
  }
}
