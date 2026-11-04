package riscvsim

import spinal.core._
import spinal.core.sim._

/** Encoded wire values for simulation observations, including sparse enums. */
object SimEncoding {
  def value[T <: SpinalEnum](signal: SpinalEnumCraft[T]): BigInt =
    signal.getEncoding.getValue(signal.toEnum)
}
