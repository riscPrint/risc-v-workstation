package riscvsim

import java.io.File
import java.nio.file.Files

/** Immutable per-hart inputs captured before model compilation. */
final class HartImages(val harts: Seq[(Int, ElfFile)], xlen: Int) {
  require(harts.size >= 2 && harts.map(_._1).distinct.size == harts.size)
  require(harts.forall { case (id, elf) => id >= 0 && elf.xlen == xlen })
  private val parts = harts.flatMap(_._2.segments).filter(_.memsz > 0)
  // Identical shared segments are allowed. Conflicting images, including BSS, are not.
  private val unique = parts.foldLeft(Vector.empty[(Long, Array[Byte], Long)]) { (out, s) =>
    out.find { case (a, _, size) => a == s.paddr && size == s.memsz } match {
      case Some((_, data, _)) if data.sameElements(s.data) => out
      case _ => out :+ ((s.paddr, s.data, s.memsz))
    }
  }.sortBy(_._1)
  unique.sliding(2).filter(_.size == 2).foreach { p =>
    require(p.head._1 + p.head._3 <= p.last._1, "hart ELF segments overlap with different contents")
  }
  require(unique.nonEmpty, "hart images have no loadable memory")
  val identity: ujson.Arr = ujson.Arr.from(harts.map { case (id, elf) =>
    ujson.Obj("hart" -> id, "elf" -> elf.file.getPath, "elf_sha256" -> elf.sha256, "entry" -> Hex(elf.entry))
  })
  def load(write: (Long, Array[Byte]) => Unit): Unit = unique.foreach { case (address, data, size) =>
    write(address, data.clone())
    var offset = data.length.toLong
    while (offset < size) {
      val count = math.min(65536L, size - offset).toInt
      write(address + offset, new Array[Byte](count)); offset += count
    }
  }
}
object HartImages {
  def capture(file: File, ids: Seq[Int], xlen: Int): HartImages = {
    val doc = ujson.read(Files.readAllBytes(file.toPath))
    require(doc("schema").str == "rvw.hart-images/1", "unknown hart image schema")
    val rows = doc("harts").arr.toSeq.map { row =>
      val id = row("hart").num
      require(id >= 0 && id <= Int.MaxValue && id == id.toInt.toDouble, "invalid hart ID")
      val elf = new ElfFile(Cli.file(file.getAbsoluteFile.getParentFile, row("elf").str))
      require(elf.sha256 == row("elf_sha256").str, "hart ELF hash changed")
      id.toInt -> elf
    }
    require(rows.map(_._1).toSet == ids.toSet, "hart images differ from adapter harts")
    new HartImages(rows.sortBy(_._1), xlen)
  }
}

/** Shared adapter service: sample RVFI per hart, never sort different harts by order. */
final class MultiHartSession(ctx: RunContext, probes: Map[Int, RvfiProbe],
    dependenciesComplete: Boolean = false,
    annotate: (Int, RvfiRecord) => Option[ujson.Obj] = (_, _) => None,
    addressesPhysical: Boolean = false) extends AutoCloseable {
  val images = ctx.hartImages.getOrElse(throw new IllegalArgumentException("hart images required"))
  require(probes.keySet == images.harts.map(_._1).toSet)
  private val trace = new MultiHartTrace(new File(ctx.job.out, "rvfi.jsonl"),
    ujson.Obj.from(ctx.rvfiHeader.value.toSeq :+ ("hart_images" -> images.identity) :+ ("memory_dependencies" -> ujson.Str(if (dependenciesComplete) "complete" else "unavailable")) :+
      ("memory_addresses" -> ujson.Str(if (addressesPhysical) "physical" else "unavailable"))), probes.keys.toSeq.sorted)
  private val active = scala.collection.mutable.Set.empty[Int]
  private var retired = 0L
  def reset(hart: Int, cycle: Long): Unit = { trace.reset(hart, cycle); active += hart }
  def sample(cycle: Long): Unit = active.toSeq.sorted.foreach { h =>
    probes(h).sample(cycle).foreach { r => trace.retire(h, r, annotate(h, r)); retired += 1 }
  }
  def complete(hart: Int, cycle: Long, status: Status): Unit = {
    trace.complete(hart, cycle, status); active -= hart
  }
  def memory(cycle: Long, id: String, action: String, payload: ujson.Obj): Unit =
    trace.memory(cycle, id, action, payload)
  def outcome(cycle: Long): RunOutcome = trace.outcome(cycle, retired)
  def close(): Unit = trace.close()
}
