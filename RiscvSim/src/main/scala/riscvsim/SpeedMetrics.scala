package riscvsim

/** Throughput includes adapter execution and artifact handling, but excludes model setup. */
object SpeedMetrics {
  def apply(cycles: Long, instret: Long, executionS: Option[Double]): Seq[(String, Double)] =
    executionS.filter(s => !s.isNaN && !s.isInfinite && s > 0 && cycles > 0 && instret >= 0).toSeq.flatMap { s =>
      val values = Seq("sim_khz" -> (cycles / s / 1000.0), "sim_instructions_per_s" -> (instret / s))
      if (values.forall(v => !v._2.isNaN && !v._2.isInfinite)) values else Nil
    }
}
