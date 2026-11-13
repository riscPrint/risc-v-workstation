"""TileLink C release, D/E sink and B/C probe tracking."""


def render(signals,depth,max_size):
    beat_size=(signals['d.payload.data'][3]//8).bit_length()-1
    if type(depth) is not int or not 1<=depth<=64:raise ValueError('probe tracker depth must be in 1..64')
    def bits(key):return signals[key][3]
    sw=bits('a.payload.size');aw=bits('b.payload.address');src=bits('b.payload.source');sink=bits('d.payload.sink')
    text=f'''reg rvw_tl_release[0:RVW_TL_SOURCES-1];
reg [{sw-1}:0] rvw_tl_release_size[0:RVW_TL_SOURCES-1];
reg rvw_tl_sink[0:{(1<<sink)-1}];
wire rvw_tl_cf=c_valid && c_ready && rvw_tl_c_first;
wire rvw_tl_rel=c_payload_opcode==6 || c_payload_opcode==7;
wire rvw_tl_ack=c_payload_opcode==4 || c_payload_opcode==5;
wire rvw_tl_fresh_rel=!rvw_tl_release[d_payload_source] && c_valid && rvw_tl_c_first && rvw_tl_rel && c_payload_source==d_payload_source;
wire rvw_tl_alloc_sink=rvw_tl_df && rvw_tl_grant;
always @(posedge clk) begin
 if(reset) begin
  for(integer i=0;i<RVW_TL_SOURCES;i=i+1)rvw_tl_release[i]<=0;
  for(integer i=0;i<{1<<sink};i=i+1)rvw_tl_sink[i]<=0;
 end else begin
  if(c_valid) begin
   assert(c_payload_opcode>=4 && c_payload_opcode<=7);
   if(rvw_tl_rel)assert(c_payload_param<=2);else assert(c_payload_param<=5);
   assert(c_payload_size<={max_size} && c_payload_size>={beat_size});
   assert((c_payload_address & ((64'd1 << c_payload_size)-1))==0);
   if(c_payload_opcode==4 || c_payload_opcode==6)assert(!c_payload_corrupt);
  end
  if(rvw_tl_cf && rvw_tl_rel) begin
   assert(!rvw_tl_release[c_payload_source]);
   rvw_tl_release[c_payload_source]<=1;rvw_tl_release_size[c_payload_source]<=c_payload_size;
  end
  if(d_valid && rvw_tl_d_first && d_payload_opcode==6) begin
   assert(rvw_tl_release[d_payload_source] || rvw_tl_fresh_rel);
   assert(d_payload_size==(rvw_tl_fresh_rel ? c_payload_size : rvw_tl_release_size[d_payload_source]));
   if(rvw_tl_fresh_rel && d_ready)assert(c_ready);
  end
  if(rvw_tl_df && d_payload_opcode==6)rvw_tl_release[d_payload_source]<=0;
  if(rvw_tl_alloc_sink) begin assert(!rvw_tl_sink[d_payload_sink]);rvw_tl_sink[d_payload_sink]<=1;end
  if(e_valid)assert(rvw_tl_sink[e_payload_sink] || (rvw_tl_alloc_sink && e_payload_sink==d_payload_sink));
  if(e_valid && e_ready)rvw_tl_sink[e_payload_sink]<=0;
 end
end
// Multiple probes can use the same source at different addresses.
// Capacity is an instrumentation limit, not a TileLink protocol restriction.
reg rvw_tl_probe[0:{depth-1}];
reg [{src-1}:0] rvw_tl_probe_source[0:{depth-1}];
reg [{aw-1}:0] rvw_tl_probe_address[0:{depth-1}];
reg [{sw-1}:0] rvw_tl_probe_size[0:{depth-1}];
reg [2:0] rvw_tl_probe_cap[0:{depth-1}];
reg rvw_tl_probe_perm[0:{depth-1}];
integer rvw_tl_ci,rvw_tl_bi,rvw_tl_free;
wire rvw_tl_probe_same=b_valid && b_payload_source==c_payload_source && b_payload_address==c_payload_address;
wire rvw_tl_probe_retire=rvw_tl_cf && rvw_tl_ack && rvw_tl_ci>=0;
wire rvw_tl_probe_zero=rvw_tl_cf && rvw_tl_ack && rvw_tl_ci<0 && rvw_tl_probe_same;
wire [2:0] rvw_tl_cap_result=(c_payload_param==0 || c_payload_param==4) ? 1 : c_payload_param==3 ? 0 : 2;
always @* begin
 rvw_tl_ci=-1;rvw_tl_bi=-1;rvw_tl_free=-1;
 for(integer i=0;i<{depth};i=i+1)begin
  if(rvw_tl_probe[i] && rvw_tl_probe_source[i]==c_payload_source && rvw_tl_probe_address[i]==c_payload_address)rvw_tl_ci=i;
  if(rvw_tl_probe[i] && rvw_tl_probe_source[i]==b_payload_source && rvw_tl_probe_address[i]==b_payload_address)rvw_tl_bi=i;
 end
 for(integer i=0;i<{depth};i=i+1)if(!rvw_tl_probe[i] || (rvw_tl_probe_retire && rvw_tl_ci==i))rvw_tl_free=i;
end
always @(posedge clk) begin
 if(reset)for(integer i=0;i<{depth};i=i+1)rvw_tl_probe[i]<=0;
 else begin
  if(b_valid) begin
   assert(b_payload_opcode==6 || b_payload_opcode==7);assert(b_payload_param<=2);
   assert(b_payload_size<={max_size} && b_payload_size>={beat_size});assert((b_payload_address & ((64'd1 << b_payload_size)-1))==0);
  end
  if(c_valid && rvw_tl_c_first && rvw_tl_ack)begin
   assert(rvw_tl_ci>=0 || rvw_tl_probe_same);
   assert(c_payload_size==(rvw_tl_ci>=0 ? rvw_tl_probe_size[rvw_tl_ci] : b_payload_size));
   assert(rvw_tl_cap_result>=(rvw_tl_ci>=0 ? rvw_tl_probe_cap[rvw_tl_ci] : b_payload_param));
   if(rvw_tl_ci>=0 ? rvw_tl_probe_perm[rvw_tl_ci] : b_payload_opcode==7)assert(c_payload_opcode==4);
   if(rvw_tl_ci<0 && rvw_tl_probe_same && c_ready)assert(b_ready);
  end
  if(rvw_tl_probe_retire)rvw_tl_probe[rvw_tl_ci]<=0;
  if(b_valid && b_ready)begin
   assert(rvw_tl_bi<0 || (rvw_tl_probe_retire && rvw_tl_bi==rvw_tl_ci));
   if(!rvw_tl_probe_zero)begin
    assert(rvw_tl_free>=0);
    rvw_tl_probe[rvw_tl_free]<=1;rvw_tl_probe_source[rvw_tl_free]<=b_payload_source;
    rvw_tl_probe_address[rvw_tl_free]<=b_payload_address;rvw_tl_probe_size[rvw_tl_free]<=b_payload_size;
    rvw_tl_probe_cap[rvw_tl_free]<=b_payload_param;rvw_tl_probe_perm[rvw_tl_free]<=b_payload_opcode==7;
   end
  end
 end
end
'''

    if 'b.payload.corrupt' in signals:
        text+='always @(posedge clk) if(!reset && b_valid) assert(!b_payload_corrupt);\n'
    return text
