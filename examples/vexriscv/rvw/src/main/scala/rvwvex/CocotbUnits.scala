package rvwvex

import spinal.core._

// Small sequential design plus one unmodified upstream VexRiscv unit.
object CocotbUnits {
  def main(args: Array[String]): Unit = {
    val outputDirectory = args(0)
    SpinalConfig(targetDirectory = outputDirectory).generateVerilog(new Component {
      setDefinitionName("CounterUnit")
      val io = new Bundle {
        val enable = in Bool()
        val count = out UInt(8 bits)
      }
      val count = Reg(UInt(8 bits)) init(0)
      when(io.enable) { count := count + 1 }
      io.count := count
    })
    SpinalConfig(targetDirectory = outputDirectory).generateVerilog(new vexriscv.plugin.PmpSetter(2))
  }
}
