package ooomini

import spinal.core._

/** Four-entry PMP, four-byte grain, RV32 physical addresses up to 34 bits. */
object Pmp {
  def allowed(config: Vec[Bits], bounds: Vec[UInt], address: UInt, bytes: UInt,
              machine: Bool, permission: Int): Bool = {
    val first = address.resize(34)
    val last = first + bytes.resize(34) - 1
    val allow = Bool()
    allow := machine
    // Later assignments give the lowest numbered matching entry priority.
    for (i <- 3 to 0 by -1) {
      val low = if(i == 0) U(0,34 bits) else (bounds(i-1).resize(34) << 2).resize(34)
      val top = (bounds(i).resize(34) << 2).resize(34)
      val napotMask = UInt(34 bits)
      napotMask := 7
      for (bit <- 0 until 32) when(bounds(i)(bit downto 0).andR) {
        napotMask := U((BigInt(1) << scala.math.min(bit+4,34))-1,34 bits)
      }
      val base = top & ~napotMask
      val end = top | napotMask
      val hit, contained = Bool()
      hit := False; contained := False
      switch(config(i)(4 downto 3)) {
        is(1) { hit := low < top && first < top && last >= low; contained := first >= low && last < top }
        is(2) { hit := first < top+4 && last >= top; contained := first >= top && last < top+4 }
        is(3) { hit := first <= end && last >= base; contained := first >= base && last <= end }
      }
      when(hit) { allow := contained && ((machine && !config(i)(7)) || config(i)(permission)) }
    }
    allow
  }
}
