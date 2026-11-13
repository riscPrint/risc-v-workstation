"""Native Spike ISA execution with the independent Python PLIC model."""
from rvw.cosim.devices import Plic,PlicMap
from .spike_device import run as run_device


def run(directory,scenario,config,timeout,shim_inputs):
    plan=scenario['reference_model'];layout=PlicMap(**plan['layout']);device=Plic(layout)
    mmio=[(layout.priority,4*(layout.sources+1)),(layout.pending,4*(layout.sources//32+1)),
          (layout.enable,layout.enable_stride*layout.contexts),(layout.context,layout.context_stride*layout.contexts)]
    cause=11 if '-m-' in scenario['id'] else 9
    def drive(event):
        if event['kind']!='plic-level':raise ValueError('unsupported PLIC stimulus')
        device.set_level(event['source'],event['level'])
    return run_device(directory,scenario,config,timeout,shim_inputs,device=device,mmio=mmio,
                      irq=lambda:((1<<63)|cause) if device.irq(plan['context']) else 0,drive=drive,
                      scope='native Spike ISA execution with Python PLIC; no DUT coverage')
