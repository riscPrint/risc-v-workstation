package spinalchecks

import org.scalatest.funsuite.AnyFunSuite
import spinal.core._

class MapChecksSpec extends AnyFunSuite with ApplicationTest {
  class CsrRef(wlrl: Boolean = false, ro: Boolean = false) extends ApplicationRef {
    val state = Reg(Bits(4 bits)).init(8)
    val rejected = privilege =/= 3 || (write && Bool(ro)) ||
      (write && Bool(wlrl) && data(1 downto 0) === 3)
    val next = Bits(4 bits)
    next := state
    when(read && !rejected) { next(3) := False }
    when(write && !rejected) {
      if (!ro) {
        next(1 downto 0) := Mux(data(1 downto 0) === 3, B(2, 2 bits), data(1 downto 0))
        when(data(2)) { next(2) := False }
      }
    }
    state := (next & ~hwClear) | hwSet
    val allowed = (0 to 15).filter(x => (x & 3) != 3).map(BigInt(_))
    val mapping = (0 to 15).filter(x => (x & 3) == 3).map(x => BigInt(x) -> BigInt(x - 1)).toMap
    CsrChecks.bind("mapped", CsrModel(1, 4, 8, if (ro) 0 else 3, 3,
      if (ro) Nil else allowed, if (ro) 0 else 4, 8,
      if (ro || wlrl) Map.empty else mapping, wlrl, ro),
      state ^ Mux(corrupt, B(1, 4 bits), B(0, 4 bits)), read, write, data,
      privilege, rejected ^ corrupt, hwSet, hwClear, state ^ Mux(corrupt, B(1,4 bits), B(0,4 bits)))
  }
  test("WARL legalization and CSR side effects: legal passes, state/access faults fire") {
    exercise("csr_map_warl", Set("csr.state", "csr.access", "csr.read"))(new CsrRef)
  }
  test("WLRL denied writes: legal passes, state/access faults fire") {
    exercise("csr_map_wlrl", Set("csr.state", "csr.access", "csr.read"))(new CsrRef(wlrl = true))
  }
  test("read-only register: legal passes, state/access faults fire") {
    exercise("csr_map_ro", Set("csr.state", "csr.access", "csr.read"))(new CsrRef(ro = true))
  }
  class AccessRef(machineAlias: Boolean = false) extends ApplicationRef {
    val ok = privilege === 3 || (Bool(!machineAlias) && !write && permitted && (privilege === 1 || (privilege === 0 && !inhibit)))
    val allowed = HpmChecks.bindAccess("counter", read, write, privilege, permitted, !inhibit,
      true, Bool(machineAlias), !ok ^ corrupt)
    val count = Reg(UInt(4 bits)).init(0)
    when(permitted && !inhibit) { count := count + data.asUInt }
    when(write && ok) { count := 0 }
    HpmChecks.bind("events", HpmModel(1, 4, 0, "independent input event multiplicity"),
      count ^ Mux(corrupt, U(1, 4 bits), U(0, 4 bits)), data.asUInt, inhibit, permitted,
      write && allowed, U(0, 4 bits))
    HpmChecks.bindHalfRead("half", U(BigInt("123456789abcdef0",16),64 bits), inhibit,
      Mux(inhibit, B(BigInt("12345678",16),32 bits), B(BigInt("9abcdef0",16),32 bits)) ^
        Mux(corrupt, B(1,32 bits), B(0,32 bits)), read)
  }
  test("HPM increment conditions, access and RV32 halves: legal passes, each fault fires") {
    exercise("hpm_access", Set("hpm.count", "hpm.access", "hpm.read"))(new AccessRef)
  }
  test("machine counter alias denies low privilege: legal passes and faults fire") {
    exercise("hpm_machine_access", Set("hpm.count", "hpm.access", "hpm.read"))(new AccessRef(machineAlias = true))
  }
  class ResponseRef(latency: Int = 0) extends ApplicationRef {
    val state = Reg(Bits(4 bits)).init(15)
    for (i <- 0 until 4) {
      when(read) { state(i) := False }
      when(write && strobes(i)) { state(i) := data(i) }
      when(hwClear(i)) { state(i) := False }
      when(hwSet(i)) { state(i) := True }
    }
    var response = state
    var valid = read
    for (_ <- 0 until latency) { response = RegNext(response).init(0); valid = RegNext(valid).init(False) }
    RegisterChecks.bind("response", RegisterModel(1,4,15,15,0,15), state, read, write,
      data, strobes, hwSet, hwClear, response ^ Mux(corrupt,B(1,4 bits),B(0,4 bits)), valid, latency)
  }
  for (latency <- 0 to 1) test(s"device pre-clear data and response latency=$latency: legal passes, wrong response fires") {
    exercise(s"register_response_$latency", Set("register.response"))(new ResponseRef(latency))
  }
  class ImportedRef(file: String) extends ApplicationRef {
    val m = RegisterMap.load(new java.io.File(s"src/test/maps/$file")).head.model
    val state = Reg(Bits(32 bits)).init(12)
    when(read) { state(3) := False }
    when(write) {
      for (i <- 0 to 1) when(strobes(i)) { state(i) := data(i) }
      when(strobes(2) && data(2)) { state(2) := False }
    }
    for (i <- 0 until 4) {
      when(hwClear(i)) { state(i) := False }
      when(hwSet(i)) { state(i) := True }
    }
    RegisterChecks.bind("imported", m, state ^ Mux(corrupt,B(1,32 bits),B(0,32 bits)),
      read, write, data.resize(32), strobes.resize(32), hwSet.resize(32), hwClear.resize(32))
  }
  for (file <- Seq("status.properties", "status-rdl.properties")) test(s"imported $file generates device checks: legal passes and fault fires") {
    exercise(s"imported_map_$file", Set("register.state"))(new ImportedRef(file))
  }
  class ImportedCsrRef(file: String) extends ApplicationRef {
    val m = RegisterMap.load(new java.io.File(s"src/test/maps/$file")).head.csr(3)
    val state = Reg(Bits(32 bits)).init(12)
    when(read && privilege === 3) { state(3) := False }
    when(write && privilege === 3) {
      state(1 downto 0) := data(1 downto 0)
      when(data(2)) { state(2) := False }
    }
    for (i <- 0 until 4) {
      when(hwClear(i)) { state(i) := False }
      when(hwSet(i)) { state(i) := True }
    }
    val seen = state ^ Mux(corrupt, B(1,32 bits), B(0,32 bits))
    CsrChecks.bind("imported", m, seen, read, write, data.resize(32), privilege,
      (privilege =/= 3) ^ corrupt, hwSet.resize(32), hwClear.resize(32), seen)
  }
  for (file <- Seq("status.properties", "status-rdl.properties")) test(s"imported $file generates CSR checks: legal passes and faults fire") {
    exercise(s"imported_csr_$file", Set("csr.state", "csr.access", "csr.read"))(new ImportedCsrRef(file))
  }
  test("normalized map loads side effects") {
    val file = java.io.File.createTempFile("register-map", ".properties")
    try {
      java.nio.file.Files.writeString(file.toPath,
        "version=1\nregisters=status\nstatus.address=16\nstatus.width=4\nstatus.reset=8\nstatus.writeMask=3\nstatus.w1cMask=4\nstatus.readClearMask=8\n")
      val r = RegisterMap.load(file).head
      assert(r.address == 16 && r.model == RegisterModel(1,4,8,3,4,8))
      assert(r.csr(3).w1cMask == 4)
    } finally file.delete()
  }
  test("normalized map refuses missing fields, overlap and width overflow") {
    val file = java.io.File.createTempFile("bad-register-map", ".properties")
    val text = java.nio.file.Files.readString(new java.io.File("src/test/maps/status.properties").toPath)
    val overlapping = text.replace("registers=status", "registers=status,alias") +
      text.linesIterator.filter(_.startsWith("status.")).map(_.replace("status.", "alias.")).mkString("\n") + "\n"
    try {
      for (bad <- Seq(text.replace("status.width=32", "status.width=4294967328"),
        text.replace("status.reset=12\n", ""), overlapping)) {
        java.nio.file.Files.writeString(file.toPath, bad)
        intercept[IllegalArgumentException](RegisterMap.load(file))
      }
    } finally file.delete()
  }
  test("WARL cannot change a read-only field") {
    intercept[IllegalArgumentException](CsrModel(1,4,0,3,3, legalize = Map(BigInt(0) -> BigInt(8))))
  }

}
