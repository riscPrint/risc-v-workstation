package riscvsim

import java.nio.file.Files
import org.scalatest.funsuite.AnyFunSuite
import scala.sys.process._

class RiscvFormalModelSpec extends AnyFunSuite {
  test("word remainder models truncate the divisor before zero detection") {
    assume(Process(Seq("sh", "-c", "command -v iverilog >/dev/null && command -v vvp >/dev/null")).! == 0, "Icarus unavailable")
    val dir = Files.createTempDirectory("rvw-word-rem-")
    try {
      for ((name, operation, expected) <- Seq(
        ("remw", "$unsigned($signed(rvfi_rs1_rdata[31:0]) % $signed(rvfi_rs2_rdata[31:0]))", "ffffffffffffffff"),
        ("remuw", "rvfi_rs1_rdata[31:0] % rvfi_rs2_rdata[31:0]", "0000000000000000"))) {
        val source = s"""module rvfi_insn_$name(input [63:0] rvfi_rs1_rdata, rvfi_rs2_rdata, output [63:0] result);
          wire [31:0] word_result = rvfi_rs2_rdata == 32'b0 ? rvfi_rs1_rdata : $operation;
          assign result = {{32{word_result[31]}}, word_result};
          endmodule
          module tb;
            reg [63:0] a, b; wire [63:0] result;
            rvfi_insn_$name dut(a,b,result);
            initial begin
              a=64'h501660ed5af74dea; b=64'h8000000000000000; #1;
              if (result !== 64'h000000005af74dea) $$fatal(1,"upper divisor bits");
              a=64'hcbdc4b23d6d844d9; #1;
              if (result !== 64'hffffffffd6d844d9) $$fatal(1,"word sign extension");
              a=64'hfffffffffffffff9; b=3; #1;
              if (result !== 64'h$expected) $$fatal(1,"nonzero control");
              $$finish;
            end
          endmodule"""
        val v = dir.resolve(name + ".v"); val binary = dir.resolve(name + ".out")
        Files.writeString(v, RiscvFormalModel.wordRemainder(source))
        assert(Process(Seq("iverilog", "-g2012", "-s", "tb", "-o", binary.toString, v.toString)).! == 0)
        assert(Process(Seq("vvp", binary.toString)).! == 0)
      }
    } finally {
      val paths = Files.walk(dir)
      try paths.sorted(java.util.Comparator.reverseOrder()).forEach(p => Files.delete(p)) finally paths.close()
    }
  }
}
