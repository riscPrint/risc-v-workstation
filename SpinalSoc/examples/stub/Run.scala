package example
import spinal.core._
import spinal.core.sim._

object Run extends App {
  val seed = args(0).toInt
  val limit = args(1).toInt
  val compiled = SimConfig.withVerilator.compile {
    val top = new generated.ComposedSoc
    top.core.io.fault.simPublic()
    top.core.io.retired.simPublic()
    top.finisher.io.done.simPublic()
    top.finisher.io.code.simPublic()
    top
  }
  compiled.doSim(seed) { dut =>
    dut.uart_serial.rxd #= true
    dut.plic_sources #= 0
    val received = new StringBuilder
    fork {
      sleep(1)
      waitUntil(dut.uart_serial.txd.toBoolean)
      while(true) {
        waitUntil(!dut.uart_serial.txd.toBoolean)
        sleep(80)
        assert(!dut.uart_serial.txd.toBoolean)
        sleep(160)
        var value = 0
        for(i <- 0 until 8) {
          if(dut.uart_serial.txd.toBoolean) value |= 1 << i
          sleep(160)
        }
        assert(dut.uart_serial.txd.toBoolean)
        received.append(value.toChar)
      }
    }
    dut.clockDomain.forkStimulus(10)
    dut.clockDomain.waitSampling(10)
    var cycles = 0
    while(cycles < limit && !dut.finisher.io.done.toBoolean && !dut.core.io.fault.toBoolean) {
      dut.clockDomain.waitSampling()
      cycles += 1
      if(cycles==200) dut.plic_sources #= 1
    }
    val code = dut.finisher.io.code.toBigInt
    val status = if(dut.core.io.fault.toBoolean) "error" else if(!dut.finisher.io.done.toBoolean) "timeout" else if(code==1) "pass" else "fail"
    val text = received.toString.replace("\n","\\n")
    println(s"SOC_RESULT {\"status\":\"$status\",\"cycles\":$cycles,\"instret\":${dut.core.io.retired.toBigInt},\"fail_code\":$code,\"uart\":\"$text\"}")
  }
}
