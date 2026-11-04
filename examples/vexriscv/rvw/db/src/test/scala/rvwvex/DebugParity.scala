package rvwvex

import java.io.File
import java.nio.file.Paths
import spinaldb.{DbOptions, SpinalDB}
import spinalblocks.SpinalBlocks
import spinaltrace.SpinalTrace
import riscvsim.{ModelKey, RiscvSimConfig}

/** Export independent legacy and database cases. Compare every field with rvw.debug.parity. */
object DebugParity {
  def main(args: Array[String]): Unit = {
    require(args.length == 1, "usage: DebugParity OUT")
    val out = new File(args(0)).getCanonicalFile
    require(!out.exists(), "output must be new")
    out.mkdirs()
    val roots = Seq(Paths.get(VexAdapter.sourceDir.getPath, "src/main/scala"),
      Paths.get(sys.env("RVW_ADAPTER"), "src/main/scala"))
    def config(name: String) = VexTop.spinalConfig.copy(targetDirectory = new File(out, name).getPath)
    SpinalBlocks.generate(config("old-blocks-rtl"), new File(out, "old-blocks.json"), sourceRoots = roots)(new VexTop)
    SpinalDB.generate(config("blocks-rtl"), new File(out, "blocks.db"),
      DbOptions(pdg = false, sourceRoots = roots))(new VexTop)
    SpinalTrace.generateVerilog(config("old-trace-rtl"))(new VexTop)
    SpinalDB.generate(config("trace-rtl"), new File(out, "trace.db"),
      DbOptions(sourceRoots = roots))(new VexTop)
    VexAdapter.elaborate(ModelKey("rv32im", spinaltrace = true), new File(out, "model"))
    println("DebugParity: five independent elaborations exported")
  }
}
