package riscvsim

import java.io.File
import java.nio.file.Files
import org.scalatest.funsuite.AnyFunSuite

class MappedAdapterSpec extends AnyFunSuite {
  private val dir = Files.createTempDirectory("core-map").toFile
  private val file = new File(dir, "core-map.json")
  private def map(extra: String = "", bus: String = """{"name": "mem", "protocol": "valid-ready",
      "signals": {"valid": "v", "ready": "r", "address": "a", "rdata": "d"}}""") =
    s"""{"schema": "rvw.core-map/1", "core": "c", "isa": "rv32i", "xlen": 32,
       "top": {"kind": "spinal", "class": "demo.Top"}, "reset_pc": "0x80000000",
       "ram": {"base": "0x80000000", "size": 4096}, "buses": [$bus],
       "rvfi": {"prefix": "rvfi_"}, "irq": {"7": "mtip"}, "constants": {"x": "0x5"}$extra}"""

  test("a complete map parses") {
    val m = CoreMap.parse(file, map())
    assert(m.topClass.contains("demo.Top") && m.verilog.isEmpty)
    assert(m.resetPc == 0x80000000L && m.ramSize == 4096)
    assert(m.buses.head.signals("address") == "a" && !m.buses.head.writeResponse)
    assert(m.rvfiPrefix.contains("rvfi_") && m.irq == Map(7 -> "mtip") && m.constants == Map("x" -> BigInt(5)))
    assert(new MappedAdapter(m).irqInputMask == BigInt(0x80))
    assert(new MappedAdapter(m).supportsProbes)
  }

  test("unknown fields, protocols and bus signals are errors") {
    intercept[IllegalArgumentException](CoreMap.parse(file, map(""", "extra": 1""")))
    intercept[IllegalArgumentException](CoreMap.parse(file, map(bus =
      """{"name": "m", "protocol": "axi", "signals": {}}""")))
    val missing = intercept[IllegalArgumentException](CoreMap.parse(file, map(bus =
      """{"name": "m", "protocol": "req-rsp", "signals": {"cmd_valid": "v"}}""")))
    assert(missing.getMessage.contains("lacks"))
    intercept[IllegalArgumentException](CoreMap.parse(file, map(bus =
      """{"name": "m", "protocol": "valid-ready", "signals": {"valid": "v", "ready": "r", "address": "a", "rdata": "d", "bogus": "b"}}""")))
  }

  test("a Verilog top needs its files and a 1-bit clock and reset input") {
    val v = new File(dir, "core.v")
    Files.write(v.toPath, "module core(input clk, input rst); endmodule\n".getBytes)
    def verilog(clock: String) = map().replace(""""top": {"kind": "spinal", "class": "demo.Top"}""",
      s""""top": {"kind": "verilog", "module": "core", "files": ["core.v"], "parameters": {"P": 2147483648},
          "ports": [{"name": "clk", "dir": "in", "width": 1}, {"name": "rst", "dir": "in", "width": 1}],
          "clock": "$clock", "reset": "rst", "reset_active": "high"}""")
    val m = CoreMap.parse(file, verilog("clk"))
    assert(m.verilog.get.files == Seq(v.getCanonicalFile) && !m.verilog.get.resetActiveLow)
    assert(m.verilog.get.parameters("P") == BigInt(2147483648L))
    val absolute = CoreMap.parse(file, verilog("clk").replace("core.v", v.getAbsolutePath))
    assert(absolute.verilog.get.files == Seq(v.getCanonicalFile))
    intercept[IllegalArgumentException](CoreMap.parse(file, verilog("nope")))
  }
}
