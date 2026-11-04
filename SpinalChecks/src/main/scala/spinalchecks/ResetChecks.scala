package spinalchecks

import spinal.core._

/** Bind in an independent observation clock. Active levels must be normalized by the project.
  * These checks observe sampled behavior. They do not prove recovery/removal or metastability.
  */
object ResetChecks {
  def bind(name: String, requested: Bool, asserted: Bool, destinationEdge: Bool,
           controlsKnown: Bool, releaseEdges: Int): Unit = {
    require(releaseEdges >= 1)
    val edges = Reg(UInt(log2Up(BigInt(releaseEdges) + 1) bits)).init(0)
    when(requested) { edges := 0 }
      .elsewhen(destinationEdge && edges =/= releaseEdges) { edges := edges + 1 }
    val wasAsserted = RegNext(asserted).init(True)
    DeclaredChecks.rule("rdc.unknown_control", name, "independent reset controls must be known")(!controlsKnown)
    DeclaredChecks.rule("rdc.assertion", name, "sampled asynchronous assertion follows request")(
      controlsKnown && requested && !asserted)
    DeclaredChecks.rule("rdc.release", name, "release needs a destination edge and declared settling edges")(
      controlsKnown && wasAsserted && !asserted &&
        (!destinationEdge || requested || edges < releaseEdges))
  }

  def order(name: String, earlierReset: Bool, laterReset: Bool): Unit = {
    DeclaredChecks.rule("rdc.release_order", name, "declared source reset must release before destination")(
      earlierReset && !laterReset)
  }

  def crossing(name: String, sourceReset: Bool, destinationReset: Bool,
               isolated: Bool, consuming: Bool): Unit = {
    DeclaredChecks.rule("rdc.isolation", name, "independent reset source must be isolated from active consumer")(
      sourceReset && !destinationReset && consuming && !isolated)
  }

  def reconvergence(name: String, resetA: Bool, resetB: Bool, isolated: Bool, consuming: Bool): Unit = {
    DeclaredChecks.rule("rdc.reconvergence_protocol", name, "unequal reset states need isolation before merge")(
      (resetA =/= resetB) && consuming && !isolated)
  }
}
