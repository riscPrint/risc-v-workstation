package riscvsim

import java.io.{ByteArrayInputStream, ByteArrayOutputStream}
import org.scalatest.funsuite.AnyFunSuite

class ByteMemorySnapshotSpec extends AnyFunSuite {
  test("RAM image restores every byte and checks the exact length") {
    val memory = new ByteMemory(0x80000000L, 16)
    memory(0x80000000L) = 128; memory(0x8000000fL) = 255
    val out = new ByteArrayOutputStream
    memory.save(out)
    val restored = new ByteMemory(0x80000000L, 16)
    restored.restore(new ByteArrayInputStream(out.toByteArray))
    assert(restored.getOrElse(0x80000000L, 0) == 128)
    assert(restored.getOrElse(0x8000000fL, 0) == 255)
    assert(restored.sha256 == memory.sha256)
    val digest = restored.sha256
    intercept[IllegalArgumentException](restored.restore(new ByteArrayInputStream(new Array[Byte](15))))
    intercept[IllegalArgumentException](restored.restore(new ByteArrayInputStream(new Array[Byte](17))))
    assert(restored.sha256 == digest)
  }
}
