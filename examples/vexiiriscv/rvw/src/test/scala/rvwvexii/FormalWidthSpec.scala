package rvwvexii

import org.scalatest.funsuite.AnyFunSuite
import java.nio.file.Files
import spinal.core._
import vexiiriscv.VexiiRiscv
import vexiiriscv.ParamSimple
import vexiiriscv.test.WhiteboxerPlugin

/** Actual elaboration catches data truncation and memory-mask width errors. */
class FormalWidthSpec extends AnyFunSuite {
  for ((config, width) <- Seq("rv32im" -> 32, "rv64ima" -> 64, "rv64imasu" -> 64)) {
    test(s"$config formal observer preserves XLEN data and byte masks") {
      val output = Files.createTempDirectory(new java.io.File("target").toPath, "rvw-observer-width").toFile
      try {
        val report = SpinalConfig(targetDirectory = output.getPath).generateVerilog {
          val plugins = VexiiTop.param(config).plugins()
          if (!plugins.exists(_.isInstanceOf[WhiteboxerPlugin])) plugins += new WhiteboxerPlugin(false)
          plugins += new FormalRvfiPlugin
          plugins += new CsrChecksPlugin
          ParamSimple.setPma(plugins)
          VexiiRiscv(plugins)
        }
        val ports = report.toplevel.getAllIo.map(p => p.getName() -> p.getBitsWidth).toMap
        for (name <- Seq("rs1_rdata", "rs2_rdata", "rd_wdata", "pc_rdata", "pc_wdata", "mem_addr", "mem_rdata", "mem_wdata"))
          assert(ports("rvfi_" + name) == width)
        assert(report.toplevel.host[CsrChecksPlugin].logic.expected.getWidth == width)
        assert(ports("rvfi_insn") == 32)
        assert(ports("rvfi_mem_rmask") == width / 8)
        assert(ports("rvfi_mem_wmask") == width / 8)
      } finally {
        def remove(file: java.io.File): Unit = {
          if (file.isDirectory) Option(file.listFiles()).toSeq.flatten.foreach(remove)
          file.delete()
        }
        remove(output)
      }
    }
  }
}
