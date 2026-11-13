"""Native Spike ISA execution with an explicitly model-based RERI device."""
from .reri_transactions import Device
from .spike_device import run as run_device


def run(directory,scenario,config,timeout,shim_inputs):
    base=config['reri']['base'];initial=config['reri'].get('reference_initial_status','0x0')
    initial=int(initial,0) if isinstance(initial,str) else initial
    if type(initial) is not int or not 0<=initial<1<<64:raise ValueError('invalid RERI reference initial status')
    device=Device(base,status=initial)
    return run_device(directory,scenario,config,timeout,shim_inputs,device=device,mmio=[(base,128)],
                      irq=lambda:0,drive=device.event,
                      scope='native Spike ISA execution with Python RERI; no DUT coverage or signal delivery claim')
