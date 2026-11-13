"""Project-configured pyuvm SoC composition; active wire tasks stay in the project."""
import pyuvm
from rvw.uvm.soc import SocEnvironment


class SocEnvironmentComponent(pyuvm.uvm_env):
    def build_phase(self):
        cfg = pyuvm.ConfigDB().get(self, '', 'soc')
        self.config = cfg
        self.services = SocEnvironment(cfg['map'], reference=cfg['reference'],
            protocols=cfg['protocols'], frontdoors=cfg['frontdoors'],
            uart_config=cfg.get('uart_config'))
        self.virtual_sequencer = pyuvm.uvm_sequencer('virtual_sequencer', self)
        self.virtual_sequencer.services = self.services

    async def run_phase(self):
        # The project supplies one coroutine that samples live CPU/bus/UART pins.
        await self.config['run'](self.services)

    def check_phase(self):
        self.report = self.services.finish(self.config['retirements'])
