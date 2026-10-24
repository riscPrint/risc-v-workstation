package spinal.core

// Read-only access to `private[core]` SpinalHDL members SpinalBlocks needs.
// Lives in package spinal.core instead of forking SpinalHDL.
object SpinalBlocksAccess {
  def namePriority(n: Nameable): Byte = n.namePriority

  private lazy val nameableRefGetter = classOf[Nameable].getMethod("nameableRef")
  /** What a composite name (`stream_fire`) refers to, or null. */
  def nameableRef(n: Nameable): Nameable = nameableRefGetter.invoke(n).asInstanceOf[Nameable]
  def anonymSignalPrefix(bt: BaseType): String = {
    val p = bt.globalData.anonymSignalPrefix
    if (p == null) "zz" else p
  }
}
