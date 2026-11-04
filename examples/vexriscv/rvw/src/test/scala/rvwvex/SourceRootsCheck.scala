package rvwvex

import java.io.File
import java.nio.file.Files
import riscvsim.{ModelKey, RiscvSimConfig}

/** Native regression: the adapter must resolve core files outside its own tree. */
object SourceRootsCheck {
  def main(args: Array[String]): Unit = {
    val work = Files.createTempDirectory("vex-source-roots-").toFile
    try {
      val key = ModelKey("rv32im", spinaltrace = true)
      VexAdapter.elaborate(key, work)
      val graph = ujson.read(Files.readString(RiscvSimConfig.dependencyGraph(key, work).toPath))
      val files = graph("vertices").arr.map(_("file").str).toSet
      for (name <- Seq("Fetcher.scala", "IBusSimplePlugin.scala", "Misc.scala")) {
        val expected = new File(VexAdapter.sourceDir, "src/main/scala/vexriscv/plugin/" + name).getCanonicalPath
        require(files.contains(expected), "unresolved core source: " + expected)
      }
      val adapter = new File(sys.env.getOrElse("RVW_ADAPTER", ".")).getCanonicalFile
      val top = new File(adapter, "src/main/scala/rvwvex/VexTop.scala").getCanonicalPath
      require(files.contains(top), "unresolved adapter source: " + top)
      println("SourceRootsCheck: 1 passed")
    } finally org.apache.commons.io.FileUtils.deleteDirectory(work)
  }
}
