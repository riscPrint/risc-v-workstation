package rvwvex

import java.io.File
import java.nio.file.Paths
import spinaldb.{DbOptions, Main, SpinalDB}

object Database {
  def main(args: Array[String]): Unit = {
    val adapter = new File(sys.env("RVW_ADAPTER")).getCanonicalFile
    val source = new File(sys.env("VEXRISCV")).getCanonicalFile
    val base = DbOptions(sourceRoots = Seq(Paths.get(source.getPath, "src/main/scala"),
      Paths.get(adapter.getPath, "src/main/scala")))
    // `--probes` elaborates with the workstation probes, so `rvw probes list --db` can see them.
    val probes = args.contains("--probes")
    val checks = args.contains("--checks")
    val (options, rtl, arguments) = Main.parse(args.toSeq.filterNot(a => a == "--probes" || a == "--checks"), base)
    require(arguments.length == 2 && arguments.head == "rv32im", "usage: rvwvex.Database rv32im OUT [SpinalDB options]")
    val out = new File(arguments(1)).getCanonicalFile
    val config = VexTop.spinalConfig.copy(targetDirectory = rtl.getOrElse(new File(out.getParentFile, "rtl").getPath))
    val checked = if (checks) spinalchecks.SpinalChecks.install(config,
      spinalchecks.ChecksConfig(reportPath = new File(out.getParentFile, "checks.json").getPath))._1 else config
    spinalprobes.Probe.enabled(probes)(SpinalDB.generate(checked, out,
      options.copy(meta = options.meta ++ Seq("core" -> "vexriscv", "config" -> "rv32im")))(new VexTop))
  }
}
