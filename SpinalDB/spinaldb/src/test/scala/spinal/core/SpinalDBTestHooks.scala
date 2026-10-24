package spinal.core

import spinal.core.internals.Operator

/** A node SpinalDB does not model (the allow-list test): a subclass of Spinal's `~` with its own
  * parameter. It emits the same Verilog as `~`, but nothing tells the key builder what `salt` means. */
class SaltedNot(val salt: Int) extends Operator.Bits.Not

/** A node with an operand its `foreachExpression` does not walk: the key cannot see `hidden`. */
class HiddenOperandNot extends Operator.Bits.Not { var hidden: internals.Expression = null }

/** Same fields and package as a trusted literal; the formatter changes the emitted RTL. */
object Round16LiteralState { var mode = 0 }
class Round16Literal extends internals.BitsLiteral {
  value = BigInt(1); poisonMask = BigInt(0); bitCount = 8; hasSpecifiedBitCount = true
  override def hexString(n: Int, align: Boolean = false): String =
    if (Round16LiteralState.mode == 0) "01" else "02"
  override def clone(): this.type = this
}

object SpinalDBTestHooks {
  def assignRound16(b: Bits): Unit = b.assignFrom(new Round16Literal)
  def hiddenNot(b: Bits, hidden: Bits): Bits = { val op = new HiddenOperandNot; op.hidden = hidden; b.wrapUnaryOperator(op) }

  def saltedNot(b: Bits, salt: Int): Bits = b.wrapUnaryOperator(new SaltedNot(salt))

  /** `b := ` a literal with don't-care bits (`mask`), as Spinal's own phases make them. */
  def assignPoisoned(b: Bits, value: Int, mask: Int): Unit =
    b.assignFrom(internals.BitsLiteral(BigInt(value), BigInt(mask), b.getWidth, true))

  def assignPoisonedBig(b: Bits, value: BigInt, mask: BigInt): Unit =
    b.assignFrom(internals.BitsLiteral(value, mask, b.getWidth, true))
}
