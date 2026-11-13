package riscvsim

import spinal.core._
import spinal.lib.bus.tilelink.OrderingTag
import spinal.lib.bus.tilelink.fabric._
import spinal.lib.bus.tilelink.sim._
import spinal.lib.sim.SparseMemory
import scala.collection.mutable

/** Keep the native test operations the same across the two pinned SDK APIs. */
object TileLinkSdkCompat {
  private val exclusion = try {
    Some(Class.forName("spinal.lib.bus.tilelink.fabric.sim.tilelinkTesterExcluded$")
      .getField("MODULE$").get(null).asInstanceOf[SpinalTag])
  } catch { case _: ClassNotFoundException => None }
  def excluded(node: Node): Boolean = exclusion.exists(node.hasTag(_))

  type Master = { val agent: MasterAgent; val monitor: Monitor }
  type Slave = { val model: MemoryAgent }
  type Bench = {
    val nodeToModel: mutable.LinkedHashMap[Node, SparseMemory]
    val masterNodes: scala.collection.Seq[Node]
    val mastersStuff: scala.collection.Seq[Master]
    val slavesStuff: scala.collection.Seq[Slave]
    def waitCheckers(): Unit
  }
  def testbench(nodes: scala.collection.Seq[Node], orderings: scala.collection.Seq[OrderingTag], dut: Component)
               (implicit ids: IdAllocator, callback: IdCallback): Bench = {
    val cls = Class.forName("spinal.lib.bus.tilelink.fabric.sim.TilelinkTestbenchBase")
    val constructor = cls.getConstructors.find(_.getParameterCount == 5)
      .orElse(cls.getConstructors.find(_.getParameterCount == 4)).get
    val args = if (constructor.getParameterCount == 5) Array[AnyRef](nodes, orderings, dut, ids, callback)
               else Array[AnyRef](nodes, orderings, ids, callback)
    constructor.newInstance(args: _*).asInstanceOf[Bench]
  }
}
