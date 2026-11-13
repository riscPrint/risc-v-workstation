package spinalchecks

import spinal.core._
import spinal.core.internals._
import scala.collection.mutable.ArrayBuffer

/** Recognise library cancellation from assignments, never from signal names.
  * Unknown logic retains the strict contract. Enable creation stacks.
  */
private[spinalchecks] object StreamCancellation {
  final case class Term(condition: Expression, inverted: Boolean, registered: Boolean, origin: String)

  private def library(st: Statement, methods: Set[String]): Boolean =
    Option(st.scalaTrace).exists(_.getStackTrace.exists(f =>
      (f.getClassName.startsWith("spinal.lib.Stream") ||
        (methods.contains("m2sPipeWithFlush") && f.getMethodName == "m2sPipeWithFlush")) && methods.exists(m =>
        f.getMethodName == m || f.getMethodName.startsWith("$anonfun$" + m + "$"))))

  def discover(valid: Bool): Seq[Term] = {
    def walk(v: Bool, seen: Set[Bool]): Seq[Term] = {
      if (seen(v)) return Nil
      val assignments = ArrayBuffer[DataAssignmentStatement]()
      v.foreachStatements {
        case a: DataAssignmentStatement => assignments += a
        case _ =>
      }
      if (!v.isReg && assignments.size == 1 && assignments.head.parentScope == v.component.dslBody) {
        val a = assignments.head
        a.source match {
          case b: Bool if b.component == v.component => return walk(b, seen + v)
          case and: Operator.Bool.And if library(a, Set("continueWhen", "clearValidWhen")) =>
            val inherited = and.left match {
              case b: Bool if b.component == v.component => walk(b, seen + v)
              case _ => Nil
            }
            val origin = if (library(a, Set("haltWhen"))) "Stream.haltWhen"
              else if (library(a, Set("clearValidWhen"))) "Stream.clearValidWhen" else "Stream.continueWhen"
            return inherited :+ Term(and.right, true, false, origin)
          case and: Operator.Bool.And =>
            return Seq(and.left, and.right).flatMap {
              case b: Bool if b.component == v.component => walk(b, seen + v)
              case _ => Nil
            }
          case _ =>
        }
      }
      val clears = assignments.toSeq.flatMap { a =>
        val clear = a.source match {
          case b: BoolLiteral => !b.value
          case b: Bool => try { Literal(b) == 0 } catch { case scala.util.control.NonFatal(_) => false }
          case _ => false
        }
        val trusted = library(a, if (v.isReg) Set("m2sPipe", "m2sPipeWithFlush") else Set("throwWhen"))
        if (!clear || !trusted) Nil
        else a.parentScope.parentStatement match {
          case w: WhenStatement if (a.parentScope eq w.whenTrue) && (w.parentScope eq v.component.dslBody) =>
            Seq(Term(w.cond, false, v.isReg, if (!v.isReg) "Stream.throwWhen"
              else if (library(a, Set("m2sPipeWithFlush"))) "m2sPipeWithFlush register clear"
              else "Stream.m2sPipe register clear"))
          case _ => Nil
        }
      }
      val defaults = assignments.filter(_.parentScope eq v.component.dslBody)
      val inherited = if (!v.isReg && defaults.size == 1 && clears.size == assignments.size - 1)
        defaults.head.source match {
          case b: Bool if b.component == v.component => walk(b, seen + v)
          case _ => Nil
        }
      else Nil
      clears ++ inherited
    }
    walk(valid, Set.empty)
  }
}
