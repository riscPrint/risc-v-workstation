"""Request-time PMP/ePMP access checks over a reviewed CSR-bank port binding."""


def generate(prop, ports, signal, clock, reset):
    def port(key,direction,width=None):
        name=signal(prop[key]);p=ports[name]
        if p['direction']!=direction or (width is not None and p['width']!=width):
            raise ValueError('invalid PMP port: '+key)
        return name
    address=port('address','input');aw=ports[address]['width']
    if not 4<=aw<=64:raise ValueError('PMP address width must be 4..64')
    request=port('request','input',1);grant=port('grant','output',1)
    privilege=port('privilege','input',2);operation=port('operation','input',2)
    size=port('size','input',2)
    mml=signal(prop['mml']);mmwp=signal(prop['mmwp'])
    if any(ports[p]['width']!=1 for p in (mml,mmwp)):raise ValueError('MML and MMWP must be scalar')
    entries=prop['entries'];latency=prop.get('latency',0)
    if not entries or len(entries)>16 or type(latency) is not int or not 0<=latency<=64:
        raise ValueError('PMP needs 1..16 entries and latency 0..64')
    names=[]
    for entry in entries:
        cfg,addr=signal(entry['config']),signal(entry['address'])
        if ports[cfg]['width']!=8 or ports[addr]['width']!=aw-2:
            raise ValueError('PMP config/address widths must be 8 and physical width minus 2')
        names.append((cfg,addr))
    prefix='rvwa_pmp'
    extra=[f'wire [{aw}:0] {prefix}_end = {{1\'b0,{address}}} + (({aw+1}\'d1 << {size})-1);',
           f'reg {prefix}_allow, {prefix}_matched;',f'reg [2:0] {prefix}_rights;',
           f'reg [{aw}:0] {prefix}_lo, {prefix}_hi, {prefix}_mask;',f'reg {prefix}_open;',
           f'integer {prefix}_bit;', 'always @* begin',
           f'{prefix}_allow=({privilege}==3 && !{mmwp} && !({mml} && {operation}==2));',
           f'{prefix}_bit=0; {prefix}_matched=0; {prefix}_rights=0; {prefix}_lo=0; {prefix}_hi=0; {prefix}_mask=0; {prefix}_open=0;']
    previous=f'{aw+1}\'d0'
    for cfg,addr in names:
        encoded=f'{{1\'b0,{addr},2\'b00}}'
        extra += [f'{prefix}_lo=0; {prefix}_hi=0;',f'case ({cfg}[4:3])',
                  f'1: begin {prefix}_lo={previous}; {prefix}_hi={encoded}; end',
                  f'2: begin {prefix}_lo={encoded}; {prefix}_hi={encoded}+{aw+1}\'d4; end',
                  f'3: begin {prefix}_mask=7; {prefix}_open=1;',
                  f'for ({prefix}_bit=0; {prefix}_bit<{aw-3}; {prefix}_bit={prefix}_bit+1) begin',
                  f'if ({prefix}_open && {addr}[{prefix}_bit]) {prefix}_mask[{prefix}_bit+3]=1; else {prefix}_open=0; end',
                  f'{prefix}_lo={encoded} & ~{prefix}_mask; {prefix}_hi={prefix}_lo+{prefix}_mask+1; end',
                  'endcase',
                  f'if (!{prefix}_matched && {cfg}[4:3]!=0 && {prefix}_hi>{prefix}_lo && '
                  f'{{1\'b0,{address}}} < {prefix}_hi && {prefix}_end >= {prefix}_lo) begin',
                  f'{prefix}_matched=1; {prefix}_rights={cfg}[2:0];',
                  f'if (!{mml}) begin',
                  f'if ({privilege}==3 && !{cfg}[7]) {prefix}_rights=7;',
                  f'else if ({cfg}[1] && !{cfg}[0]) {prefix}_rights=0;',
                  'end else begin',
                  f'if ({cfg}[1:0]==2) begin',
                  f'if (!{cfg}[7]) {prefix}_rights=({privilege}==3 || {cfg}[2]) ? 3 : 1;',
                  f'else {prefix}_rights=({privilege}==3 && {cfg}[2]) ? 5 : 4;',
                  f'end else if ({cfg}[7] && {cfg}[2:0]==7) {prefix}_rights=1;',
                  f'else if ({cfg}[7] != ({privilege}==3)) {prefix}_rights=0;',
                  'end',
                  f'{prefix}_allow=({{1\'b0,{address}}}>={prefix}_lo && {prefix}_end<{prefix}_hi && '
                  f'{prefix}_end<{aw+1}\'d{1<<aw} && {operation}<3 && ({operation}==0 ? {prefix}_rights[0] : ({operation}==1 ? {prefix}_rights[1] : ({operation}==2 ? {prefix}_rights[2] : 0))));',
                  'end']
        previous=encoded
    extra += [f'if ({privilege}==2 || {operation}==3 || {prefix}_end>={aw+1}\'d{1<<aw}) {prefix}_allow=0;', 'end']
    valid,allowed=request,f'{prefix}_allow'
    for i in range(latency):
        extra += [f'reg {prefix}_valid{i}=0, {prefix}_saved{i};',f'always @(posedge {clock}) begin',
                  f'{prefix}_valid{i} <= !{reset} && {valid}; {prefix}_saved{i} <= {allowed}; end']
        valid,allowed=f'{prefix}_valid{i}',f'{prefix}_saved{i}'
    return extra,f'!({valid}) || !{grant} || ({allowed})'
