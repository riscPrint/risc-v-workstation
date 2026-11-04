package riscvsim

import java.io.File
import java.nio.{ByteBuffer, ByteOrder}
import java.nio.file.Files
import java.security.MessageDigest

/**
 * Minimal little-endian ELF reader (ELF32 and ELF64): loadable segments, symbols, entry.
 * Enough to load a bare-metal RISC-V program into a simulation memory.
 */
final class ElfFile(val file: File, val loadBias: Long = 0L) {
  private val contents: Array[Byte] = Files.readAllBytes(file.toPath)
  private val bb = ByteBuffer.wrap(contents).order(ByteOrder.LITTLE_ENDIAN)
  require(contents.length > 52 && contents(0) == 0x7f && contents(1) == 'E' && contents(2) == 'L' && contents(3) == 'F',
    s"$file is not an ELF file")
  require(contents(5) == 1, s"$file is not little-endian")

  /** 32 or 64. */
  val xlen: Int = contents(4) match {
    case 1 => 32
    case 2 => 64
    case c => throw new IllegalArgumentException(s"$file: unknown ELF class $c")
  }
  private val is64 = xlen == 64
  val machine: Int = u16(0x12)
  require(machine == 243, s"$file is not a RISC-V ELF (e_machine $machine)")

  private def u16(o: Long): Int = bb.getShort(o.toInt) & 0xffff
  private def u32(o: Long): Long = bb.getInt(o.toInt).toLong & 0xffffffffL
  private def u64(o: Long): Long = bb.getLong(o.toInt)
  private def word(o: Long): Long = if (is64) u64(o) else u32(o)

  val elfType: Int = u16(0x10)
  require(elfType == 2 || elfType == 3, "only ET_EXEC and self-relocating ET_DYN images are supported")
  require(loadBias == 0 || elfType == 3, "load bias requires ET_DYN")
  require(loadBias >= 0, "load bias must be nonnegative")
  private def relocated(a: Long): Long = Math.addExact(a, loadBias)
  val entry: Long = relocated(word(0x18))
  private val phoff = if (is64) u64(0x20) else u32(0x1c)
  private val shoff = if (is64) u64(0x28) else u32(0x20)
  private val (phentsize, phnum, shentsize, shnum) =
    if (is64) (u16(0x36), u16(0x38), u16(0x3a), u16(0x3c)) else (u16(0x2a), u16(0x2c), u16(0x2e), u16(0x30))

  /** A PT_LOAD segment: physical address, file bytes, memory size (>= data length; the rest is zero). */
  case class Segment(paddr: Long, data: Array[Byte], memsz: Long)

  private val parsedSegments: Seq[Segment] = (0 until phnum).flatMap { i =>
    val h = phoff + i.toLong * phentsize
    require(u32(h) != 3, "PT_INTERP requires an unsupported dynamic linker")
    if (u32(h) != 1) None
    else {
      val (off, paddr, filesz, memsz) =
        if (is64) (u64(h + 0x08), u64(h + 0x18), u64(h + 0x20), u64(h + 0x28))
        else (u32(h + 0x04), u32(h + 0x0c), u32(h + 0x10), u32(h + 0x14))
      require(off >= 0 && filesz >= 0 && memsz >= filesz && off <= contents.length &&
        filesz <= contents.length - off && memsz <= Int.MaxValue, "invalid ELF load segment")
      val address = relocated(paddr)
      require(address >= 0 && memsz <= Long.MaxValue - address, "ELF address overflow")
      Some(Segment(address, java.util.Arrays.copyOfRange(contents, off.toInt, (off + filesz).toInt), memsz))
    }
  }

  /** Symbol name -> value, from every SHT_SYMTAB section. */
  lazy val symbols: Map[String, Long] = {
    val sections = (0 until shnum).map(i => shoff + i.toLong * shentsize)
    def shType(s: Long) = u32(s + 4)
    def shOffset(s: Long) = if (is64) u64(s + 0x18) else u32(s + 0x10)
    def shSize(s: Long) = if (is64) u64(s + 0x20) else u32(s + 0x14)
    def shLink(s: Long) = u32(s + (if (is64) 0x28 else 0x18))
    def shEntsize(s: Long) = if (is64) u64(s + 0x38) else u32(s + 0x24)
    sections.filter(shType(_) == 2).flatMap { s =>
      val strOff = shOffset(sections(shLink(s).toInt))
      (0L until shSize(s) / shEntsize(s)).map { k =>
        val e = shOffset(s) + k * shEntsize(s)
        val nameOff = u32(e)
        val value = if (is64) u64(e + 8) else u32(e + 4)
        var end = (strOff + nameOff).toInt
        while (contents(end) != 0) end += 1
        val section = u16(e + (if (is64) 6 else 14))
        new String(contents, (strOff + nameOff).toInt, end - (strOff + nameOff).toInt) ->
          (if (section == 0 || section == 0xfff1) value else relocated(value))
      }
    }.toMap
  }

  def symbol(name: String): Option[Long] = symbols.get(name)

  /** Writes every loadable segment (zero-filling .bss) through `write(address, bytes)`. */
  def load(write: (Long, Array[Byte]) => Unit): Unit =
    for (s <- parsedSegments) {
      write(s.paddr, s.data.clone())
      if (s.memsz > s.data.length) write(s.paddr + s.data.length, new Array[Byte]((s.memsz - s.data.length).toInt))
    }

  /** Copies keep callers from changing the captured input or later loads. */
  def bytes: Array[Byte] = contents.clone()
  def segments: Seq[Segment] = parsedSegments.map(s => s.copy(data = s.data.clone()))

  /** For tools that need a path. Consume it inside `use`; it is deleted on return or exception. */
  def withSnapshotFile[T](directory: File)(use: File => T): T = {
    val path = Files.createTempFile(directory.toPath, ".elf-snapshot-", ".elf")
    try {
      Files.write(path, contents)
      use(path.toFile)
    } finally Files.deleteIfExists(path)
  }

  lazy val sha256: String = ElfFile.sha256(contents)
}

object ElfFile {
  def apply(path: String): ElfFile = new ElfFile(new File(path))
  def sha256(bytes: Array[Byte]): String =
    MessageDigest.getInstance("SHA-256").digest(bytes).map(b => f"${b & 0xff}%02x").mkString
}
