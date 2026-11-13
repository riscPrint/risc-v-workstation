package spinalchecks

import java.nio.charset.StandardCharsets
import java.nio.file.{Files, Path}
import spinal.core.BaseType

/** A small property builder that emits the same SVA consumed by rvw formal.
  * Keep properties beside the design. Render them after Spinal assigns RTL names.
  * This builder emits text; it does not insert assertions or run verification.
  */
object Sva {
  private def ident(value: String): String = {
    require(value != null && value.matches("[A-Za-z_][A-Za-z0-9_]*"),
      "SVA needs an assigned local RTL identifier")
    value
  }
  private def delay(value: Int): Unit = require(value >= 0 && value <= 64, "delay must be in 0..64")

  final class Expr private[Sva] (private val value: () => String) {
    def render: String = value()
    def unary_! : Expr = new Expr(() => s"!(${render})")
    def &&(other: Expr): Expr = new Expr(() => s"(${render}) && (${other.render})")
    def ||(other: Expr): Expr = new Expr(() => s"(${render}) || (${other.render})")
    def equal(other: Expr): Expr = new Expr(() => s"(${render}) == (${other.render})")
    def equal(number: BigInt): Expr = {
      require(number >= 0, "literal must be nonnegative")
      new Expr(() => s"(${render}) == $number")
    }
    def past: Expr = new Expr(() => s"$$past(${render})")
    def rose: Expr = new Expr(() => s"$$rose(${render})")
    def fell: Expr = new Expr(() => s"$$fell(${render})")
    def stable: Expr = new Expr(() => s"$$stable(${render})")
    def changed: Expr = new Expr(() => s"$$changed(${render})")
    def sequence: Sequence = new Sequence(() => render)
    def throughout(other: Sequence): Sequence = new Sequence(() => s"(${render}) throughout (${other.render})")
  }

  final class Sequence private[Sva] (private val value: () => String) {
    def render: String = value()
    def thenAfter(cycles: Int, other: Sequence): Sequence = {
      delay(cycles)
      new Sequence(() => s"(${render}) ##$cycles (${other.render})")
    }
    def repeat(count: Int): Sequence = repeat(count, count)
    def repeat(minimum: Int, maximum: Int): Sequence = {
      require(minimum >= 1 && minimum <= maximum && maximum <= 64, "repetition must be in 1..64")
      new Sequence(() => s"(${render})[*$minimum:$maximum]")
    }
    def or(other: Sequence): Sequence = new Sequence(() => s"(${render}) or (${other.render})")
    def intersect(other: Sequence): Sequence = new Sequence(() => s"(${render}) intersect (${other.render})")
    def within(other: Sequence): Sequence = new Sequence(() => s"(${render}) within (${other.render})")
    def firstMatch: Sequence = new Sequence(() => s"first_match(${render})")
    def implies(other: Sequence, overlap: Boolean = true): Property =
      new Property(() => s"(${render}) ${if (overlap) "|->" else "|=>"} (${other.render})")
    def property: Property = new Property(() => render)
  }

  final class Property private[Sva] (private val value: () => String) {
    def render: String = value()
    private def statement(kind: String, name: String, clock: Expr, reset: Option[Expr]): String = {
      val event = ident(clock.render)
      val disable = reset.map(r => s"disable iff (${r.render}) ").getOrElse("")
      s"${ident(name)}: $kind property (@(posedge $event) $disable${render});"
    }
    def assertOn(name: String, clock: Expr, reset: Option[Expr] = None): String =
      statement("assert", name, clock, reset)
    def assumeOn(name: String, clock: Expr, reset: Option[Expr] = None): String =
      statement("assume", name, clock, reset)
    def coverOn(name: String, clock: Expr, reset: Option[Expr] = None): String =
      statement("cover", name, clock, reset)
  }

  def signal(name: String): Expr = { ident(name); new Expr(() => name) }
  def signal(value: BaseType): Expr = new Expr(() => ident(value.getName()))
  def literal(value: Boolean): Expr = new Expr(() => if (value) "1'b1" else "1'b0")
  def write(path: Path, statements: Seq[String]): Unit = {
    require(statements.nonEmpty, "declare at least one property")
    Files.write(path, (statements.mkString("\n") + "\n").getBytes(StandardCharsets.UTF_8))
  }
}
