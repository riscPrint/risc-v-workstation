package riscvsim

/** Calls that differ between the SpinalHDL versions RiscvSim is built against (see
  * `scripts/sbt/SpinalAxis.scala`). Older versions miss the member; each caller states its fallback. */
object SpinalCompat {
  def member(o: AnyRef, name: String): Option[AnyRef] =
    o.getClass.getMethods.find(m => m.getName == name && m.getParameterCount == 0).map(_.invoke(o))
  def intMember(o: AnyRef, name: String): Option[Int] = member(o, name).map(_.asInstanceOf[Number].intValue)
}
