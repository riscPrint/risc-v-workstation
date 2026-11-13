"""Check accepted WSTRB history against paired AW burst geometry."""


def render(signals,depth,max_beats):
    data=signals['w.payload.data'][3];lanes=data//8;aw=signals['aw.payload.addr'][3]
    if 'w.payload.strb' in signals and signals['w.payload.strb'][3]!=lanes:
        raise ValueError('WSTRB width must equal write data byte width')
    def net(key,default): return key.replace('.','_') if key in signals else default
    length=net('aw.payload.len',"8'd0")
    size=net('aw.payload.size',str(lanes.bit_length()-1))
    burst=net('aw.payload.burst',"2'd1")
    strobe=net('w.payload.strb',f"{lanes}'d{(1<<lanes)-1}")
    return f'''reg [{aw-1}:0] rvw_ast_addr[0:RVW_DEPTH-1];
reg [2:0] rvw_ast_size[0:RVW_DEPTH-1];
reg [1:0] rvw_ast_burst[0:RVW_DEPTH-1];
reg [{lanes-1}:0] rvw_strobes[0:RVW_DEPTH*{max_beats}-1];
wire [{aw-1}:0] rvw_pair_addr=rvw_ac>0 ? rvw_ast_addr[rvw_ah] : aw_payload_addr;
wire [2:0] rvw_pair_size=rvw_ac>0 ? rvw_ast_size[rvw_ah] : {size};
wire [1:0] rvw_pair_burst=rvw_ac>0 ? rvw_ast_burst[rvw_ah] : {burst};
reg rvw_bad_strobe;
reg [63:0] rvw_byte_addr,rvw_beat_bytes,rvw_wrap_bytes;
reg [{lanes-1}:0] rvw_allowed_strobe,rvw_seen_strobe;
integer rvw_st_slot,rvw_start_lane,rvw_end_lane;
always @* begin
 rvw_bad_strobe=0;rvw_byte_addr=0;
 rvw_beat_bytes=64'd1 << rvw_pair_size;
 rvw_wrap_bytes=({{1'b0,rvw_pair_len}}+9'd1) << rvw_pair_size;
 rvw_st_slot=rvw_wc>0 ? rvw_wh : rvw_wt;
 rvw_start_lane=0;rvw_end_lane=0;rvw_allowed_strobe=0;rvw_seen_strobe=0;
 for(integer j=0;j<{max_beats};j=j+1) if(j<rvw_pair_beats) begin
  if(rvw_pair_burst==2) rvw_byte_addr=(rvw_pair_addr & ~(rvw_wrap_bytes-1)) | ((rvw_pair_addr+(j*rvw_beat_bytes)) & (rvw_wrap_bytes-1));
  else if(rvw_pair_burst==0 || j==0) rvw_byte_addr=rvw_pair_addr;
  else rvw_byte_addr=(rvw_pair_addr & ~(rvw_beat_bytes-1))+(j*rvw_beat_bytes);
  rvw_start_lane=rvw_byte_addr % {lanes};
  rvw_end_lane=((rvw_byte_addr & ~(rvw_beat_bytes-1)) % {lanes})+rvw_beat_bytes-1;
  rvw_allowed_strobe=({{{lanes}{{1'b1}}}} << rvw_start_lane) & ~({{{lanes}{{1'b1}}}} << (rvw_end_lane+1));
  rvw_seen_strobe=(rvw_wc==0 && j==rvw_wbeat) ? {strobe} : rvw_strobes[rvw_st_slot*{max_beats}+j];
  if((rvw_seen_strobe & ~rvw_allowed_strobe)!=0) rvw_bad_strobe=1;
 end
end
always @(posedge clk) if(!reset) begin
 if(rvw_awf) begin rvw_ast_addr[rvw_at]<=aw_payload_addr;rvw_ast_size[rvw_at]<={size};rvw_ast_burst[rvw_at]<={burst};end
 if(rvw_awf) assert({length}<{max_beats});
 if(rvw_wf) begin
  assert(rvw_wbeat<{max_beats});
  if(rvw_wbeat==0) assert(rvw_wc<RVW_DEPTH || rvw_pair);
  rvw_strobes[rvw_wt*{max_beats}+rvw_wbeat]<={strobe};
 end
 if(rvw_pair) assert(!rvw_bad_strobe);
end
'''
