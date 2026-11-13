"""Independent TileLink A/D and coherent Probe/Release/Grant bookkeeping."""


def render(signals,depth=4,options=None):
    options=options or {}
    signals=dict(signals)
    constants=[]
    # Spinal removes zero-bit source/sink fields from emitted RTL.
    for role,chs in [('source',('a','d','b','c')),('sink',('d','e'))]:
        if options.get(role+'_width')==0:
            for ch in chs:
                if ch+'.valid' not in signals:continue
                key=ch+'.payload.'+role
                if key in signals:raise ValueError('zero-width '+role+' has a recorded RTL field')
                local=key.replace('.','_');signals[key]=(local,None,None,1,None,False)
                constants.append("wire "+local+"=1'b0;\n")
    def net(key,default=None):
        if key in signals:return key.replace('.','_')
        if default is None:raise ValueError('missing TileLink field '+key)
        return default
    def bits(key):net(key);return signals[key][3]
    coherent='b.valid' in signals
    for ch in ('a','d')+ (('b','c','e') if coherent else ()):
        net(ch+'.valid');net(ch+'.ready')
        if ch!='e':
            for key in ('opcode','param','source','size'):net(ch+'.payload.'+key)
        if ch in ('a','b','c'):net(ch+'.payload.address')
    source_width=0 if options.get('source_width')==0 else bits('a.payload.source')
    if not 0<=source_width<=8 or bits('d.payload.source')!=max(1,source_width):
        raise ValueError('TileLink source widths must match in 0..8')
    size_width=bits('a.payload.size');max_size=options.get('size_max',min(12,(1<<size_width)-1))
    if type(max_size) is not int or not 0<=max_size<=12:
        raise ValueError('TileLink size_max must be in 0..12')
    if any(bits(ch+'.payload.size')!=size_width for ch in ('d',)+ (('b','c') if coherent else ())):
        raise ValueError('TileLink size widths differ')
    if max_size >= (1<<size_width):raise ValueError('TileLink size_max exceeds size field width')
    data_width=bits('d.payload.data')
    if data_width not in (8,16,32,64,128,256,512,1024):raise ValueError('unsupported TileLink data width')
    lanes=data_width//8;beat_size=lanes.bit_length()-1
    for ch in ('a','c'):
        if ch+'.payload.data' in signals and bits(ch+'.payload.data')!=data_width:
            raise ValueError('TileLink data widths differ')
    for ch in ('a',)+ (('b','c') if coherent else ()):
        if not 1<=bits(ch+'.payload.address')<=64:raise ValueError('unsupported TileLink address width')
    if coherent:
        net('c.payload.corrupt')
        if any(bits(ch+'.payload.source')!=max(1,source_width) for ch in ('b','c')):
            raise ValueError('TileLink coherent source widths differ')
        sink_width=bits('d.payload.sink')
        if not 1<=sink_width<=8 or bits('e.payload.sink')!=sink_width:raise ValueError('TileLink sink widths must match in 1..8')
    for key,actual in [('source_width',source_width),('data_width',data_width),('with_bce',int(coherent))]:
        if key in options and options[key]!=actual:raise ValueError('TileLink option differs from fields: '+key)
    text=''.join(constants)+f'localparam integer RVW_TL_SOURCES={1<<source_width};\n'
    # Only accepted beats start a burst. Unaccepted first offers can change.
    for ch in ('a','d')+ (('c',) if coherent else ()):
        payload=sorted(k for k in signals if k.startswith(ch+'.payload.'))
        header=[k for k in payload if k.rsplit('.',1)[1] not in ('data','mask','corrupt')]
        pack=lambda keys:'{'+','.join(net(k) for k in keys)+'}'
        hp=pack(header);pp=pack(payload);hw=sum(bits(k) for k in header);pw=sum(bits(k) for k in payload)
        op=net(ch+'.payload.opcode');sz=net(ch+'.payload.size');v=net(ch+'.valid');r=net(ch+'.ready')
        has={'a':f'({op}<=3)','d':f'({op}==1 || {op}==5)','c':f'({op}==5 || {op}==7)'}[ch]
        text+=f'''reg [12:0] rvw_tl_{ch}_beat=0;
reg [{hw-1}:0] rvw_tl_{ch}_header;
reg [{pw-1}:0] rvw_tl_{ch}_previous;
reg rvw_tl_{ch}_stall=0;
wire rvw_tl_{ch}_first=rvw_tl_{ch}_beat==0;
wire rvw_tl_{ch}_last=!{has} || {sz}<={beat_size} || rvw_tl_{ch}_beat==((64'd1 << ({sz}-{beat_size}))-1);
always @(posedge clk) begin
 if(reset) begin rvw_tl_{ch}_beat<=0;rvw_tl_{ch}_stall<=0;end
 else begin
  if(!rvw_tl_{ch}_first && {v}) assert({hp}==rvw_tl_{ch}_header);
  if(rvw_tl_{ch}_stall) begin assert({v});assert({pp}==rvw_tl_{ch}_previous);end
  rvw_tl_{ch}_stall<=!rvw_tl_{ch}_first && {v} && !{r};
  rvw_tl_{ch}_previous<={pp};
  if({v} && {r}) begin
   if(rvw_tl_{ch}_first) rvw_tl_{ch}_header<={hp};
   rvw_tl_{ch}_beat<=rvw_tl_{ch}_last ? 0 : rvw_tl_{ch}_beat+1;
  end
 end
end
'''
    aop=net('a.payload.opcode');dop=net('d.payload.opcode');aid=net('a.payload.source');did=net('d.payload.source')
    asz=net('a.payload.size');dsz=net('d.payload.size');ap=net('a.payload.param');dp=net('d.payload.param')
    acor=net('a.payload.corrupt',"1'b0");dcor=net('d.payload.corrupt',"1'b0");denied=net('d.payload.denied')
    text+=f'''reg rvw_tl_busy[0:RVW_TL_SOURCES-1];
reg [2:0] rvw_tl_op[0:RVW_TL_SOURCES-1];
reg [{size_width-1}:0] rvw_tl_size[0:RVW_TL_SOURCES-1];
wire rvw_tl_af=a_valid && a_ready && rvw_tl_a_first;
wire rvw_tl_df=d_valid && d_ready && rvw_tl_d_first;
wire rvw_tl_fresh=!rvw_tl_busy[{did}] && a_valid && rvw_tl_a_first && {aid}=={did};
wire [2:0] rvw_tl_expected_op=rvw_tl_fresh ? {aop} : rvw_tl_op[{did}];
wire [{size_width-1}:0] rvw_tl_expected_size=rvw_tl_fresh ? {asz} : rvw_tl_size[{did}];
wire rvw_tl_grant={dop}==4 || {dop}==5;
always @(posedge clk) begin
 if(reset) for(integer i=0;i<RVW_TL_SOURCES;i=i+1)rvw_tl_busy[i]<=0;
 else begin
  if(a_valid) begin
   assert({aop}<={7 if coherent else 5});assert({asz}<={max_size});
   assert((a_payload_address & ((64'd1 << {asz})-1))==0);
   if({aop}==2) begin assert({ap}<=4);end
   else if({aop}==3) begin assert({ap}<=3);end
   else if({aop}==5) assert({ap}<=1);
   else if({aop}>=6) begin assert({asz}>={beat_size});assert({ap}<=2);if({aop}==7)assert({ap}!=0);end
   else assert({ap}==0);
   if({aop}>=4)assert(!{acor});
  end
  if(rvw_tl_af) begin
   assert(!rvw_tl_busy[{aid}]);rvw_tl_busy[{aid}]<=1;rvw_tl_op[{aid}]<={aop};rvw_tl_size[{aid}]<={asz};
  end
  if(d_valid) begin
   assert({dop}==0 || {dop}==1 || {dop}==2 || ({int(coherent)} && ({dop}==4 || {dop}==5 || {dop}==6)));
   assert({dsz}<={max_size});
   if(rvw_tl_grant)assert({dp}<=1);else assert({dp}==0);
   if(rvw_tl_grant || {dop}==6)assert({dsz}>={beat_size});
   if({dop}!=1 && {dop}!=5)assert(!{dcor});
   if(({dop}==1 || {dop}==5) && {denied})assert({dcor});
   if({dop}==6)assert(!{denied});
  end
  if(d_valid && rvw_tl_d_first && {dop}!=6) begin
   assert(rvw_tl_busy[{did}] || rvw_tl_fresh);
   assert({dsz}==rvw_tl_expected_size);
   if(rvw_tl_expected_op<=1)assert({dop}==0);
   else if(rvw_tl_expected_op<=4)assert({dop}==1);
   else if(rvw_tl_expected_op==5)assert({dop}==2);
   else if(rvw_tl_expected_op==6)assert(rvw_tl_grant);
   else assert({dop}==4);
   if(rvw_tl_fresh && d_ready)assert(a_ready);
  end
  if(rvw_tl_df && {dop}!=6)rvw_tl_busy[{did}]<=0;
 end
end
'''
    if 'a.payload.mask' in signals:
        if bits('a.payload.mask')!=lanes:raise ValueError('TileLink mask width differs from data bytes')
        text+=f'''wire [{lanes-1}:0] rvw_tl_mask=(({asz}>={beat_size} ? {lanes}'d{(1<<lanes)-1} : ((64'd1 << (64'd1 << {asz}))-1)) << (a_payload_address % {lanes}));
always @(posedge clk) if(!reset && a_valid) begin
 if({aop}==1) assert((a_payload_mask & ~rvw_tl_mask)==0);
 else if({aop}<=5)assert(a_payload_mask==rvw_tl_mask);
 else assert(a_payload_mask=={lanes}'d{(1<<lanes)-1});
end
'''
    if 'a.payload.data' not in signals:
        text+=f'always @(posedge clk) if(!reset && a_valid) assert({aop}>=4);\n'
    if coherent and 'c.payload.data' not in signals:
        text+='always @(posedge clk) if(!reset && c_valid) assert(c_payload_opcode==4 || c_payload_opcode==6);\n'
    if coherent:
        from .tilelink_coherent import render as coherent_body
        text+=coherent_body(signals,depth,max_size)
    return text
