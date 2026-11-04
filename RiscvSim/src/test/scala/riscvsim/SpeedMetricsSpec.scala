package riscvsim

import org.scalatest.funsuite.AnyFunSuite

class SpeedMetricsSpec extends AnyFunSuite {
  test("rates use execution seconds without model setup") {
    assert(SpeedMetrics(1000000, 500000, Some(2)).toMap ==
      Map("sim_khz" -> 500.0, "sim_instructions_per_s" -> 250000.0))
    assert(SpeedMetrics(1, 0, Some(0.001)).toMap.apply("sim_instructions_per_s") == 0)
  }
  test("missing and invalid measurements have no rate") {
    Seq(None, Some(0.0), Some(-1.0), Some(Double.NaN), Some(Double.PositiveInfinity),
      Some(Double.MinPositiveValue)).foreach { s => assert(SpeedMetrics(10, 2, s).isEmpty) }
    assert(SpeedMetrics(0, 1, Some(1)).isEmpty)
    assert(SpeedMetrics(1, -1, Some(1)).isEmpty)
  }
}
