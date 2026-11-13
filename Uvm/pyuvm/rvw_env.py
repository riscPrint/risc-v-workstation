"""Optional pyuvm wrappers. Install pyuvm 4 and cocotb 2."""
import pyuvm
from rvw.sim.uvm_models import Scoreboard, Memory, RetirementMonitor, RegisterModel


class BaseScoreboard(pyuvm.uvm_scoreboard):
    def build_phase(self):
        self.model = Scoreboard()

    def expect(self, transaction):
        self.model.expect(transaction)

    def observe(self, transaction):
        self.model.observe(transaction)

    def check_phase(self):
        self.model.finish()


class BaseEnvironment(pyuvm.uvm_env):
    def build_phase(self):
        self.scoreboard = BaseScoreboard('scoreboard', self)
        self.virtual_sequencer = pyuvm.uvm_sequencer('virtual_sequencer', self)


class CpuEnvironment(BaseEnvironment):
    """Project supplies memory regions and a strict retirement comparator.

    Connect project instruction/data agents to the same memory object. Connect
    the retirement monitor to a live reference comparator or a trace oracle.
    This class does not infer CPU pins or claim a Spike connection.
    """
    def build_phase(self):
        super().build_phase()
        config = pyuvm.ConfigDB().get(self, '', 'cpu')
        self.memory = Memory(config['memory_base'], config['memory_size'])
        self.retirements = RetirementMonitor(config['compare'])
        self.interrupt_agent = config['interrupt_agent']
        self.debug_agent = config['debug_agent']
        self.registers = (RegisterModel(config['register_map'], config['frontdoor'], config.get('backdoor'))
                          if config.get('register_map') else None)

    def check_phase(self):
        self.retirements.finish()
