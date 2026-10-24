package spinal.core

// Read-only access to a few `private[core]` SpinalHDL members SpinalTrace needs.
// Lives in package spinal.core instead of forking SpinalHDL.
object SpinalTraceAccess {
  def namePriority(n: Nameable): Byte = n.namePriority
  def anonymSignalPrefix(bt: BaseType): String = {
    val p = bt.globalData.anonymSignalPrefix
    if (p == null) "_zz" else p
  }
}
