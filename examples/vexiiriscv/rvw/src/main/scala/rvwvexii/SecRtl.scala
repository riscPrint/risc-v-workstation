package rvwvexii

/** Plain Verilog for `rvw sec` native runs. The upstream WhiteboxerPlugin signals give the commit PC.
  * Usage: SecRtl OUT [config...]. Without configs, `rv32im` goes to OUT/VexiiRiscv.v (the original
  * layout); each named config goes to OUT/<config>/VexiiRiscv.v. */
object SecRtl {
  def main(args: Array[String]): Unit = {
    // VexiiTop reads `live-devices.json` beside the launcher script; build-rtl.sh runs in `rvw/`.
    if (!sys.props.contains("riscvsim.script")) sys.props("riscvsim.script") = new java.io.File("run.sh").getAbsolutePath
    if (args.length == 1)
      VexiiTop.spinalConfig.copy(targetDirectory = args(0)).generateVerilog(VexiiTop("rv32im"))
    for (config <- args.drop(1))
      VexiiTop.spinalConfig.copy(targetDirectory = s"${args(0)}/$config").generateVerilog(VexiiTop(config))
  }
}
