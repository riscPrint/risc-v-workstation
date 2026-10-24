package spinalwaves

import spinal.core.sim.SimTimeout

/** Upper bound on simulated time for the SpinalWaves/SpinalTrace sim helpers.
  *
  * A testbench that waits for something that never happens keeps the clock running and the VCD
  * growing without limit (one such run wrote >200 GB). The helpers therefore arm Spinal's
  * `SimTimeout` by default; hitting it fails the simulation like any other sim failure.
  */
object SimGuard {
  /** Default limit in sim time units: 10,000,000 (1M cycles at `forkStimulus(10)`).
    * Override with env `SPINAL_SIM_TIMEOUT` (time units; `0` or `none` disables). */
  val DefaultLimit: Long = 10000000L

  def defaultTimeout: Option[Long] = sys.env.get("SPINAL_SIM_TIMEOUT").map(_.trim.toLowerCase) match {
    case Some("" | "0" | "none" | "off") => None
    case Some(v)                          => Some(v.toLong)
    case None                             => Some(DefaultLimit)
  }

  /** Call at the start of a simulation body. */
  def arm(limit: Option[Long]): Unit = limit.filter(_ > 0).foreach(SimTimeout(_))
}
