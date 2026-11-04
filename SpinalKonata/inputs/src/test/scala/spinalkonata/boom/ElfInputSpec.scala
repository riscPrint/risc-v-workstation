package spinalkonata.boom

import java.nio.{ByteBuffer, ByteOrder}
import java.nio.file.{Files, StandardCopyOption}
import org.scalatest.funsuite.AnyFunSuite

class ElfInputSpec extends AnyFunSuite {
  // One ELF64 PT_LOAD segment. No compiler or BOOM model is needed.
  private def program(value: Byte): Array[Byte] = {
    val bytes = new Array[Byte](128)
    val b = ByteBuffer.wrap(bytes).order(ByteOrder.LITTLE_ENDIAN)
    b.put(0, 0x7f.toByte); b.put(1, 'E'.toByte); b.put(2, 'L'.toByte); b.put(3, 'F'.toByte)
    b.put(4, 2.toByte); b.put(5, 1.toByte)
    b.putShort(0x10, 2.toShort); b.putShort(0x12, 243.toShort)
    b.putLong(0x18, 0x80000000L); b.putLong(0x20, 64L)
    b.putShort(0x36, 56.toShort); b.putShort(0x38, 1.toShort)
    b.putInt(64, 1); b.putLong(72, 120L); b.putLong(88, 0x80000000L)
    b.putLong(96, 8L); b.putLong(104, 8L); bytes(120) = value
    bytes
  }

  for (replace <- Seq(false, true)) test(s"one ELF capture serves loading, disassembly and hash: replace=$replace") {
    val dir = Files.createTempDirectory("konata-elf")
    val path = dir.resolve("input.elf")
    val before = program(1)
    Files.write(path, before)
    val input = ElfInput.capture(path.toFile, dir.resolve("inputs").toFile)
    // Named load/disassembly boundary. Edit-and-revert must not enter the snapshot.
    val changed = program(2)
    if (replace) {
      val replacement = dir.resolve("replacement")
      Files.write(replacement, changed)
      Files.move(replacement, path, StandardCopyOption.REPLACE_EXISTING)
    } else Files.write(path, changed)
    var loaded: Array[Byte] = Array.emptyByteArray
    input.elf.load((_, data) => loaded = data)
    val disassembled = input.elf.withSnapshotFile(dir.toFile)(f => Files.readAllBytes(f.toPath))
    Files.write(path, before)
    assert(loaded(0) == 1)
    assert(disassembled.sameElements(before))
    assert(input.elf.sha256 == riscvsim.ElfFile.sha256(before))
    assert(input.record("sha256").str == input.elf.sha256)
    assert(input.record("resolved").str == path.toRealPath().toString)
  }

  test("tool edit-and-revert refuses publication") {
    val dir = Files.createTempDirectory("konata-tool")
    val tool = dir.resolve("objdump")
    val bytes = "#!/bin/sh\necho fixture\n".getBytes("UTF-8")
    Files.write(tool, bytes); tool.toFile.setExecutable(true)
    val captured = ToolInput.capture(tool.toString, dir.toFile)
    Files.write(tool, "#!/bin/sh\necho changed\n".getBytes("UTF-8"))
    Files.write(tool, bytes)
    intercept[IllegalArgumentException](captured.verify())
  }
}
