package riscvsim

import java.io.File
import java.nio.file.Files

/** Captured firmware and raw payloads. No device or reset-state claim is made. */
final class BootImage(elf: ElfFile, payloads: Seq[(File, Long)], ram: Seq[(Long, Long)]) {
  private case class Part(address: Long, data: Array[Byte], size: Long)
  private val raw = payloads.map { case (file, address) =>
    val bytes = Files.readAllBytes(file.toPath)
    (file, Part(address, bytes, bytes.length.toLong))
  }
  private val parts = elf.segments.map(s => Part(s.paddr, s.data, s.memsz)) ++ raw.map(_._2)
  require(parts.nonEmpty, "boot image is empty")
  parts.foreach { p =>
    require(p.address >= 0 && p.size > 0 && p.size <= Long.MaxValue - p.address, "invalid boot range")
    require(ram.exists { case (base, size) =>
      base >= 0 && size > 0 && size <= Long.MaxValue - base &&
        p.address >= base && p.address + p.size <= base + size
    }, "boot image is outside RAM")
  }
  parts.sortBy(_.address).sliding(2).foreach { pair =>
    if (pair.size == 2) require(pair.head.address + pair.head.size <= pair.last.address, "boot images overlap")
  }
  val layout: Seq[(Long, Long)] = parts.map(p => p.address -> p.size)
  val entry: Long = elf.entry
  val identities: Seq[(String, String)] = Seq(elf.file.getPath -> elf.sha256) ++
    raw.map { case (file, part) => file.getPath -> ElfFile.sha256(part.data) }
  /** Validation and capture finish before the first write. BSS is zero-filled in bounded chunks. */
  def load(write: (Long, Array[Byte]) => Unit): Unit = parts.foreach { p =>
    write(p.address, p.data.clone())
    var offset = p.data.length.toLong
    while (offset < p.size) {
      val count = math.min(65536L, p.size - offset).toInt
      write(p.address + offset, new Array[Byte](count))
      offset += count
    }
  }
}

object BootImage {
  /** Paths are relative to the manifest. Addresses are decimal or 0x strings. */
  def fromManifest(elf: ElfFile, file: File): BootImage = {
    val description = ujson.read(Files.readAllBytes(file.toPath))
    require(description("schema").str == "rvw.boot-payloads/1", "unknown boot payload schema")
    def address(v: ujson.Value): Long = java.lang.Long.decode(v.str).longValue()
    val payloads = description("payloads").arr.toSeq.map { p =>
      val source = Cli.file(file.getAbsoluteFile.getParentFile, p("file").str)
      source -> address(p("address"))
    }
    val ram = description("ram").arr.toSeq.map(p => address(p("base")) -> address(p("size")))
    new BootImage(elf, payloads, ram)
  }
}
