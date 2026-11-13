package rvwvexii

import java.io.File
import riscvsim.PluginDevice

/** Project device map. DeviceApiV1 has no core-specific address or interrupt routing. */
final class DeviceBus(description: File, library: File, seed: Long) extends AutoCloseable {
  private case class Region(base: Long, size: Long, routes: Seq[(Int, Int)], model: PluginDevice)
  private val descriptionJson = ujson.read(java.nio.file.Files.readString(description.toPath))
  private def number(value: ujson.Value): Long = value match {
    case ujson.Str(text) => java.lang.Long.decode(text)
    case _ => value.num.toLong
  }
  private val regions = descriptionJson("devices").arr.map { row =>
    Region(number(row("base")), number(row("size")), row("irq_map").arr.map { pair =>
      pair(0).num.toInt -> pair(1).num.toInt
    }.toSeq, new PluginDevice(library, row("config") match {
      case ujson.Str(path) => java.nio.file.Files.readString(new File(description.getParentFile, path).toPath)
      case value => ujson.write(value)
    }, seed))
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
  def close(): Unit = regions.foreach(_.model.close())
}
