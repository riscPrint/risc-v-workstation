"""Generate UVM RAL from the validated rvw.soc/1 register subset."""
from rvw.soc.model import load


def generate(path):
    obj = load(path)
    lines = ['package rvw_ral;', ' import uvm_pkg::*;', ' `include "uvm_macros.svh"']
    regs = []
    for region in obj['regions']:
        for reg in region['registers']:
            name = 'reg_' + region['name'] + '_' + reg['name']
            # No silent combination of read-clear and write-one-clear semantics.
            if reg['read_action'] == 'clear' and reg['write_action'] == 'one_to_clear':
                raise ValueError('combined RC and W1C is unsupported')
            access = {'r': 'RO', 'w': 'WO', 'rw': 'RW'}[reg['access']]
            if reg['read_action'] == 'clear':
                if reg['access'] != 'r':
                    raise ValueError('read-clear requires read-only access')
                access = 'RC'
            if reg['write_action'] == 'one_to_clear':
                if reg['access'] != 'rw':
                    raise ValueError('one-to-clear requires read-write access')
                access = 'W1C'
            width, reset = reg['width'], reg['reset']
            lines += [f' class {name} extends uvm_reg;', f'  `uvm_object_utils({name})',
                      '  uvm_reg_field value;',
                      f'  function new(string name="{name}"); super.new(name,{width},UVM_NO_COVERAGE); endfunction',
                      '  virtual function void build();', '   value=new("value");',
                      f'   value.configure(this,{width},0,"{access}",0,64\'h{(reset or 0):x},{int(reset is not None)},0,0);',
                      '  endfunction', ' endclass']
            regs.append((name, region['base'] + reg['offset'], reg['access']))
    lines += [' class register_block extends uvm_reg_block;',
              '  `uvm_object_utils(register_block)']
    lines += [f'  {name} {name}_h;' for name, _, _ in regs]
    lines += ['  function new(string name="register_block"); super.new(name,UVM_NO_COVERAGE); endfunction',
              '  virtual function void build();',
              '   default_map=create_map("map",0,4,UVM_LITTLE_ENDIAN,1);']
    for name, address, access in regs:
        rights = {'r': 'RO', 'w': 'WO', 'rw': 'RW'}[access]
        lines += [f'   {name}_h=new("{name}");', f'   {name}_h.configure(this); {name}_h.build();',
                  f'   default_map.add_reg({name}_h,64\'h{address:x},"{rights}");']
    lines += ['   lock_model();', '  endfunction', ' endclass', 'endpackage']
    return '\n'.join(lines) + '\n'


def register(sub):
    from pathlib import Path
    parser = sub.add_parser('uvm-ral', help='generate UVM register classes from rvw.soc/1')
    parser.add_argument('--map', type=Path, required=True)
    parser.add_argument('--out', type=Path, required=True)
    parser.set_defaults(func=command)


def command(args):
    text = generate(args.map)
    with args.out.open('x') as dst:
        dst.write(text)
    return 0
