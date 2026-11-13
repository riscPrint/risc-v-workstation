package spinalchecks.demo

import spinal.core._
import spinal.lib._
import spinal.lib.bus.amba3.apb._
import spinalchecks._

/** A concrete library IP binding. Only the reset-defined direction word is selected.
  * The output-data register has unknown reset storage and is not modeled here.
  */
class CheckedGpio extends Component {
  val io = new Bundle {
    val apb = slave(Apb3(Apb3Gpio.getApb3Config()))
    val pins = in Bits(8 bits)
    val enables = out Bits(8 bits)
    // Seeded observation fault for the example test, not a modification of the IP.
    val corruptObservation = in Bool()
  }
  val peripheral = Apb3Gpio(8, withReadSync = false)
  peripheral.io.apb <> io.apb
  peripheral.io.gpio.read := io.pins
  io.enables := peripheral.io.gpio.writeEnable
  val selected = io.apb.PSEL.orR && io.apb.PENABLE && io.apb.PREADY && io.apb.PADDR === 8
  val response = io.apb.PRDATA ^ Mux(io.corruptObservation, B(1, 32 bits), B(0, 32 bits))
  DeviceBusChecks.bind("gpio.direction", Seq(DeviceRegister(8, RegisterModel(1, 32, 0, 255, 0, 0))),
    selected, io.apb.PADDR, io.apb.PWRITE, io.apb.PWDATA, B(BigInt("ffffffff", 16), 32 bits),
    selected, response, io.apb.PSLVERROR, maxLatency = 1)
}
