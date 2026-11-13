package rvwvex

import spinalchecks.StreamCancelBinding

/** Project-owned source review. See checks-evidence/README.md and cancel-wave.json. */
object CheckSemantics {
  val cancellations = Seq(
    StreamCancelBinding("IBusSimplePlugin_fetchPc_output", "IBusSimplePlugin_fetcherHalt", false,
      "Fetcher.scala:167 gates the offer with !fetcherHalt; wave 2000-2010 ps"),
    StreamCancelBinding("IBusSimplePlugin_iBusRsp_stages_0_input", "IBusSimplePlugin_fetcherHalt", false,
      "Fetcher.scala:216 aliases fetchPc.output; wave 2000-2010 ps"),
    StreamCancelBinding("IBusSimplePlugin_rspJoin_rspBuffer_output", "IBusSimplePlugin_rspJoin_rspBuffer_flush", true,
      "IBusSimplePlugin.scala:366-369 consumes FIFO pop on flush despite output stall; wave 2010-2020 ps")
  )
}
