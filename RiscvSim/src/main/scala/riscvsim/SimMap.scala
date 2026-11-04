package riscvsim

import java.io.{File, PrintWriter}
import java.nio.file.Files
import java.security.MessageDigest

/** Captured generated map. Adapters own device semantics and reject unsupported placements. */
case class SimRegion(name: String, kind: String, base: BigInt, size: BigInt, permissions: String,
                     registers: Seq[ujson.Value]) {
  def contains(a: BigInt, n: BigInt): Boolean = n > 0 && a >= base && a + n <= base + size
}
case class SimMap(file: File, sha256: String, regions: Seq[SimRegion], bytes: Array[Byte]) {
  def region(a: BigInt, n: BigInt, permission: Char): Option[SimRegion] =
    regions.find(r => r.contains(a, n) && r.permissions.contains(permission))
  def register(regionName: String, name: String): Long = {
    val r = regions.find(_.name == regionName).getOrElse(throw new IllegalArgumentException(s"missing region $regionName"))
    val g = r.registers.find(_("name").str == name).getOrElse(throw new IllegalArgumentException(s"missing register $name"))
    (r.base + SimMap.number(g("offset"))).toLong
  }
  def reset(regionName: String, name: String): Long = {
    val r = regions.find(_.name == regionName).get
    val g = r.registers.find(_("name").str == name).get
    require(g("access").str == "rw" && g("read_action").str == "none" && g("write_action").str == "normal",
      "unsupported device register semantics")
    SimMap.number(g("reset")).toLong
  }
  def save(out: File): Unit = Files.write(new File(out, "sim-map.json").toPath, bytes)
}
object SimMap {
  def number(v: ujson.Value): BigInt = v match {
    case ujson.Str(s) => if (s.startsWith("0x")) BigInt(s.drop(2), 16) else BigInt(s)
    case ujson.Num(n) if n.isWhole && math.abs(n) <= 9007199254740991d => BigInt(n.toLong)
    case _ => throw new IllegalArgumentException("map integer must be exact")
  }
  def load(file: File): SimMap = {
    val bytes = Files.readAllBytes(file.toPath)
    val obj = ujson.read(bytes)
    require(obj("schema").str == "rvw.sim-map/1", "requires rvw.sim-map/1")
    val rawBits = number(obj("address_bits"))
    require(rawBits >= 1 && rawBits <= 64, "invalid address width")
    val bits = rawBits.toInt
    val regions = obj("regions").arr.toSeq.map { r =>
      val b = number(r("base")); val s = number(r("size"))
      require(b >= 0 && s > 0 && b + s <= (BigInt(1) << bits), "invalid region bounds")
      require((s & (s - 1)) == 0 && b % s == 0, "invalid decode window")
      require(Set("ram", "mmio")(r("kind").str), "invalid region kind")
      require(Set("r", "rw", "rx", "rwx")(r("permissions").str), "invalid permissions")
      require(r("cacheable").isInstanceOf[ujson.Bool], "invalid cacheable flag")
      val regs = r("registers").arr.toSeq
      require(regs.map(_("name").str).distinct.size == regs.size, "duplicate registers")
      val spans = regs.map { g =>
        val rawWidth = number(g("width"))
        require(Set(BigInt(8), BigInt(16), BigInt(32), BigInt(64))(rawWidth), "invalid register width")
        val width = rawWidth.toInt
        val offset = number(g("offset"))
        require(Set(8, 16, 32, 64)(width), "invalid register width")
        require(offset >= 0 && offset % (width / 8) == 0 && offset + width / 8 <= s, "invalid register bounds")
        require(Set("r", "w", "rw")(g("access").str), "invalid register access")
        require(Set("none", "clear")(g("read_action").str) && Set("normal", "one_to_clear")(g("write_action").str), "invalid register actions")
        if (g("reset") != ujson.Null) {
          val reset = number(g("reset"))
          require(reset >= 0 && reset < (BigInt(1) << width), "invalid register reset")
        }
        (offset, BigInt(width / 8))
      }.sortBy(_._1)
      spans.sliding(2).filter(_.size == 2).foreach(p => require(p.head._1 + p.head._2 <= p.last._1, "overlapping registers"))
      require(r("kind").str == "mmio" || regs.isEmpty, "RAM cannot have registers")
      SimRegion(r("name").str, r("kind").str, b, s, r("permissions").str, r("registers").arr.toSeq)
    }
    require(regions.nonEmpty && regions.map(_.name).distinct.size == regions.size, "invalid region names")
    regions.sortBy(_.base).sliding(2).filter(_.size == 2).foreach(p => require(p.head.base + p.head.size <= p.last.base, "overlapping regions"))
    SimMap(file, MessageDigest.getInstance("SHA-256").digest(bytes).map(b => f"${b & 255}%02x").mkString, regions, bytes)
  }
}

/** Captures accepted bus requests and the endpoint selected by the harness.
  * These are harness endpoint observations, not retirement-to-bus pairs. */
class MapCapture(map: SimMap, job: RunJob, ctx: RunContext) extends AutoCloseable {
  map.save(job.out)
  private val writer = new PrintWriter(new File(job.out, "soc-transactions.jsonl"))
  private def emit(v: ujson.Value): Unit = { writer.println(v.render()); writer.flush() }
  emit(ujson.Obj("schema" -> "rvw.soc-capture/1", "map_sha256" -> map.sha256, "identity" -> ctx.rvfiHeader))
  def request(cycle: Long, bus: String, address: BigInt, size: BigInt, write: Boolean,
              selected: Option[SimRegion]): Unit = emit(ujson.Obj("cycle" -> cycle.toString, "bus" -> bus,
    "address" -> Hex(address), "size" -> size.toString, "write" -> write,
    "selected" -> selected.map(r => ujson.Str(r.name)).getOrElse(ujson.Null)))
  def close(): Unit = { emit(ujson.Obj("event" -> "end")); writer.close() }
}
