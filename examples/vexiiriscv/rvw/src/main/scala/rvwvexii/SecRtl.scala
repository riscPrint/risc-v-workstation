package rvwvexii

/** Plain Verilog of the example configuration for `rvw sec` native runs.
  * The upstream WhiteboxerPlugin signals give the commit PC. Usage: SecRtl OUT */
object SecRtl {
  def main(args: Array[String]): Unit =
    VexiiTop.spinalConfig.copy(targetDirectory = args(0)).generateVerilog(VexiiTop("rv32im"))
}
