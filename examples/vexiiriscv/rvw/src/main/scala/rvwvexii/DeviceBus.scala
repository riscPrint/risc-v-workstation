package rvwvexii

import java.io.File
import riscvsim.PluginDevice

/** Project device map. DeviceApiV1 has no core-specific address or interrupt routing. */
final class DeviceBus(description: File, library: File, seed: Long) extends AutoCloseable {
  private case class Region(base: Long, size: Long, routes: Seq[(Int, Int)], model: PluginDevice, kind: String, config: ujson.Value)
  private val descriptionJson = ujson.read(java.nio.file.Files.readString(description.toPath))
  private def number(value: ujson.Value): Long = value match {
    case ujson.Str(text) => java.lang.Long.decode(text)
    case _ => value.num.toLong
  }
  private val regions = descriptionJson("devices").arr.map { row =>
    val config = row("config") match {
      case ujson.Str(path) => java.nio.file.Files.readString(new File(description.getParentFile, path).toPath)
      case value => ujson.write(value)
    }
    Region(number(row("base")), number(row("size")), row("irq_map").arr.map { pair =>
      pair(0).num.toInt -> pair(1).num.toInt
    }.toSeq, new PluginDevice(library, config, seed), ujson.read(config)("model").str, ujson.read(config))
  }.toSeq
  private def region(address: Long, bytes: Int) =
    regions.find(r => address >= r.base && address + bytes <= r.base + r.size)
  def contains(address: Long, bytes: Int): Boolean = region(address, bytes).nonEmpty
  def read(address: Long, bytes: Int): BigInt = {
    val r = region(address, bytes).getOrElse(throw new IllegalArgumentException("unmapped device read"))
    r.model.read(address - r.base, bytes)
  }
  def write(address: Long, bytes: Int, value: BigInt): Unit = {
    val r = region(address, bytes).getOrElse(throw new IllegalArgumentException("unmapped device write"))
    r.model.write(address - r.base, bytes, value, (BigInt(1) << bytes) - 1)
  }
  def tick(cycle: Long): BigInt = regions.foldLeft(BigInt(0)) { (levels, region) =>
    val outputs = region.model.tick(cycle)
    levels | region.routes.foldLeft(BigInt(0)) { case (bits, (source, target)) =>
      if (outputs.testBit(source)) bits.setBit(target) else bits
    }
  }
  /** Drive input `input` of the one device of model `kind` (for example a PLIC source). */
  def setInput(kind: String, input: Int, level: Boolean): Unit = regions.filter(_.kind == kind) match {
    case Seq(r) => r.model.setInput(input, level)
    case found => throw new IllegalArgumentException(s"stimulus needs exactly one $kind device, found ${found.size}")
  }
  def isPlic(address: Long, bytes: Int): Boolean = region(address, bytes).exists(_.kind == "plic")
  def plicEvidence: Option[ujson.Obj] = regions.filter(_.kind == "plic") match {
    case Seq(r) =>
      val layout = ujson.Obj.from(r.config("map").obj.toSeq)
      for (key <- Seq("priority", "pending", "enable", "context"))
        layout(key) = RiscvNumber(r.base + number(layout(key)))
      Some(ujson.Obj("schema" -> "rvw.external-interrupts/1", "plic" -> layout,
        "routes" -> ujson.Arr.from(r.routes.map { case (context, pin) => ujson.Arr(context, pin) })))
    case _ => None
  }
  private def RiscvNumber(value: Long): ujson.Value = ujson.Num(value.toDouble)
  def close(): Unit = regions.foreach(_.model.close())
}
