"""Seeded test master, live bus monitors and independent map-derived RAL."""
import json
import os
import random
from pathlib import Path
import cocotb
from cocotb.triggers import Timer
import pyuvm
from rvw.uvm.soc import SocEnvironment
from rvw.vip import apb, axi, uart

HERE = Path(__file__).resolve().parent

class Master:
    def __init__(self, dut):
        self.dut, self.services, self.cycles = dut, None, 0

    def get(self, name): return int(getattr(self.dut, 'apb_PSLVERROR' if name=='apb_PSLVERR' else name).value)
    def put(self, **pins):
        for name, value in pins.items(): getattr(self.dut, 'apb_PSLVERROR' if name=='apb_PSLVERR' else name).value = value

    async def tick(self):
        self.put(clk=0)
        await Timer(5, unit='ns')
        if self.services:
            self.services.buses['control'].sample(apb.Pins(
                reset_n=1-self.get('reset'), **{f:self.get('apb_'+f.upper()) for f in
                ('psel','penable','paddr','pwrite','pwdata','pready','prdata','pslverr')},
                pstrb=15 if self.get('apb_PWRITE') else 0))
            values={f:self.get('axi_'+f.replace('valid','_valid').replace('ready','_ready')) for f in
                    ('awvalid','awready','wvalid','wready','bvalid','bready','arvalid','arready','rvalid','rready')}
            self.services.buses['serial'].sample(axi.Pins(reset_n=1-self.get('reset'), **values,
                aw=axi.Address(self.get('axi_aw_payload_addr')),
                ar=axi.Address(self.get('axi_ar_payload_addr')),
                w=axi.Write(self.get('axi_w_payload_data'), self.get('axi_w_payload_strb')),
                b=axi.Response(response=self.get('axi_b_payload_resp')),
                r=axi.Response(response=self.get('axi_r_payload_resp'),data=self.get('axi_r_payload_data'))))
            self.services.uart.sample(self.get('tx'), reset_n=not self.get('reset'))
        self.put(clk=1)
        await Timer(5, unit='ns')
        self.cycles += 1

    async def until(self, signal):
        for _ in range(100):
            await Timer(1, unit='ns')
            ready=self.get(signal)
            await self.tick()
            if ready: return
        raise AssertionError('bus handshake timeout: '+signal)

    async def apb(self, address, write=False, value=0):
        self.put(apb_PSEL=1,apb_PENABLE=0,apb_PADDR=address,apb_PWRITE=int(write),apb_PWDATA=value)
        await self.tick()
        self.put(apb_PENABLE=1)
        await Timer(1, unit='ns')
        result=self.get('apb_PRDATA')
        assert not self.get('apb_PSLVERROR')
        await self.until('apb_PREADY')
        self.put(apb_PSEL=0,apb_PENABLE=0)
        await self.tick()
        return result

    async def axil(self, address, write=False, value=0):
        if write:
            self.put(axi_aw_payload_addr=address,axi_aw_valid=1)
            await self.until('axi_aw_ready'); self.put(axi_aw_valid=0)
            await self.tick() # exercise separated address and data channels
            self.put(axi_w_payload_data=value,axi_w_payload_strb=15,axi_w_valid=1)
            await self.until('axi_w_ready'); self.put(axi_w_valid=0)
            await self.until('axi_b_valid')
        else:
            self.put(axi_ar_payload_addr=address,axi_ar_valid=1)
            await self.until('axi_ar_ready'); self.put(axi_ar_valid=0)
            for _ in range(100):
                await Timer(1,unit='ns')
                valid=self.get('axi_r_valid'); result=self.get('axi_r_payload_data')
                await self.tick()
                if valid: return result
            raise AssertionError('AXI read timeout')

class Frontdoor:
    def __init__(self, transfer): self.transfer=transfer
    async def read(self,address,width):
        assert width==32
        return await self.transfer(address)
    async def write(self,address,value,width):
        assert width==32
        await self.transfer(address,True,value)

@pyuvm.test()
class ConnectedSoc(pyuvm.uvm_test):
    async def run_phase(self):
        self.raise_objection()
        try:
            master=Master(cocotb.top)
            master.put(clk=0,reset=1,apb_PSEL=0,apb_PENABLE=0,apb_PADDR=0,apb_PWRITE=0,apb_PWDATA=0,
                axi_aw_valid=0,axi_aw_payload_addr=0,axi_aw_payload_prot=0,
                axi_w_valid=0,axi_w_payload_data=0,axi_w_payload_strb=0,axi_b_ready=1,
                axi_ar_valid=0,axi_ar_payload_addr=0,axi_ar_payload_prot=0,axi_r_ready=1)
            services=SocEnvironment(HERE/'map.json', reference=None,cpu_required=False,
                protocols={'control':'apb','serial':'axi-lite'},
                frontdoors={'control':Frontdoor(master.apb),'serial':Frontdoor(master.axil)})
            master.services=services
            for _ in range(5): await master.tick()
            master.put(reset=0)
            await master.tick()
            for reg in ('control.data','serial.data'): await services.registers.read(reg,check=True)
            rng=random.Random(int(os.environ.get('RVW_SOC_SEED','1')))
            for _ in range(4):
                await services.registers.write('control.data',rng.getrandbits(32))
                await services.registers.read('control.data',check=True)
                value=rng.randrange(256)
                services.serial.expect(uart.Frame(value))
                await services.registers.write('serial.data',value)
                await services.registers.read('serial.data',check=True)
                for _ in range(88): await master.tick()
            report=services.finish(0)
            assert report['uart_frames']==4
            Path('soc-checks.json').write_text(json.dumps(dict(report,cycles=master.cycles),indent=2)+'\n')
        finally:
            self.drop_objection()
