package riscvsim

import java.nio.{ByteBuffer, ByteOrder}
import java.nio.file.Files
import org.scalatest.funsuite.AnyFunSuite

class BootImageSpec extends AnyFunSuite {
  def image(kind: Int = 3, memsz: Long = 8, interp: Boolean = false): java.io.File = {
    val d = new Array[Byte](260)
    val b = ByteBuffer.wrap(d).order(ByteOrder.LITTLE_ENDIAN)
    b.putInt(0, 0x464c457f); d(4) = 2; d(5) = 1
    b.putShort(16, kind.toShort); b.putShort(18, 243.toShort)
    b.putLong(24, 0x100); b.putLong(32, 64)
    b.putShort(54, 56); b.putShort(56, 1)
    b.putInt(64, if (interp) 3 else 1)
    b.putLong(72, 256); b.putLong(80, 0x100); b.putLong(88, 0x100)
    b.putLong(96, 4); b.putLong(104, memsz)
    d(256) = 42
    val path = Files.createTempFile("boot-image", ".elf")
    path.toFile.deleteOnExit(); Files.write(path, d); path.toFile
  }
  test("self-relocating PIE loads with an explicit bias and zero BSS") {
    val e = new ElfFile(image(), 0x80000000L)
    assert(e.entry == 0x80000100L)
    val writes = scala.collection.mutable.Map[Long, Byte]()
    e.load((a, d) => d.indices.foreach(i => writes(a + i) = d(i)))
    assert(writes(0x80000100L) == 42 && writes(0x80000107L) == 0)
  }
  test("reject ET_REL, dynamic interpreter, EXEC bias and invalid segment sizes") {
    intercept[IllegalArgumentException](new ElfFile(image(kind = 1)))
    intercept[IllegalArgumentException](new ElfFile(image(interp = true)))
    intercept[IllegalArgumentException](new ElfFile(image(kind = 2), 4096))
    intercept[IllegalArgumentException](new ElfFile(image(memsz = 2)))
  }
  test("firmware, kernel and DTB capture immutable nonoverlapping payloads") {
    val kernel = Files.createTempFile("kernel", ".bin"); kernel.toFile.deleteOnExit()
    val dtb = Files.createTempFile("device", ".dtb"); dtb.toFile.deleteOnExit()
    Files.write(kernel, Array[Byte](1, 2)); Files.write(dtb, Array[Byte](3, 4))
    val boot = new BootImage(new ElfFile(image(), 0x80000000L),
      Seq(kernel.toFile -> 0x80200000L, dtb.toFile -> 0x87e00000L), Seq(0x80000000L -> 0x8000000L))
    Files.write(kernel, Array[Byte](9))
    val writes = scala.collection.mutable.Map[Long, Byte]()
    boot.load((a, d) => d.indices.foreach(i => writes(a + i) = d(i)))
    assert(writes(0x80200000L) == 1 && writes(0x87e00001L) == 4)
    assert(boot.identities.size == 3)
    assert(boot.identities(1)._2 == ElfFile.sha256(Array[Byte](1, 2)))
  }
  test("reject overlap including BSS, outside RAM and address overflow before writes") {
    val raw = Files.createTempFile("payload", ".bin"); raw.toFile.deleteOnExit()
    Files.write(raw, Array[Byte](1, 2))
    val e = new ElfFile(image(), 0x80000000L)
    for (a <- Seq(0x80000106L, 0x90000000L, Long.MaxValue))
      intercept[IllegalArgumentException](new BootImage(e, Seq(raw.toFile -> a), Seq(0x80000000L -> 0x8000000L)))
  }
  test("driver captures payloads before compile and passes them to the adapter") {
    val dir = Files.createTempDirectory("boot-driver").toFile
    try {
      val kernel = new java.io.File(dir, "kernel")
      Files.write(kernel.toPath, Array[Byte](7, 8))
      val manifest = new java.io.File(dir, "loads.json")
      Files.writeString(manifest.toPath, ujson.write(ujson.Obj(
        "schema" -> "rvw.boot-payloads/1",
        "ram" -> ujson.Arr(ujson.Obj("base" -> "0x80000000", "size" -> "0x08000000")),
        "payloads" -> ujson.Arr(ujson.Obj("file" -> "kernel", "address" -> "0x80200000")))))
      val memory = scala.collection.mutable.Map[Long, Byte]()
      val adapter = new CoreAdapter {
        type Model = Unit
        override def supportsBootPayloads = true
        def core = "boot-fixture"
        def configs = Seq("test")
        def isa(config: String) = "rv64i"
        def xlen = 64
        def sourceDir = dir
        def compile(key: ModelKey, work: java.io.File, cache: java.io.File): Unit = {
          Files.write(kernel.toPath, Array[Byte](99)); ()
        }
        def run(model: Unit, job: RunJob, ctx: RunContext): RunOutcome = {
          ctx.loadMemory((a, d) => d.indices.foreach(i => memory(a + i) = d(i)))
          RunOutcome(Status.Timeout, 10, 2)
        }
      }
      val options = Map("elf" -> image().getPath, "out" -> new java.io.File(dir, "out").getPath,
        "seed" -> "1", "elf-load-bias" -> "2147483648", "boot-payloads" -> manifest.getPath)
      val job = Cli.job(options, adapter, dir)
      val driver = new Driver(adapter)
      val result = driver.runJobs(Seq(job), 1).head
      assert(memory(0x80200000L) == 7)
      assert(result("details")("boot_payloads").arr.size == 2)
      assert(result("elf_load_bias").str == "2147483648")
      assert(driver.replay(job).contains("--boot-payloads"))

    } finally org.apache.commons.io.FileUtils.deleteDirectory(dir)
  }

  test("ELF alone rejects overlapping segments including BSS") {
    for (address <- Seq(0x100L, 0x106L)) {
      val file = image()
      val data = Files.readAllBytes(file.toPath)
      val b = ByteBuffer.wrap(data).order(ByteOrder.LITTLE_ENDIAN)
      b.putShort(56, 2)
      b.putInt(120, 1); b.putLong(128, 256)
      b.putLong(136, address); b.putLong(144, address)
      b.putLong(152, 4); b.putLong(160, 8)
      Files.write(file.toPath, data)
      intercept[IllegalArgumentException](new ElfFile(file))
    }
  }
  test("ELF rejects a short program header stride") {
    val file = image()
    val data = Files.readAllBytes(file.toPath)
    ByteBuffer.wrap(data).order(ByteOrder.LITTLE_ENDIAN).putShort(54, 0)
    Files.write(file.toPath, data)
    intercept[IllegalArgumentException](new ElfFile(file))
  }
  test("ELF32 bias cannot overflow its address width") {
    val file = image()
    val data = Files.readAllBytes(file.toPath)
    val b = ByteBuffer.wrap(data).order(ByteOrder.LITTLE_ENDIAN)
    data(4) = 1
    b.putInt(24, 0x100); b.putInt(28, 52)
    b.putShort(42, 32); b.putShort(44, 1)
    b.putInt(52, 1); b.putInt(56, 256); b.putInt(60, 0x100); b.putInt(64, 0x100)
    b.putInt(68, 4); b.putInt(72, 8)
    Files.write(file.toPath, data)
    intercept[IllegalArgumentException](new ElfFile(file, 0x100000000L))
  }

}
