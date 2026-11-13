package rvwnax

import java.io.File
import java.nio.file.Paths
import spinaldb.{DbOptions, SpinalDB}

/** Writes the SpinalDB design database of one NaxRiscv configuration, elaborated as in simulation. */
object Database {
  def main(args: Array[String]): Unit = {
    val adapter = new File(sys.env("RVW_ADAPTER")).getCanonicalFile
    val source = new File(sys.env("NAXRISCV")).getCanonicalFile
    val base = DbOptions(sourceRoots = Seq(Paths.get(source.getPath, "src/main/scala"),
      Paths.get(adapter.getPath, "src/main/scala")))
    val (options, rtl, arguments) = spinaldb.Main.parse(args.toSeq, base)
    require(arguments.length == 2 && NaxTop.configs.contains(arguments.head),
      s"usage: rvwnax.Database ${NaxTop.configs.mkString("|")} OUT [SpinalDB options]")
    val out = new File(arguments(1)).getCanonicalFile
    val config = NaxTop.spinalConfig.includeSimulation
    SpinalDB.generate(config.copy(targetDirectory = rtl.getOrElse(new File(out.getParentFile, "rtl").getPath)), out,
      options.copy(meta = options.meta ++ Seq("core" -> "naxriscv", "config" -> arguments.head)))(NaxTop(arguments.head))
  }
}
