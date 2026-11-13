package riscvsim

import java.io.File
import java.nio.file.Files
import org.scalatest.funsuite.AnyFunSuite

class InstructionPortSpec extends AnyFunSuite {
  def files(): (File, File) = {
    val dir = Files.createTempDirectory("instruction-port-")
    val binding = dir.resolve("port.json")
    val feed = dir.resolve("feed.json")
    Files.writeString(binding, """{"schema":"rvw.instruction-port/1","config":"test","word_bytes":4,
      "signals":{"cmd_valid":"valid","cmd_ready":"ready","address":"pc","rsp_valid":"response","rdata":"word"}}""")
    Files.writeString(feed, ujson.write(ujson.Obj("schema" -> "rvw.instruction-feed/1", "word_bytes" -> 4,
      "reference_elf_sha256" -> ("a" * 64), "words" -> ujson.Arr(ujson.Obj("address" -> "0x80000000", "data" -> "0x13")))))
    (binding.toFile, feed.toFile)
  }
  test("file source supplies exact words and faults on unlisted addresses") {
    val (binding, file) = files()
    val mode = InstructionMode.load(binding, file, "test")
    assert(mode.feed.response(BigInt("80000000", 16)).contains((BigInt(0x13), false)))
    assert(mode.feed.response(BigInt("80000004", 16)).contains((BigInt(0), true)))
  }
  test("binding refuses another config and a changed bus word width") {
    val (binding, file) = files()
    intercept[IllegalArgumentException](InstructionMode.load(binding, file, "other"))
    Files.writeString(file.toPath, Files.readString(file.toPath).replace("word_bytes\":4", "word_bytes\":8"))
    intercept[IllegalArgumentException](InstructionMode.load(binding, file, "test"))
  }
  test("source refuses duplicate addresses") {
    val (binding, file) = files()
    val data = ujson.read(Files.readString(file.toPath))
    data("words").arr += data("words")(0)
    Files.writeString(file.toPath, ujson.write(data))
    intercept[IllegalArgumentException](InstructionMode.load(binding, file, "test"))
  }
}
