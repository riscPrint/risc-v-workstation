"""Software descriptions for the explicit composed peripheral profiles."""
import json

COMPATIBLE={'Clint':'riscv,clint0','Plic':'riscv,plic0','Uart16550':'rvw,uart16550-subset',
            'Uart16550Full':'ns16550a','Gpio':'rvw,gpio','Spi':'rvw,spinal-spi','I2c':'rvw,spinal-i2c','Timer':'rvw,timer','Finisher':'rvw,test-finisher'}


def board_dts(obj,spec):
    def frequency(name):
        domain = spec['devices'][name].get('domain')
        return spec.get('domains', {}).get(domain, {}).get('clock_hz', spec['clock_hz'])
    timer = next((r['name'] for r in obj['regions'] if spec['devices'][r['name']].get('class', '').split('.')[-1] == 'Clint'), None)
    timebase = frequency(timer) if timer is not None else spec['clock_hz']
    lines=['/dts-v1/;','/ {','  #address-cells = <2>;','  #size-cells = <2>;',
           '  compatible = "rvw,verification-soc";',f'  model = {json.dumps(obj["name"])};',
           '  cpus {','    #address-cells = <1>;','    #size-cells = <0>;',
           f'    timebase-frequency = <{timebase}>;',
           '    rvw_cpu0: cpu@0 {','      device_type = "cpu";','      reg = <0>;',
           '      compatible = "riscv";',f'      riscv,isa = {json.dumps(obj["platform"]["isa"])};',
           '      rvw_cpu_intc: interrupt-controller {','        #interrupt-cells = <1>;',
           '        interrupt-controller;','        compatible = "riscv,cpu-intc";','      };','    };','  };',
           '  soc {','    #address-cells = <2>;','    #size-cells = <2>;','    compatible = "simple-bus";','    ranges;']
    for r in obj['regions']:
        base,size=r['base'],r['size']
        name=r['name']
        lines += [f'    region_{name}: {name}@{base:x} {{',f'      reg = <0x{base>>32:x} 0x{base&0xffffffff:x} 0x{size>>32:x} 0x{size&0xffffffff:x}>;']
        if r['kind']=='ram':
            if spec['devices'][name]['type'] == 'rom':
                lines += ['      compatible = "mtd-rom";', '      bank-width = <4>;']
            else:
                lines += ['      device_type = "memory";']
        else:
            cls=spec['devices'][name].get('class','').split('.')[-1]
            compatible=COMPATIBLE.get(cls)
            if compatible:lines += [f'      compatible = "{compatible}";']
            causes=[i['cause'] for i in obj['interrupts'] if i['region']==name]
            if causes:
                lines += ['      interrupts-extended = '+', '.join(f'<&rvw_cpu_intc {i}>' for i in causes)+';']
            if cls=='Plic':lines+=['      interrupt-controller;','      #interrupt-cells = <1>;','      riscv,ndev = <7>;']
            if cls in ('Uart16550','Uart16550Full'):lines+=['      reg-shift = <2>;','      reg-io-width = <4>;',f'      clock-frequency = <{frequency(name)}>;']
        lines += ['    };']
    return '\n'.join(lines+['  };','};'])+'\n'


def linker(obj):
    execute=next((r for r in obj['regions'] if r['kind']=='ram' and 'x' in r['permissions']),None)
    writable=next((r for r in obj['regions'] if r['kind']=='ram' and 'w' in r['permissions']),None)
    if execute is None or writable is None:
        return None
    return f'''/* Link from this export directory. Startup code remains project-owned. */
INCLUDE memory.ld
ENTRY(_start)
SECTIONS {{
  .text : {{ *(.text*) *(.rodata*) }} > {execute['name']}
  .data : {{ *(.data*) *(.sdata*) }} > {writable['name']}
  .bss (NOLOAD) : {{ __bss_start = .; *(.bss*) *(.sbss*) *(COMMON) __bss_end = .; }} > {writable['name']}
  __stack_top = ORIGIN({writable['name']}) + LENGTH({writable['name']});
}}
'''
