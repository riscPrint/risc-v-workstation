package riscvsim

import spinal.core._
import spinal.core.sim._

/** Encoded wire values for simulation observations, including sparse enums. */
object SimEncoding {
  /** Preserve all wire bits, including bit 63, on both supported Spinal axes. */
  def longBits(signal: BitVector): Long = signal.toBigInt.toLong

  def value[T <: SpinalEnum](signal: SpinalEnumCraft[T]): BigInt =
    signal.getEncoding.getValue(signal.toEnum)
}
