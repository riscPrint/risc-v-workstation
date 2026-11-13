"""Bounded five-channel AXI transaction trackers, independent of DUT storage."""


def render(kind,signals,depth=4,max_beats=256):
    if type(depth) is not int or not 1<=depth<=64:
        raise ValueError('AXI tracker depth must be in 1..64')
    if type(max_beats) is not int or not 1<=max_beats<=256:
        raise ValueError('AXI write strobe history must be in 1..256 beats')
    if kind not in ('axi4','axi_lite4'): raise ValueError('AXI transaction kind required')
    def net(key,default=None):
        if key in signals:return key.replace('.','_')
        if default is None:raise ValueError('missing transaction field '+key)
        return default
    def width(key): return signals[key][3]
    for ch in ('aw','w','b','ar','r'):
        net(ch+'.valid');net(ch+'.ready')
    net('w.payload.data');net('r.payload.data');net('aw.payload.addr');net('ar.payload.addr')
    data_width=width('w.payload.data')
    if data_width!=width('r.payload.data') or data_width not in (8,16,32,64,128,256,512,1024):
        raise ValueError('transaction trackers require equal power-of-two read/write data widths')
    if any(not 1<=width(ch+'.payload.addr')<=64 for ch in ('aw','ar')):
        raise ValueError('AXI address width must be in 1..64')
    ids=[width(ch+'.payload.id') for ch in ('aw','b','ar','r') if ch+'.payload.id' in signals]
    if ids and (len(ids)!=4 or len(set(ids))!=1 or not 1<=ids[0]<=8):
        raise ValueError('all four ID fields need the same width, at most 8 bits')
    if 'w.payload.id' in signals: raise ValueError('AXI3 WID is unsupported')
    for ch in ('aw','ar'):
        for key,expected in [('len',8),('size',3),('burst',2),('lock',1)]:
            if ch+'.payload.'+key in signals and width(ch+'.payload.'+key)!=expected:
                raise ValueError('non-AXI4 field width '+ch+'.'+key)
    for ch in ('b','r'):
        if ch+'.payload.resp' in signals and width(ch+'.payload.resp')!=2:
            raise ValueError('AXI response must have two bits')
    bits=ids[0] if ids else 0;count=1<<bits;ib=max(1,bits)
    for channel,response in [('aw','w'),('ar','r')]:
        if channel+'.payload.len' in signals and response+'.payload.last' not in signals:
            raise ValueError('burst transaction tracking requires LAST')
    n={}
    for channel in ('aw','w','b','ar','r'):
        n[channel+'f']=f"({net(channel+'.valid')} && {net(channel+'.ready')})"
    for channel in ('aw','ar'):
        n[channel+'id']=net(channel+'.payload.id',"1'b0")
        n[channel+'len']=net(channel+'.payload.len',"8'd0")
        n[channel+'lock']=net(channel+'.payload.lock',"1'b0")
    for channel in ('b','r'):
        n[channel+'id']=net(channel+'.payload.id',"1'b0")
        n[channel+'resp']=net(channel+'.payload.resp',"2'd0")
    n['wl']=net('w.payload.last',"1'b1");n['rl']=net('r.payload.last',"1'b1")
    text=f'''// Tracker depth is an instrumentation bound, not an AXI protocol limit.
localparam integer RVW_DEPTH={depth}, RVW_IDS={count};
wire rvw_arf={n['arf']},rvw_rf={n['rf']},rvw_awf={n['awf']},rvw_wf={n['wf']},rvw_bf={n['bf']};
wire [{ib-1}:0] rvw_arid={n['arid']},rvw_rid={n['rid']},rvw_awid={n['awid']},rvw_bid={n['bid']};
integer rvw_rc[0:RVW_IDS-1],rvw_rh[0:RVW_IDS-1],rvw_rt[0:RVW_IDS-1];
reg [7:0] rvw_rlen[0:RVW_IDS*RVW_DEPTH-1];
reg rvw_rlock[0:RVW_IDS*RVW_DEPTH-1];
reg [8:0] rvw_rbeat[0:RVW_IDS-1];
wire rvw_rpresent=rvw_rc[rvw_rid]>0 || (rvw_arf && rvw_arid==rvw_rid);
wire [7:0] rvw_read_len=rvw_rc[rvw_rid]>0 ? rvw_rlen[rvw_rid*RVW_DEPTH+rvw_rh[rvw_rid]] : {n['arlen']};
wire rvw_read_lock=rvw_rc[rvw_rid]>0 ? rvw_rlock[rvw_rid*RVW_DEPTH+rvw_rh[rvw_rid]] : {n['arlock']};
wire rvw_rpop=rvw_rf && {n['rl']};
integer rvw_ac=0,rvw_ah=0,rvw_at=0,rvw_wc=0,rvw_wh=0,rvw_wt=0;
reg [{ib-1}:0] rvw_aid[0:RVW_DEPTH-1];
reg [7:0] rvw_alen[0:RVW_DEPTH-1];
reg rvw_alock[0:RVW_DEPTH-1];
reg [8:0] rvw_wlen[0:RVW_DEPTH-1];
reg [8:0] rvw_wbeat=0;
integer rvw_bc[0:RVW_IDS-1],rvw_bh[0:RVW_IDS-1],rvw_bt[0:RVW_IDS-1];
reg rvw_block[0:RVW_IDS*RVW_DEPTH-1];
wire rvw_wp=rvw_wf && {n['wl']};
wire rvw_av=rvw_ac>0 || rvw_awf,rvw_wv=rvw_wc>0 || rvw_wp;
wire [{ib-1}:0] rvw_pair_id=rvw_ac>0 ? rvw_aid[rvw_ah] : rvw_awid;
wire [7:0] rvw_pair_len=rvw_ac>0 ? rvw_alen[rvw_ah] : {n['awlen']};
wire rvw_pair_lock=rvw_ac>0 ? rvw_alock[rvw_ah] : {n['awlock']};
wire [8:0] rvw_pair_beats=rvw_wc>0 ? rvw_wlen[rvw_wh] : rvw_wbeat+9'd1;
wire rvw_current_aw=rvw_ac>rvw_wc || (rvw_ac==rvw_wc && rvw_awf);
wire [7:0] rvw_current_len=rvw_ac>rvw_wc ? rvw_alen[(rvw_ah+rvw_wc)%RVW_DEPTH] : {n['awlen']};
wire rvw_pair=rvw_av && rvw_wv && (rvw_bc[rvw_pair_id]<RVW_DEPTH || (rvw_bf && rvw_bid==rvw_pair_id));
wire rvw_bpresent=rvw_bc[rvw_bid]>0 || (rvw_pair && rvw_pair_id==rvw_bid);
wire rvw_write_lock=rvw_bc[rvw_bid]>0 ? rvw_block[rvw_bid*RVW_DEPTH+rvw_bh[rvw_bid]] : rvw_pair_lock;
always @(posedge clk) begin
 if(reset) begin
  rvw_ac<=0;rvw_ah<=0;rvw_at<=0;rvw_wc<=0;rvw_wh<=0;rvw_wt<=0;rvw_wbeat<=0;
  for(integer i=0;i<RVW_IDS;i=i+1) begin
   rvw_rc[i]<=0;rvw_rh[i]<=0;rvw_rt[i]<=0;rvw_rbeat[i]<=0;
   rvw_bc[i]<=0;rvw_bh[i]<=0;rvw_bt[i]<=0;
  end
 end else begin
  assert(rvw_ac>=0 && rvw_ac<=RVW_DEPTH && rvw_wc>=0 && rvw_wc<=RVW_DEPTH);
  assert(rvw_ah>=0 && rvw_ah<RVW_DEPTH && rvw_at>=0 && rvw_at<RVW_DEPTH);
  assert(rvw_wh>=0 && rvw_wh<RVW_DEPTH && rvw_wt>=0 && rvw_wt<RVW_DEPTH);
  if({net('r.valid')}) begin
   assert(rvw_rpresent);
   assert({n['rl']} == (rvw_rbeat[rvw_rid]=={{1'b0,rvw_read_len}}));
   if({n['rresp']}==1) assert(rvw_read_lock);
  end
  if({net('b.valid')}) begin
   assert(rvw_bpresent);
   if({n['bresp']}==1) assert(rvw_write_lock);
  end
  if(rvw_current_aw) begin
   assert(rvw_wbeat<={{1'b0,rvw_current_len}});
   if({net('w.valid')}) assert({n['wl']} == (rvw_wbeat=={{1'b0,rvw_current_len}}));
  end
  if(rvw_pair) assert(rvw_pair_beats=={{1'b0,rvw_pair_len}}+9'd1);
  if(rvw_wf) begin
   assert(rvw_wbeat<256);
   if(!{n['wl']}) assert(rvw_wbeat<255);
   rvw_wbeat<={n['wl']} ? 0 : rvw_wbeat+1;
  end
  if(rvw_awf) begin
   assert(rvw_ac<RVW_DEPTH || rvw_pair);
   rvw_aid[rvw_at]<=rvw_awid;rvw_alen[rvw_at]<={n['awlen']};rvw_alock[rvw_at]<={n['awlock']};
   rvw_at<=rvw_at==RVW_DEPTH-1 ? 0 : rvw_at+1;
  end
  if(rvw_wp) begin
   assert(rvw_wc<RVW_DEPTH || rvw_pair);
   rvw_wlen[rvw_wt]<=rvw_wbeat+9'd1;rvw_wt<=rvw_wt==RVW_DEPTH-1 ? 0 : rvw_wt+1;
  end
  if(rvw_pair) begin rvw_ah<=rvw_ah==RVW_DEPTH-1 ? 0 : rvw_ah+1;rvw_wh<=rvw_wh==RVW_DEPTH-1 ? 0 : rvw_wh+1;end
  case({{rvw_awf,rvw_pair}})2'b10:rvw_ac<=rvw_ac+1;2'b01:rvw_ac<=rvw_ac-1;endcase
  case({{rvw_wp,rvw_pair}})2'b10:rvw_wc<=rvw_wc+1;2'b01:rvw_wc<=rvw_wc-1;endcase
  for(integer i=0;i<RVW_IDS;i=i+1) begin
   assert(rvw_rc[i]>=0 && rvw_rc[i]<=RVW_DEPTH && rvw_bc[i]>=0 && rvw_bc[i]<=RVW_DEPTH);
   assert(rvw_rh[i]>=0 && rvw_rh[i]<RVW_DEPTH && rvw_rt[i]>=0 && rvw_rt[i]<RVW_DEPTH);
   assert(rvw_bh[i]>=0 && rvw_bh[i]<RVW_DEPTH && rvw_bt[i]>=0 && rvw_bt[i]<RVW_DEPTH);
   if(rvw_arf && rvw_arid==i) begin
    assert(rvw_rc[i]<RVW_DEPTH || (rvw_rpop && rvw_rid==i));
    rvw_rlen[i*RVW_DEPTH+rvw_rt[i]]<={n['arlen']};rvw_rlock[i*RVW_DEPTH+rvw_rt[i]]<={n['arlock']};
    rvw_rt[i]<=rvw_rt[i]==RVW_DEPTH-1 ? 0 : rvw_rt[i]+1;
   end
   if(rvw_rpop && rvw_rid==i)rvw_rh[i]<=rvw_rh[i]==RVW_DEPTH-1 ? 0 : rvw_rh[i]+1;
   if(rvw_rf && rvw_rid==i)rvw_rbeat[i]<={n['rl']} ? 0 : rvw_rbeat[i]+1;
   case({{rvw_arf && rvw_arid==i,rvw_rpop && rvw_rid==i}})2'b10:rvw_rc[i]<=rvw_rc[i]+1;2'b01:rvw_rc[i]<=rvw_rc[i]-1;endcase
   if(rvw_pair && rvw_pair_id==i)begin
    rvw_block[i*RVW_DEPTH+rvw_bt[i]]<=rvw_pair_lock;rvw_bt[i]<=rvw_bt[i]==RVW_DEPTH-1 ? 0 : rvw_bt[i]+1;
   end
   if(rvw_bf && rvw_bid==i)rvw_bh[i]<=rvw_bh[i]==RVW_DEPTH-1 ? 0 : rvw_bh[i]+1;
   case({{rvw_pair && rvw_pair_id==i,rvw_bf && rvw_bid==i}})2'b10:rvw_bc[i]<=rvw_bc[i]+1;2'b01:rvw_bc[i]<=rvw_bc[i]-1;endcase
  end
 end
end
'''
    if kind=='axi4':
        maxsize=(data_width//8).bit_length()-1
        for ch in ('aw','ar'):
            addr=net(ch+'.payload.addr');size=net(ch+'.payload.size',str(maxsize))
            length=n[ch+'len'];burst=net(ch+'.payload.burst',"2'd1");lock=n[ch+'lock']
            cache=net(ch+'.payload.cache',"4'd0")
            aw=width(ch+'.payload.addr')
            text+=f'''wire [{aw}:0] rvw_{ch}_aligned={{1'b0,{addr}}} & ~(({aw+1}'d1 << {size})-1);
wire [{aw}:0] rvw_{ch}_end=rvw_{ch}_aligned+(({{1'b0,{length}}}+9'd1) << {size})-1;
wire [{aw}:0] rvw_{ch}_bytes=({{1'b0,{length}}}+9'd1) << {size};
always @(posedge clk) if(!reset && {net(ch+'.valid')}) begin
 assert({size}<={maxsize});
 if({burst}==1) assert((rvw_{ch}_end >> 12)==({addr} >> 12));
 if({lock}) begin
  assert({length}==0 || {length}==1 || {length}==3 || {length}==7 || {length}==15);
  assert(rvw_{ch}_bytes<=128);
  assert(({{1'b0,{addr}}} & (rvw_{ch}_bytes-1))==0);
  assert(({cache} & 4'd2)==0);
 end
end
'''
    if kind=='axi4':
        from .axi_strobes import render as render_strobes
        text+=render_strobes(signals,depth,max_beats)
    return text
