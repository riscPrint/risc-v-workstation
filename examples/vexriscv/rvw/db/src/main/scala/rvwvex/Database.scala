package rvwvex

import java.io.File
import java.nio.file.Paths
import spinaldb.{DbOptions, Main, SpinalDB}

object Database {
  def main(args: Array[String]): Unit = {
    val arguments = Main.expandArgsFile(args.toSeq)
    require(arguments.length == 2 && arguments.head == "rv32im", "usage: rvwvex.Database rv32im OUT")
    val adapter = new File(sys.env("RVW_ADAPTER")).getCanonicalFile
    val source = new File(sys.env("VEXRISCV")).getCanonicalFile
    val out = new File(arguments(1)).getCanonicalFile
    SpinalDB.generate(VexTop.spinalConfig.copy(targetDirectory = new File(out.getParentFile, "rtl").getPath), out,
      DbOptions(sourceRoots = Seq(Paths.get(source.getPath, "src/main/scala"),
        Paths.get(adapter.getPath, "src/main/scala")),
        pdg = false, blocks = false, hgldd = false,
        meta = Seq("core" -> "vexriscv", "config" -> "rv32im")))(new VexTop)
  }
}
