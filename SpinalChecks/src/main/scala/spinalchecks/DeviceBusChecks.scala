package spinalchecks

import spinal.core._

/** Project register addresses and independent accepted bus observations. One request at a time.
  * The binding uses byte addresses and expanded bit strobes. Responses are in order.
  */
case class DeviceRegister(address: BigInt, model: RegisterModel) {
  require(address >= 0)
}
object DeviceRegister {
  def load(file: java.io.File): Seq[DeviceRegister] =
    RegisterMap.load(file).map(r => DeviceRegister(r.address, r.model))
}
object DeviceBusChecks {
  def bind(name: String, registers: Seq[DeviceRegister], accepted: Bool, address: UInt,
           write: Bool, data: Bits, strobes: Bits, response: Bool, responseData: Bits,
           responseError: Bool, maxLatency: Int): Unit = {
    require(registers.nonEmpty && registers.map(_.address).distinct.size == registers.size)
    require(maxLatency >= 1)
    val w = data.getWidth
    require(strobes.getWidth == w && responseData.getWidth == w)
    require(registers.forall(r => r.model.width == w && r.address.bitLength <= address.getWidth))
    val expected = registers.map(r => Reg(Bits(w bits)).init(r.model.reset))
    val hit = registers.map(r => address === U(r.address, address.getWidth bits))
    val mapped = hit.reduce(_ || _)
    val readValue = Bits(w bits)
    readValue := 0
    for (((r, state), selected) <- registers.zip(expected).zip(hit)) {
      when(selected) { readValue := state }
      val m = r.model
      when(accepted && selected) {
        val mask = B(m.writeMask, w bits) & strobes
        when(write) {
          state := ((state & ~mask) | (data & mask)) & ~(data & strobes & B(m.w1cMask, w bits))
        }.otherwise { state := state & ~B(m.readClearMask, w bits) }
      }
    }
    val busy = Reg(Bool()).init(False)
    val age = Reg(UInt(log2Up(BigInt(maxLatency) + 1) bits)).init(0)
    val savedData = Reg(Bits(w bits)).init(0)
    val savedError = Reg(Bool()).init(False)
    val savedWrite = Reg(Bool()).init(False)
    when(busy && age =/= maxLatency) { age := age + 1 }
    when(accepted && !busy) {
      busy := True; age := 0
      savedData := readValue; savedError := !mapped; savedWrite := write
    }
    when(response) { busy := False }
    val valid = busy || accepted
    val wantedError = Mux(busy, savedError, !mapped)
    val wantedWrite = Mux(busy, savedWrite, write)
    val wantedData = Mux(busy, savedData, readValue)
    DeclaredChecks.rule("register.bus_order", name, "single outstanding independent request; no unsolicited response")(
      (accepted && busy) || (response && !valid))
    DeclaredChecks.rule("register.bus_decode", name, "response error equals project address decode")(
      response && valid && (responseError =/= wantedError))
    DeclaredChecks.rule("register.bus_data", name, "pre-side-effect read data from independent bus history")(
      response && valid && !wantedError && !wantedWrite && (responseData =/= wantedData))
    DeclaredChecks.rule("register.bus_latency", name, "response must arrive within declared cycle bound")(
      busy && age === maxLatency - 1 && !response)
  }

  /** Deterministic stimulus for an adapter. Includes reads before/after each masked write.
    * The adapter drives accepted requests and supplies its own independent response capture.
    */
  def accesses(registers: Seq[DeviceRegister]): Seq[(BigInt, Boolean, BigInt, BigInt)] =
    registers.flatMap { r =>
      val all = (BigInt(1) << r.model.width) - 1
      Seq((r.address, false, BigInt(0), all), (r.address, true, all, all),
          (r.address, false, BigInt(0), all), (r.address, true, BigInt(0), all),
          (r.address, false, BigInt(0), all))
    }
}
