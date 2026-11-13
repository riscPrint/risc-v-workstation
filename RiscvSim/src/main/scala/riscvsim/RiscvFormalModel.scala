package riscvsim

import java.io.File
import java.nio.file.Files

/** Correct word-divisor zero tests in imported riscv-formal remainder models.
  * Keep the source checkout unchanged. The generated checker joins the RTL hash. */
object RiscvFormalModel {
  def wordRemainder(text: String): String = {
    val modules = "(?s)module\\s+\\w*insn_remu?w\\b.*?endmodule".r
    modules.replaceAllIn(text, m => java.util.regex.Matcher.quoteReplacement(
      m.matched.replace("rvfi_rs2_rdata == 32'b0 ? rvfi_rs1_rdata",
        "rvfi_rs2_rdata[31:0] == 32'b0 ? rvfi_rs1_rdata[31:0]")))
  }

  def prepare(source: File, out: File): File = {
    out.mkdirs()
    source.listFiles().filter(_.getName.endsWith(".v")).foreach { file =>
      Files.writeString(new File(out, file.getName).toPath, wordRemainder(Files.readString(file.toPath)))
    }
    out
  }
}
