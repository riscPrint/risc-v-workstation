package rvwsmp

/** Pure model controls. This does not execute CPU or peripheral RTL. */
object DeviceChecks {
  def main(args: Array[String]): Unit = {
    val d = new Devices(3)
    d.write(0x2000004L,1,4)
    require(!d.msip(0) && d.msip(1) && !d.msip(2))
    d.write(0x2000004L,0,4); require(!d.msip(1))
    d.write(0x2004010L,BigInt("0123456789abcdef",16),8)
    require(d.read(0x2004010L,8)==BigInt("0123456789abcdef",16))
    d.write(0x2004014L,0,4); require(d.compare(2)==BigInt("89abcdef",16))
    d.write(0xc000004L,3,4); d.write(0xc002080L,2,4); d.source(1,true)
    require(!d.external(0) && d.external(1) && !d.external(2))
    require(d.read(0xc201004L,4)==1); require(!d.external(1))
    d.write(0xc201004L,1,4); require(d.external(1))
    d.source(1,false); require(!d.external(1))
    d.source(1,true); d.write(0xc201000L,3,4); require(!d.external(1))
    println("SMP device model: 9 checks passed; no peripheral RTL executed")
  }
}
