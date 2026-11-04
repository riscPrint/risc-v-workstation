package spinalchecks

import spinal.core._

object ValueChecks {
  /** Supply a full precision signed result. Bounds are mathematical values, including unsigned intent. */
  def range(name: String, active: Bool, value: SInt, minimum: BigInt, maximum: BigInt): Unit = {
    require(minimum <= maximum)
    require(minimum >= -(BigInt(1) << (value.getWidth - 1)))
    require(maximum < (BigInt(1) << (value.getWidth - 1)))
    DeclaredChecks.rule("value.underflow", name, s"declared full precision range [$minimum,$maximum]")(
      active && value < S(minimum, value.getWidth bits))
    DeclaredChecks.rule("value.overflow", name, s"declared full precision range [$minimum,$maximum]")(
      active && value > S(maximum, value.getWidth bits))
  }

  /** Signed narrowing either preserves the mathematical value or explicitly uses modular low bits. */
  def narrowing(name: String, active: Bool, full: SInt, narrowed: SInt, modular: Boolean): Unit = {
    require(full.getWidth > narrowed.getWidth)
    val mismatch = if (modular) narrowed.asBits =/= full.asBits.resize(narrowed.getWidth)
      else narrowed.resize(full.getWidth) =/= full
    DeclaredChecks.rule("value.truncation", name,
      if (modular) "declared modular low bits" else "declared signed value preservation")(
      active && mismatch)
  }
}
