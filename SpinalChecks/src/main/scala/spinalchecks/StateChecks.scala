package spinalchecks

import spinal.core._

/** The adapter supplies initialization evidence. No arbitrary startup delay is inserted. */
object StateChecks {
  def machine(name: String, state: UInt, initialized: Bool, states: Seq[BigInt],
              transitions: Seq[(BigInt, BigInt)]): Unit = {
    require(states.nonEmpty && states.distinct.size == states.size)
    require(states.forall(s => s >= 0 && s.bitLength <= state.getWidth))
    require(transitions.nonEmpty && transitions.forall { case (a,b) => states.contains(a) && states.contains(b) })
    val prev = RegNext(state)
    val hadState = RegNext(initialized).init(False)
    val legal = states.map(s => state === U(s, state.getWidth bits)).reduce(_ || _)
    val allowed = transitions.map { case (a,b) =>
      prev === U(a, state.getWidth bits) && state === U(b, state.getWidth bits)
    }.reduce(_ || _)
    DeclaredChecks.rule("state.encoding", name, "declared state codes; active on first initialized sample")(
      initialized && !legal)
    DeclaredChecks.rule("state.transition", name, "declared edges including self loops; consecutive initialized samples")(
      initialized && hadState && !allowed)
  }

  def branches(name: String, active: Bool, selected: Bits, required: Boolean): Unit = {
    require(selected.getWidth > 0)
    val s = selected.asUInt
    DeclaredChecks.rule("state.exclusive", name, "at most one declared branch while active")(
      active && (s & (s - 1)) =/= 0)
    if (required) DeclaredChecks.rule("state.required", name, "one declared branch is required while active")(
      active && selected === 0)
  }
}
