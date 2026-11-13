package examplesocvexii

import spinal.core._
import spinal.core.sim._
import java.nio.file.{Files, Paths}
import scala.jdk.CollectionConverters._

/** Manifest rows: image path, seed, cycle limit, optional RAM tohost address. */
object Run extends App {
  val compiled = SimConfig.withVerilator.addSimulatorFlag("--assert").compile {
    val top = new generated.ComposedSoc
    top.ram.mem.simPublic()
    top.core.io.retired.simPublic()
    top.finisher.io.done.simPublic(); top.finisher.io.code.simPublic()
    top
  }
  for(row <- Files.readAllLines(Paths.get(args(0))).asScala.filter(_.nonEmpty)) {
    val job = row.split("\t")
    compiled.doSim(job(1).toInt) { dut =>
      SimTimeout(job(2).toLong * 10 + 10000)
      val image = Files.readAllLines(Paths.get(job(0))).asScala
      image.zipWithIndex.foreach { case (word, index) => dut.ram.mem.setBigInt(index, BigInt(word, 16)) }
      val tohost = java.lang.Long.parseUnsignedLong(job(3), 16)
      dut.uart_serial.rxd #= true; dut.plic_sources #= 0
      val received = new StringBuilder
      fork {
        sleep(1); waitUntil(dut.uart_serial.txd.toBoolean)
        while(true) {
          waitUntil(!dut.uart_serial.txd.toBoolean)
          sleep(80); assert(!dut.uart_serial.txd.toBoolean); sleep(160)
          var value = 0
          for(i <- 0 until 8) { if(dut.uart_serial.txd.toBoolean) value |= 1 << i; sleep(160) }
          assert(dut.uart_serial.txd.toBoolean)
          received.append(value.toChar)
        }
      }
      dut.clockDomain.forkStimulus(10)
      dut.clockDomain.waitSampling(10)
      var cycles = 0
      def code: BigInt = if(tohost == 0) {
        if(dut.finisher.io.done.toBoolean) dut.finisher.io.code.toBigInt else BigInt(0)
      } else dut.ram.mem.getBigInt(((tohost - 0x80000000L) / 4).toInt)
      while(cycles < job(2).toInt && code == 0) {
        dut.clockDomain.waitSampling(); cycles += 1
        if(cycles == 200 && job.length > 4 && job(4) == "external") dut.plic_sources #= 1
      }
      val value = code
      val status = if(value == 1) "pass" else if(value == 0) "timeout" else "fail"
      val uartHex = received.toString.getBytes("UTF-8").map(b => f"${b & 255}%02x").mkString
      println(s"SOC_RESULT {\"status\":\"$status\",\"cycles\":$cycles,\"instret\":${dut.core.io.retired.toBigInt},\"fail_code\":$value,\"uart_hex\":\"$uartHex\"}")
    }
  }
}
