package spinaltrace

import java.io.File

import spinal.core._
import spinal.core.internals._

import scala.collection.mutable

/** Tag put on signals that SpinalTrace named so they survive into the RTL/VCD. */
object SpinalTraceNamedTag extends SpinalTag {
  override def toString = "SpinalTraceNamed"
}

/** Tag put (by the naming phase) on signals that only carry a Spinal auto-generated REMOVABLE name such
  * as `when_<File>_l<n>`; the name priority itself is not stable until the end of elaboration. */
object SpinalGeneratedNameTag extends SpinalTag {
  override def toString = "SpinalGeneratedName"
}

/** Small netlist helpers shared by the naming phase and the PDG extractor. */
object Netlist {

  /** All assignment statements of a BaseType (full and partial, data and init). */
  def assignments(bt: BaseType): Seq[AssignmentStatement] = {
    val ret = mutable.ArrayBuffer[AssignmentStatement]()
    bt.foreachStatements(ret += _)
    ret.toSeq
  }

  def isLiteral(e: Expression): Boolean = e match {
    case _: Literal => true
    case c: Cast    => isLiteral(c.input)
    case r: Resize  => isLiteral(r.input)
    case _          => false
  }

  /** True when a signal is only a container for a constant (Spinal folds those later). */
  def isLiteralDriven(bt: BaseType): Boolean = {
    val as = assignments(bt)
    as.nonEmpty && as.forall(a => a.isInstanceOf[DataAssignmentStatement] && isLiteral(a.source))
  }

  /** Signals named by the compiler rather than the user: Spinal's anonymous `_zz_*`, the REMOVABLE
    * `when_<File>_l<n>` / `switch_<File>_l<n>` names and the names SpinalTrace adds. */
  def isGenerated(bt: BaseType): Boolean =
    bt.isUnnamed ||
      bt.getName().startsWith(SpinalTraceAccess.anonymSignalPrefix(bt)) ||
      SpinalTraceAccess.namePriority(bt) == Nameable.REMOVABLE ||
      bt.hasTag(SpinalTraceNamedTag) || bt.hasTag(SpinalGeneratedNameTag)

  /** The single full combinational driver of a compiler-generated signal, if any. */
  def soleDriver(bt: BaseType, generated: BaseType => Boolean): Option[Expression] = {
    if (bt.isReg || bt.isInput || bt.isOutput || !generated(bt)) return None
    assignments(bt) match {
      case Seq(a: DataAssignmentStatement) if a.target eq bt => Some(a.source)
      case _                                                => None
    }
  }

  /** Look through casts/resizes and compiler-generated single-driver signals. */
  def resolve(e: Expression, generated: BaseType => Boolean, depth: Int = 0): Expression = {
    if (depth > 32) return e
    e match {
      case c: Cast     => resolve(c.input, generated, depth + 1)
      case r: Resize   => resolve(r.input, generated, depth + 1)
      case bt: BaseType => soleDriver(bt, generated).map(resolve(_, generated, depth + 1)).getOrElse(bt)
      case other       => other
    }
  }

  private def isLiteralOne(e: Expression): Boolean = e match {
    case l: Literal => l.getValue() == 1
    case _          => false
  }

  /** Spinal lowers `vec(addr) := x` into `when((U(1) << addr)(i)) { vec_i := x }` per element.
    * Returns (addr, i) when `cond` has that shape. */
  def vecWriteIndex(cond: Expression, generated: BaseType => Boolean): Option[(Expression, Int)] =
    resolve(cond, generated) match {
      case a: BitVectorBitAccessFixed =>
        resolve(a.source, generated) match {
          case op: Operator.BitVector.ShiftLeftByUInt if isLiteralOne(resolve(op.left, generated)) =>
            // Keep the address as close to a named signal as possible (it is the probe).
            val addr = op.right match {
              case bt: BaseType => bt
              case other        => resolve(other, generated)
            }
            Some((addr, a.bitId))
          case _ => None
        }
      case _ => None
    }
}

/** Source locations from Spinal's ScalaLocated stack traces (two-pass `debugComponents`). */
class Locations(extraRoots: Seq[File], val includeLibraryFrames: Boolean = false) {
  private val cache = mutable.HashMap[(String, String, Int), PdgModel.Location]()

  private def keep(f: StackTraceElement): Boolean = {
    val cls  = f.getClassName
    val file = f.getFileName
    file != null && !file.endsWith(".java") && f.getLineNumber > 0 &&
    !cls.matches("spinaltrace\\.[^.]+") && !cls.startsWith("spinalwaves.") &&
    !cls.startsWith("java.") && !cls.startsWith("jdk.") && !cls.startsWith("sun.") &&
    (includeLibraryFrames || !cls.startsWith("spinal.lib."))
  }

  def frame(trace: Throwable): Option[StackTraceElement] =
    if (trace == null) None else ScalaLocated.filterStackTrace(trace.getStackTrace).find(keep)

  def of(s: ScalaLocated): PdgModel.Location = frame(s.getScalaTrace()) match {
    case Some(f) =>
      cache.getOrElseUpdate((f.getClassName, f.getFileName, f.getLineNumber), {
        val (file, line, col) = SourceInfo.locate(f, extraRoots)
        PdgModel.Location(file, line, col)
      })
    case None => PdgModel.Location.unknown
  }

  /** Fallback when there is no stack trace: Spinal's `genLineComments` string "@ File.scala lN". */
  def ofAssignment(a: AssignmentStatement): PdgModel.Location = {
    val l = of(a)
    if (l != PdgModel.Location.unknown || a.locationString == null) l
    else {
      val Pat = """@ (\S+) l(\d+)""".r
      a.locationString match {
        case Pat(f, n) => PdgModel.Location(f, n.toInt, 0)
        case _         => l
      }
    }
  }
}

object Locations {
  /** File symbol as used by Spinal in `when_<File>_l<line>`: like Spinal's `Location.fileSymbol`, only the
    * letters and digits of the file name, so `frontend-types.scala` gives a legal HDL name. */
  def fileSymbol(trace: Throwable): Option[(String, Int)] = {
    if (trace == null) return None
    ScalaLocated.filterStackTrace(trace.getStackTrace)
      .find(f => f.getFileName != null && !f.getFileName.endsWith(".java") && f.getLineNumber > 0)
      .map(f => (f.getFileName.stripSuffix(".scala").filter(_.isLetterOrDigit), f.getLineNumber))
  }
}
