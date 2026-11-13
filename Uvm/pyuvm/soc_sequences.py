"""pyuvm virtual sequence wrapper for project SoC execution callbacks."""
import pyuvm
from rvw.uvm.scenarios import SocScenarios

class SocVirtualSequence(pyuvm.uvm_sequence):
    def __init__(self, scenario='boot', *, seed=1, **options):
        super().__init__('soc_'+scenario)
        self.scenario,self.seed,self.options=scenario,seed,options

    async def body(self):
        library=SocScenarios(self.sequencer.backend,seed=self.seed)
        if self.scenario not in ('boot','interrupt_storm','bus_error','reset_during_traffic'):
            raise ValueError('unknown SoC scenario')
        self.report=await getattr(library,self.scenario)(**self.options)
