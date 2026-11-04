package riscvsim

import java.nio.file.Files
import org.scalatest.funsuite.AnyFunSuite
import spinal.core._
import spinal.core.sim._
import spinal.lib.bus.tilelink.Opcode

class SimEncodingSpec extends AnyFunSuite {
  test("capture TileLink wire opcodes rather than enum ordinals") {
    class Top extends Component {
      val io = new Bundle { val opcode = in(Opcode.A()) }
    }
    val work = Files.createTempDirectory("mmu-encoding").toFile
    try {
      SimConfig.withVerilator.workspacePath(work.getPath).compile(new Top).doSim { dut =>
        for ((op, encoded) <- Seq(Opcode.A.PUT_FULL_DATA -> 0, Opcode.A.GET -> 4, Opcode.A.ACQUIRE_PERM -> 7)) {
          dut.io.opcode #= op
          sleep(1)
          assert(SimEncoding.value(dut.io.opcode) == encoded)
        }
      }
    } finally org.apache.commons.io.FileUtils.deleteDirectory(work)
  }
}
