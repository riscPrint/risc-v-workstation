"""A real CPU and DMA traffic engine share the composed SoC through AXI."""
import json
from pathlib import Path
import cocotb
from cocotb.triggers import RisingEdge,ClockCycles
from rvw.sim.bench import start


@cocotb.test()
async def shared_memory(d):
    await start(d)
    for cycle in range(1,50001):
        await RisingEdge(d.clk)
        if int(d.core_dmaError.value):break
        if int(d.finisher_done.value) and (int(d.finisher_code.value)!=1 or int(d.core_dmaDone.value)):break
    await ClockCycles(d.clk,10)
    report=dict(cycles=cycle,retired=int(d.core_retired.value),dma_writes=int(d.core_dmaWrites.value),
                dma_reads=int(d.core_dmaReads.value),dma_done=bool(int(d.core_dmaDone.value)),
                dma_error=bool(int(d.core_dmaError.value)),finisher=int(d.finisher_code.value))
    Path('cpu-dma-checks.json').write_text(json.dumps(report,indent=2)+'\n')
    assert report['finisher']==1,'CPU_DMA_FINISHER'
    assert report['retired']>0 and report['dma_done'] and not report['dma_error'],'CPU_DMA_PROGRESS'
    assert report['dma_reads']==33 and report['dma_writes']==33,'CPU_DMA_TRANSFERS'
