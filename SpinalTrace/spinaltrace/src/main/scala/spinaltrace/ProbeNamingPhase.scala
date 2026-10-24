package spinaltrace

import spinal.core._
import spinal.core.internals._

import scala.collection.mutable

/** Early SpinalTrace phase (inserted right after Spinal's reflection naming).
  *
  * Gives a name to the *existing* anonymous signals the trace engine has to read back from the VCD:
  * `when` conditions, `switch` values and non-literal keys, mux selects, dynamic bit/range/Vec indexes
  * and memory port address/enable signals. Naming them stops Spinal from inlining them into
  * expressions, so they become plain wires in the RTL (and hence in the VCD). No logic is added.
  *
  * Names follow Spinal's own `when_<File>_l<line>` convention with a role prefix and use the
  * REMOVABLE priority, so any user name wins. Every renamed signal gets [[SpinalTraceNamedTag]].
  */
class ProbeNamingPhase extends PhaseNetlist {
  val named = mutable.ArrayBuffer[BaseType]()

  override def impl(pc: PhaseContext): Unit = {
    // Same notion as the extractor (Netlist.isGenerated) at this stage: anonymous or a Spinal
    // REMOVABLE auto-name such as `when_Vec_l90`, so both recognise the same dynamic Vec writes.
    val generated: BaseType => Boolean = bt => bt.isUnnamed || SpinalTraceAccess.namePriority(bt) == Nameable.REMOVABLE

    def name(e: Expression, role: String): Unit = e match {
      case bt: BaseType if bt.isUnnamed && !Netlist.isLiteralDriven(bt) => doName(bt, role)
      case _                                                            =>
    }

    def doName(bt: BaseType, role: String): Unit = {
      val (file, line) = Locations.fileSymbol(bt.getScalaTrace()).getOrElse(("x", 0))
      bt.unsetName()
      // File names may hold characters Verilog names cannot (BOOM's frontend-types.scala)
      val tag = file.map(c => if (c.isLetterOrDigit || c == '_') c else '_')
      bt.setName(s"${role}_${tag}_l$line", Nameable.REMOVABLE)
      bt.addTag(SpinalTraceNamedTag)
      named += bt
    }

    pc.walkStatements {
      case bt: BaseType if bt.isNamed && SpinalTraceAccess.namePriority(bt) == Nameable.REMOVABLE => bt.addTag(SpinalGeneratedNameTag)
      case _ =>
    }

    pc.walkStatements { s =>
      s match {
        case w: WhenStatement =>
          Netlist.vecWriteIndex(w.cond, generated) match {
            case Some((addr, _)) => name(addr, "index") // per-element enables stay anonymous
            case None            => name(w.cond, "when")
          }
        case sw: SwitchStatement =>
          name(sw.value, "switch")
          for (el <- sw.elements; k <- el.keys) k match {
            case bt: BaseType => name(bt, "case_key")
            case _            =>
          }
        case m: MemWrite =>
          name(m.address, "mem_addr"); name(m.writeEnable, "mem_wen")
        case m: MemReadSync =>
          name(m.address, "mem_addr"); name(m.readEnable, "mem_ren")
        case m: MemReadAsync =>
          name(m.address, "mem_addr")
        case m: MemReadWrite =>
          name(m.address, "mem_addr"); name(m.writeEnable, "mem_wen"); name(m.chipSelect, "mem_cs")
        case _ =>
      }
      s.walkExpression {
        case m: BinaryMultiplexer             => name(m.cond, "mux_sel")
        case m: Multiplexer                   => name(m.select, "index")
        case a: BitVectorBitAccessFloating    => name(a.bitId, "index")
        case a: BitVectorRangedAccessFloating => name(a.offset, "index")
        case t: BitAssignmentFloating         => name(t.bitId, "index")
        case t: RangedAssignmentFloating      => name(t.offset, "index")
        case _                                =>
      }
    }
  }
}
