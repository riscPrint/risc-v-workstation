package ooomini

import java.io.File
import riscvsim.PluginDevice

/** Project-owned address windows and interrupt routes for standard device plugins. */
final class ProjectDevices(description: File, library: File, seed: Long) extends AutoCloseable {
  private def number(v: ujson.Value): Long = v match {
    case ujson.Str(s) => java.lang.Long.decode(s)
    case _ => v.num.toLong
  }
  private case class Region(base: Long, size: Long, routes: Seq[(Int,Int)],
                            config: ujson.Value, initial: Seq[Int], model: PluginDevice)
  private val regions = ujson.read(java.nio.file.Files.readString(description.toPath))("devices").arr.map { row =>
    val text = row("config") match {
      case ujson.Str(path) => java.nio.file.Files.readString(new File(description.getParentFile,path).toPath)
      case value => ujson.write(value)
    }
    val config = ujson.read(text)
    val initial = row.obj.get("initial_levels").map(_.arr.map(_.num.toInt).toSeq).getOrElse(Seq.empty)
    require(config("model").str != "plic" || config.obj.get("levels").forall(_.arr.isEmpty),
      "scheduled PLIC sources need a stimulus evidence binding")
    val model = new PluginDevice(library,text,seed)
    initial.foreach(source => model.setInput(source,true))
    Region(number(row("base")),number(row("size")),row("irq_map").arr.map(p => p(0).num.toInt -> p(1).num.toInt).toSeq,
      config,initial,model)
  }.toSeq
  private def region(address: Long, bytes: Int) = regions.find(r => address >= r.base && address+bytes <= r.base+r.size)
  def contains(address: Long, bytes: Int): Boolean = region(address,bytes).nonEmpty
  def isPlic(address: Long, bytes: Int): Boolean = region(address,bytes).exists(_.config("model").str == "plic")
  def read(address: Long, bytes: Int): BigInt = {
    val r = region(address,bytes).getOrElse(throw new IllegalArgumentException("unmapped device read"))
    r.model.read(address-r.base,bytes)
  }
  def write(address: Long, bytes: Int, value: BigInt): Unit = {
    val r = region(address,bytes).getOrElse(throw new IllegalArgumentException("unmapped device write"))
    r.model.write(address-r.base,bytes,value,(BigInt(1)<<bytes)-1)
  }
  def tick(cycle: Long): BigInt = regions.foldLeft(BigInt(0)) { (levels,r) =>
    val pins = r.model.tick(cycle)
    levels | r.routes.foldLeft(BigInt(0)) { case (bits,(source,target)) => if(pins.testBit(source)) bits.setBit(target) else bits }
  }
  val plicEvidence: Option[ujson.Obj] = regions.filter(_.config("model").str == "plic") match {
    case Seq(r) =>
      val layout = ujson.Obj.from(r.config("map").obj.toSeq)
      for(key <- Seq("priority","pending","enable","context")) layout(key) = ujson.Num((r.base+number(layout(key))).toDouble)
      Some(ujson.Obj("schema" -> "rvw.external-interrupts/1","plic" -> layout,
        "routes" -> ujson.Arr.from(r.routes.map { case (context,pin) => ujson.Arr(context,pin) }),
        "initial_levels" -> ujson.Arr.from(r.initial),"stimulus" -> ujson.Arr()))
    case Seq() => None
    case _ => throw new IllegalArgumentException("one PLIC is supported")
  }
  def close(): Unit = regions.foreach(_.model.close())
}
