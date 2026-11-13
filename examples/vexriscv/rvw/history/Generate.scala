package rvwvex
object HistoryGenerate {
  def main(args: Array[String]): Unit = {
    VexTop.spinalConfig.copy(targetDirectory = args(0), headerWithDate = false,
      headerWithRepoHash = false).generateVerilog(new VexTop)
  }
}
