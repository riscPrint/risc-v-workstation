# Full register UART profile

`rvw soc peripheral uart16550-full --name uart --base 0x10000000 --out uart.json`
exports `rvwsoc.Uart16550Full`. Add its region and binder to the project map
and composition. The binder exports `serial` and `modem`. Modem pins use
active-low RS232 control names. Tie unused modem inputs high. Add
`rx_ready_n` and `tx_ready_n` to the binder exports when DMA requests are used.
The profile uses APB3 full-word accesses with register shift 2. Unaligned and
out-of-window accesses return an error. The serial engine and queues use the
peripheral clock. Reset is asynchronous and active high.

The offsets are RBR/THR/DLL at 0, IER/DLM at 4, IIR/FCR at 8, LCR at 12,
MCR at 16, LSR at 20, MSR at 24 and scratch at 28. DLAB selects DLL/DLM.
The divisor resets to 1. The bit period is `16 * divisor` input clocks.
Divisor zero stops serial progress. LCR resets to zero, which selects 5N1.
Program the divisor and LCR before transmission. Format is captured at frame
start. A divisor change during a frame has no qualification result.

FCR selects one-byte holding registers or 16-byte FIFOs. An enable change
clears both FIFOs. FCR bits 1 and 2 clear RX and TX queues independently.
A TX clear does not stop the current serial frame. The RX thresholds are
1, 4, 8 and 14 bytes. RX timeout is four configured character periods.
FCR bit 3 selects DMA request behavior. In mode 1, RX requests stay active
from threshold/timeout until empty. TX requests stay active from empty until
full. In mode 0, RX reports nonempty and TX reports an empty holding queue.
Writes to a full TX queue are ignored. Software must check THRE or DMA ready.

The engine supports 5 to 8 data bits, odd/even/mark/space parity and one or
two stop bits. The 5-bit two-stop setting uses 1.5 stop bits. LCR controls
transmit break. RX records parity, framing and break status with each byte.
Overflow retains older FIFO data and sets OE. An LSR read clears reported
error flags. FIFO error status retains errors on later queued bytes. THRE
tracks the holding queue. TEMT also requires the serial shifter to finish.

Interrupt priority is line status, RX data, RX timeout, THRE, then modem
status. An IIR read acknowledges only a reported THRE interrupt. Reading
RBR clears the receive timeout. MSR reads clear delta bits. RI records a
trailing-edge delta. MCR supplies RTS, DTR, OUT1 and OUT2. Loopback routes
serial and modem values internally and holds external outputs inactive.

Run the directed native bench from the repository root:

```sh
rvw regress cocotb SpinalSoc/examples/uart16550/bench.json \
  --out NEW_DIR --seed 31 --json
```

The bench uses the existing `rvw.vip.uart.CocotbAgent` and `Scoreboard`.
It drives serial receive pins and checks transmitted frames independently.
It checks FIFO order, overflow, interrupt priority, timeout, divisor aliases,
modem status/deltas, error clearing and loopback. Its framing matrix includes
5N1.5, 6O2, 7E1, 8O2, mark parity and space parity. It does not establish
complete 16550 compliance, hardware timing or baud mismatch tolerance.
The general register oracle cannot describe DLAB aliases or bit-selective
read-clear flags. Their reset values stay unknown in the software map.

## Wrapper reproduction and measured checks

Elaborate the wrapper with `rvwsoc.FullUartGenerate OUT` in the private
SpinalSoc build. Bind its RTL to the same bench:

```sh
python SpinalSoc/examples/uart16550/configure.py \
  --wrapper OUT/Uart16550Full.v --out NEW_BENCH.json
rvw regress cocotb NEW_BENCH.json --out NEW_RUN --seed 31 --json
```

| Native target | Directed checks | VIP TX frames | Result |
|---|---:|---:|---|
| UART RTL | 240 | 28 | pass |
| Spinal wrapper | 240 | 28 | pass |

Both runs used Verilator and seed 31 on 2026-11-13. Each had one test and
zero skips. The 5N1.5 timing check measured 361 clocks between queued frame
starts at 48 clocks per bit. This includes one idle clock between frames.
No CPU, complete compliance campaign or hardware run was performed here.
