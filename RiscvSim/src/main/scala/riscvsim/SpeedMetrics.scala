package riscvsim

/** Throughput includes adapter execution and artifact handling, but excludes model setup. */
object SpeedMetrics {
  def apply(cycles: Long, instret: Long, executionS: Option[Double]): Seq[(String, Double)] =
    executionS.filter(s => s.isFinite && s > 0 && cycles > 0 && instret >= 0).toSeq.flatMap { s =>
      val values = Seq("sim_khz" -> (cycles / s / 1000.0), "sim_instructions_per_s" -> (instret / s))
      if (values.forall(_._2.isFinite)) values else Nil
    }
}
