package spinalchecks

import spinal.core._
import spinal.lib._

/** Project bindings are elaborated in their sampling clock domain. */
case class DeclaredRule(kind: String, name: String, detail: String, cd: ClockDomain, fail: Bool, trigger: Bool) extends SpinalTag {
  override def allowMultipleInstance = true
}

object DeclaredChecks {
  def rule(kind: String, name: String, detail: String, trigger: Bool = null)(fail: Bool): Unit = {
    require(name.nonEmpty && detail.nonEmpty)
    Component.current.addTag(DeclaredRule(kind, name, detail, ClockDomain.current, fail, trigger))
  }

  /** Flow has no stall rule. Check a project-declared payload set only on valid beats. */
  def flowValues(name: String, flow: Flow[Bits], allowed: Seq[BigInt]): Unit = {
    require(allowed.nonEmpty && allowed.forall(x => x >= 0 && x.bitLength <= flow.payload.getWidth))
    rule("flow.payload_legal", name, "declared valid-beat payload set")(
      flow.valid && !allowed.map(x => flow.payload === B(x, flow.payload.getWidth bits)).reduce(_ || _))
  }
}
