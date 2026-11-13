package riscvsim

import java.nio.file.Files
import org.scalatest.funsuite.AnyFunSuite
import spinal.core._
import spinal.core.sim._
import spinal.lib.bus.tilelink.Opcode

class SimEncodingSpec extends AnyFunSuite {
  test("read all 64 unsigned wire bits without signed-Long range checks") {
    class Top extends Component {
      val io = new Bundle { val address = in UInt(64 bits) }
    }
    val work = Files.createTempDirectory("rv64-wire").toFile
    try {
      SimConfig.withVerilator.workspacePath(work.getPath).compile(new Top).doSim { dut =>
        for (value <- Seq(BigInt(0), BigInt("80000000", 16), BigInt(1) << 63, (BigInt(1) << 64) - 1)) {
          dut.io.address #= value
          sleep(1)
          assert(SimEncoding.longBits(dut.io.address) == value.toLong)
        }
      }
    } finally org.apache.commons.io.FileUtils.deleteDirectory(work)
  }

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
