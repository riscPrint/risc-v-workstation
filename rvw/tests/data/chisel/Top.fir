FIRRTL version 3.3.0
circuit Top :
  module Acc : @[Gen.scala 8:7]
    input clock : Clock @[Gen.scala 8:7]
    input reset : Reset @[Gen.scala 8:7]
    output io : { flip in : { valid : UInt<1>, bits : UInt<8>}, out : UInt<8>} @[Gen.scala 9:14]

    regreset acc : UInt<8>, clock, reset, UInt<8>(0h0) @[Gen.scala 13:20]
    when io.in.valid : @[Gen.scala 14:21]
      node _acc_T = add(acc, io.in.bits) @[Gen.scala 15:16]
      node _acc_T_1 = tail(_acc_T, 1) @[Gen.scala 15:16]
      connect acc, _acc_T_1 @[Gen.scala 15:9]
    connect io.out, acc @[Gen.scala 17:10]

  module Acc_1 : @[Gen.scala 8:7]
    input clock : Clock @[Gen.scala 8:7]
    input reset : Reset @[Gen.scala 8:7]
    output io : { flip in : { valid : UInt<1>, bits : UInt<8>}, out : UInt<8>} @[Gen.scala 9:14]

    regreset acc : UInt<8>, clock, reset, UInt<8>(0h0) @[Gen.scala 13:20]
    when io.in.valid : @[Gen.scala 14:21]
      node _acc_T = add(acc, io.in.bits) @[Gen.scala 15:16]
      node _acc_T_1 = tail(_acc_T, 1) @[Gen.scala 15:16]
      connect acc, _acc_T_1 @[Gen.scala 15:9]
    connect io.out, acc @[Gen.scala 17:10]

  module Top : @[Gen.scala 20:7]
    input clock : Clock @[Gen.scala 20:7]
    input reset : UInt<1> @[Gen.scala 20:7]
    output io : { flip a : { valid : UInt<1>, bits : UInt<8>}, flip b : UInt<1>, flip sel : UInt<2>, y : UInt<8>[2], r : UInt<8>} @[Gen.scala 21:14]

    inst units_0 of Acc @[Gen.scala 28:33]
    connect units_0.clock, clock
    connect units_0.reset, reset
    inst units_1 of Acc_1 @[Gen.scala 28:33]
    connect units_1.clock, clock
    connect units_1.reset, reset
    connect units_0.io.in.bits, io.a.bits @[Gen.scala 30:13]
    connect units_0.io.in.valid, io.a.valid @[Gen.scala 30:13]
    connect io.y[0], units_0.io.out @[Gen.scala 31:13]
    connect units_1.io.in.bits, io.a.bits @[Gen.scala 30:13]
    connect units_1.io.in.valid, io.a.valid @[Gen.scala 30:13]
    connect io.y[1], units_1.io.out @[Gen.scala 31:13]
    cmem mem : UInt<8> [4] @[Gen.scala 33:16]
    when io.a.valid : @[Gen.scala 34:20]
      write mport MPORT = mem[io.sel], clock @[Gen.scala 34:31]
      connect MPORT, io.a.bits @[Gen.scala 34:31]
    read mport io_r_MPORT = mem[io.sel], clock @[Gen.scala 35:19]
    connect io.r, io_r_MPORT @[Gen.scala 35:8]

