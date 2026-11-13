# Fetch stream triage

Core revision: `a62c145aa042a5de874344e0a7683bd7c8c8c870`.
Program: `rv32ui-p-beq`, SHA256
`d0bbee0c7e2b53c19c1629dc7097e8bd126ab7c692896799a8f1954ed2a13061`.
The run on 2026-11-13 completed 878 cycles and retired 338 instructions.
Software passed. C1 failed. All 57 generated checks were bound.
Eleven valid-hold checks fired 288 times. No payload-stability check fired.
No waiver or disable changed this result.

`cancel-wave.json` contains two pre-edge samples at the first firing of each
check. The full wave is local at `rvw/out/cancel-wave/native/program_0/wave.vcd`.
The JSON records its SHA256. Values are binary. Times use the VCD's 1 ps unit.
Run `rvw/triage-wave.py --help` to repeat the extraction. Set
`RVW_CHECKS_WAVE=1` when running `rvwvex.CsrChecksRuntime` to record a wave.
This capture used the standard Stream gate recognizer before custom pipe
recognition was added. It does not measure the final recognizer's coverage.

All IDs below have prefix `stream.valid_hold:IBusSimplePlugin_`.
Each row is a tool contract mismatch for the observed drop. It is not a core
bug finding. The source statements implement explicit halt or flush behavior.
This disposition does not establish that all behavior of each stream is legal.

| ID suffix | Firings | First window, ps | Cancel statement and propagation |
|---|---:|---|---|
| `iBusRsp_stages_1_input` | 69 | 270–280 | `Fetcher.scala:232` uses `m2sPipeWithFlush(iBusRsp.flush, false, ...)`. `Misc.scala:146` clears rValid before the next edge. Flush is 1 in the first sample. |
| `iBusRsp_stages_1_output` | 69 | 270–280 | `Fetcher.scala:219` connects `input.haltWhen(halt)`. Input has the preceding registered flush. A local halt condition alone does not describe this drop. |
| `iBusRsp_stages_1_input_haltWhen` | 69 | 270–280 | Same `Fetcher.scala:219` gate, with the same flushed input. |
| `iBusRsp_stages_0_output_toEvent_m2sPipe` | 69 | 270–280 | This is the actual register output from `Fetcher.scala:232` and `Misc.scala:146`. The stage-1 input is its valid alias. |
| `injector_decodeInput` | 4 | 1050–1060 | `Fetcher.scala:312–313` pipes with `getFlushAt(INJECTOR_M2S)`. `Misc.scala:146` clears rValid. `decode.arbitration.removeIt` is 1 before the clear and 0 after it. |
| `fetchPc_output` | 2 | 2000–2010 | `Fetcher.scala:167` assigns `!fetcherHalt && booted`. `fetcherHalt` changes from 0 to 1 while ready stays 0. |
| `iBusRsp_stages_0_input` | 2 | 2000–2010 | `Fetcher.scala:216` connects it to `fetchPc.output`. It has the same halt and valid drop. |
| `iBusRsp_output` | 1 | 2010–2020 | `IBusSimplePlugin.scala:391` connects `join.haltWhen(exceptionDetected)`. The response-buffer input is discarded during the preceding flush. |
| `rspJoin_rspBuffer_output` | 1 | 2010–2020 | `IBusSimplePlugin.scala:369` drives FIFO pop ready with `output.ready || flush`. FIFO pop is accepted during the flush even though buffer-output ready is 0. Output valid falls at the next edge. |
| `rspJoin_join` | 1 | 2010–2020 | `IBusSimplePlugin.scala:387` ANDs stage-output valid with response-buffer valid. The response-buffer discard removes this offer. |
| `rspJoin_join_haltWhen` | 1 | 2010–2020 | `IBusSimplePlugin.scala:391` gates that join. It inherits the response-buffer discard. |

The final standard-library recognizer also supports direct registered clears
inside a method named `m2sPipeWithFlush`. It requires an unconditional alias
path to the valid register and a top-level conditional assignment of False.
It does not infer arbitrary halt equations or discarded FIFO transactions.
Those streams retain strict checks and explicit disposition hints. The three remaining conditions now have exact project bindings in
`CheckSemantics.scala`. A later native capture at `rvw/out/cancel-bound49`
completed all 49 programs with zero firings and all 49 C1 results passing.
The current `checks-qualification.json` records this capture. Formal was NOT RUN.
The earlier capture is retained in `pre-cancellation-qualification.json`.
