package riscvsim

import spinal.core._
import spinal.core.sim._
import spinal.core.internals.{ExpressionContainer, PhaseContext, PhaseNetlist, PhaseGetInfoRTL}
import scala.collection.mutable.ArrayBuffer

/** Live state transfer through Spinal's public register and memory bridge.
  * Use at a settled low clock. The caller owns inputs, clock, RAM and devices.
  * This does not serialize the JVM scheduler or Verilator implementation data. */
class BridgeState {
  private val registers = ArrayBuffer.empty[BaseType]
  private val memories = ArrayBuffer.empty[Mem[Data]]
  def instrument(config: SpinalConfig): SpinalConfig = {
    config.addTransformationPhase(new PhaseNetlist {
      override def impl(pc: PhaseContext): Unit = {
        require(registers.isEmpty && memories.isEmpty, "use one BridgeState per elaboration")
        pc.walkComponents {
          case b: BlackBox if b.isBlackBox => throw new IllegalArgumentException("bridge state does not support blackboxes")
            case _ =>
        }
        // Backend-generated synchronous read buffers are state too. Lower
        // supported ports to explicit registers before collecting the inventory.
        val reads = ArrayBuffer.empty[MemReadSync]
        pc.walkDeclarations {
          case m: Mem[_] => m.foreachStatements {
            case r: MemReadSync => reads += r
            case _: MemReadWrite => throw new IllegalArgumentException("bridge state does not support combined synchronous memory ports")
            case _ =>
          }
          case _ =>
        }
        reads.zipWithIndex.foreach { case (read, index) =>
          require(read.getWidth == read.mem.width &&
            (read.readUnderWrite == dontCare || read.readUnderWrite == readFirst),
            "bridge state needs full-width read-first synchronous memory ports")
          val consumers = ArrayBuffer.empty[ExpressionContainer]
          pc.walkBaseNodes {
            case ec: ExpressionContainer => ec.foreachExpression(e => if (e eq read) consumers += ec)
            case _ =>
          }
          read.mem.component.rework {
            read.clockDomain {
              val value = Reg(Bits(read.getWidth bits)).setName(s"snapshot_read_$index")
              when(read.readEnable.asInstanceOf[Bool]) {
                // Use the lowered width. The original HardType can depend on a
                // plugin database scope which has ended before this phase runs.
                val data = Bits(read.getWidth bits)
                read.mem.readAsyncImpl(read.address.asInstanceOf[UInt], data, dontCare, false)
                value := data
              }
              consumers.foreach(_.remapExpressions(e => if (e eq read) value else e))
            }
          }
          read.removeStatement()
        }
        pc.walkDeclarations {
          case b: BaseType if b.isReg => b.simPublic(); registers += b
          case m: Mem[_] => m.simPublic(); memories += m.asInstanceOf[Mem[Data]]
          case _ =>
        }
      }
    })
    // Normalization can replace or remove declarations. Bind the inventory to
    // the final netlist, including state introduced by backend lowering.
    config.phasesInserters += { phases =>
      val index = phases.indexWhere(_.isInstanceOf[PhaseGetInfoRTL])
      require(index >= 0, "bridge state needs the final RTL information phase")
      phases.insert(index, new PhaseNetlist {
        override def impl(pc: PhaseContext): Unit = {
          registers.clear(); memories.clear()
          pc.walkDeclarations {
            case b: BaseType if b.isReg => b.simPublic(); registers += b
            case m: Mem[_] => m.simPublic(); memories += m.asInstanceOf[Mem[Data]]
            case _ =>
          }
        }
      })
    }
    config
  }
  private def layout: ujson.Value = ujson.Obj(
    "registers" -> ujson.Arr.from(registers.map(b => ujson.Arr(b.getRtlPath(), b.getBitsWidth))),
    "memories" -> ujson.Arr.from(memories.map(m => ujson.Arr(m.component.getRtlPath() + "/" + m.getName(), m.width, m.wordCount))))
  def capture(): ujson.Value = ujson.Obj("schema" -> "rvw.spinal-state/1", "layout" -> layout,
    "registers" -> ujson.Arr.from(registers.map(b => ujson.Str((b.toBigInt & ((BigInt(1) << b.getBitsWidth) - 1)).toString))),
    "memories" -> ujson.Arr.from(memories.map(m => ujson.Arr.from(
      (0 until m.wordCount).map(i => ujson.Str(m.getBigInt(i).toString))))))
  def restore(state: ujson.Value): Unit = {
    require(state("schema").str == "rvw.spinal-state/1" && state("layout") == layout,
      "Spinal state layout mismatch")
    val regs = state("registers").arr.map(v => BigInt(v.str))
    val mems = state("memories").arr.map(_.arr.map(v => BigInt(v.str)))
    require(regs.size == registers.size && mems.size == memories.size, "Spinal state count mismatch")
    def fits(v: BigInt, width: Int): Boolean = v >= 0 && v.bitLength <= width
    require(registers.zip(regs).forall { case (b, v) => fits(v, b.getBitsWidth) })
    require(memories.zip(mems).forall { case (m, vs) =>
      vs.size == m.wordCount && vs.forall(fits(_, m.width)) })
    registers.zip(regs).foreach { case (b, v) => spinal.core.sim.setBigInt(b, if (b.isInstanceOf[SInt] && v.testBit(b.getBitsWidth - 1)) v - (BigInt(1) << b.getBitsWidth) else v) }
    memories.zip(mems).foreach { case (m, vs) => vs.zipWithIndex.foreach { case (v, i) => m.setBigInt(i, v) } }
  }
}
