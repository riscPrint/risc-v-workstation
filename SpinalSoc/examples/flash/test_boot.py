"""Boot a real composed CPU from a ROM stub and the SPI NOR pin model."""
import hashlib
import json
import os
from pathlib import Path
from types import SimpleNamespace
import cocotb
from cocotb.triggers import FallingEdge,RisingEdge,ClockCycles
from rvw.sim.bench import start
from rvw.vip.spi import CocotbAgent,Pins
from rvw.vip.spi_flash import ReadOnlyNor


@cocotb.test()
async def boot(d):
    here=Path(__file__).resolve().parent
    config=json.loads((here/'boot.json').read_text())
    for name,digest in config['memory_images'].items():
        assert hashlib.sha256((here/'rtl'/name).read_bytes()).hexdigest()==digest,'MEMORY_IMAGE_CHANGED'
    image=(here/'flash.bin').read_bytes()
    assert hashlib.sha256(image).hexdigest()==config['flash_sha256'],'FLASH_IMAGE_CHANGED'
    corrupt=os.environ.get('RVW_FLASH_CORRUPT')=='1'
    if corrupt:
        image=bytearray(image);image[256]^=1;image=bytes(image)
    flash=ReadOnlyNor(image,capacity=65536)
    class Reset:
        @property
        def value(self):return 1-int(d.reset.value)
    view=SimpleNamespace(clk=d.clk,reset_n=Reset(),flash_cs_n=d.spi_pins_ss,
                         flash_sclk=d.spi_pins_sclk,flash_mosi=d.spi_pins_mosi,flash_miso=d.spi_pins_miso)
    agent=CocotbAgent(view,'flash')
    async def drive():
        while True:
            await FallingEdge(d.clk)
            d.spi_pins_miso.value=flash.step(agent.pins()).miso
    d.spi_pins_miso.value=1
    driving=cocotb.start_soon(drive())
    monitoring=cocotb.start_soon(agent.run_monitor())
    await start(d)
    initial_word=int(d.boot_ram_word0.value)
    assert initial_word==0,'RAM_PRELOADED_WITH_PAYLOAD'
    cycles=0
    for cycles in range(1,config['max_cycles']+1):
        await RisingEdge(d.clk)
        if int(d.finisher_done.value):break
    await ClockCycles(d.clk,10)
    report=dict(cycles=cycles,done=bool(int(d.finisher_done.value)),code=int(d.finisher_code.value),
                retired=int(d.core_retired.value),ram_initial_word=initial_word,ram_word0=int(d.boot_ram_word0.value),
                corrupt=corrupt,core_revision=config['core_revision'],tools_revision=config['tools_revision'],flash=flash.finish(),spi_words=agent.monitor.coverage['words'],
                payload_sha256=config['payload_sha256'],boot_sha256=config['boot_sha256'])
    Path('boot-checks.json').write_text(json.dumps(report,indent=2)+'\n')
    agent.monitor.finish()
    driving.cancel();monitoring.cancel()
    assert report['done'],'FLASH_BOOT_TIMEOUT'
    assert report['code']==1,f"FLASH_BOOT_FINISHER:{report['code']}"
    assert report['retired']>0,'FLASH_BOOT_NO_INSTRUCTIONS'
    assert report['ram_word0']==config['first_word'],'RAM_PAYLOAD_MISMATCH'
    assert report['flash']['read_bytes']==config['payload_size'],'FLASH_PAYLOAD_NOT_READ'
    assert report['flash']['transactions']==1,'FLASH_TRANSACTION_COUNT'
    assert report['spi_words']==config['payload_size']+4,'SPI_BOOT_WORD_COUNT'
