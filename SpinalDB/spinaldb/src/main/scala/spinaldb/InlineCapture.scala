package spinaldb

import spinal.core._
import spinal.core.internals._

/** Read each inline body once before the emitter. Never call a live implementation at extraction. */
private[spinaldb] object InlineCapture {
  final class Body(val text: String) extends BlackBoxImpl {
    override def getVerilog(): String = text
  }

  def text(bb: BlackBox): Either[String, Seq[(String, String)]] = bb.impl match {
    case null => Right(Nil)
    case b: Body if b.getClass == classOf[Body] => Right(Seq("verilog" -> b.text))
    case _ => Left("input_not_captured:inline: elaborate with SpinalDB.elaborate before writing")
  }

  class BeforeEmission extends PhaseNetlist {
    override def impl(pc: PhaseContext): Unit = {
      def walk(c: Component): Unit = {
        c match {
          case bb: BlackBox if bb.impl != null =>
            // The original may read a file or vary on each call. The emitter sees only this value.
            bb.impl = new Body(bb.impl.getVerilog())
          case _ =>
        }
        c.children.foreach(walk)
      }
      walk(pc.topLevel)
    }
  }

  def instrument(config: SpinalConfig): SpinalConfig = {
    val inserters = config.phasesInserters.clone()
    inserters += { phases =>
      val at = phases.indexWhere(_.isInstanceOf[PhaseVerilog])
      require(at >= 0, "SpinalDB: Verilog emission phase not found")
      phases.insert(at, new BeforeEmission)
    }
    config.copy(phasesInserters = inserters)
  }
}
