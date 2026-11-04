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
    val (options, rtl, arguments) = Main.parse(args.toSeq, base)
    require(arguments.length == 2 && arguments.head == "rv32im", "usage: rvwvex.Database rv32im OUT [SpinalDB options]")
    val out = new File(arguments(1)).getCanonicalFile
    SpinalDB.generate(VexTop.spinalConfig.copy(targetDirectory = rtl.getOrElse(new File(out.getParentFile, "rtl").getPath)), out,
      options.copy(meta = options.meta ++ Seq("core" -> "vexriscv", "config" -> "rv32im")))(new VexTop)
  }
}
