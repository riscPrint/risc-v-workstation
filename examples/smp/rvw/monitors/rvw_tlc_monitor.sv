module rvw_tlc_message_monitor(
  input wire clock,
  input wire reset,
  input wire [511:0] expected_data,
  input wire [0:0] c0_a_valid,
  input wire [0:0] c0_a_ready,
  input wire [2:0] c0_a_opcode,
  input wire [2:0] c0_a_param,
  input wire [0:0] c0_a_source,
  input wire [31:0] c0_a_address,
  input wire [2:0] c0_a_size,
  input wire [0:0] c0_b_valid,
  input wire [0:0] c0_b_ready,
  input wire [2:0] c0_b_opcode,
  input wire [2:0] c0_b_param,
  input wire [0:0] c0_b_source,
  input wire [31:0] c0_b_address,
  input wire [2:0] c0_b_size,
  input wire [0:0] c0_c_valid,
  input wire [0:0] c0_c_ready,
  input wire [2:0] c0_c_opcode,
  input wire [2:0] c0_c_param,
  input wire [0:0] c0_c_source,
  input wire [511:0] c0_c_data,
  input wire [31:0] c0_c_address,
  input wire [2:0] c0_c_size,
  input wire [0:0] c0_c_corrupt,
  input wire [0:0] c0_d_valid,
  input wire [0:0] c0_d_ready,
  input wire [2:0] c0_d_opcode,
  input wire [2:0] c0_d_param,
  input wire [0:0] c0_d_source,
  input wire [8:0] c0_d_sink,
  input wire [511:0] c0_d_data,
  input wire [2:0] c0_d_size,
  input wire [0:0] c0_d_denied,
  input wire [0:0] c0_d_corrupt,
  input wire [0:0] c0_e_valid,
  input wire [0:0] c0_e_ready,
  input wire [8:0] c0_e_sink,
  input wire [0:0] c1_a_valid,
  input wire [0:0] c1_a_ready,
  input wire [2:0] c1_a_opcode,
  input wire [2:0] c1_a_param,
  input wire [0:0] c1_a_source,
  input wire [31:0] c1_a_address,
  input wire [2:0] c1_a_size,
  input wire [0:0] c1_b_valid,
  input wire [0:0] c1_b_ready,
  input wire [2:0] c1_b_opcode,
  input wire [2:0] c1_b_param,
  input wire [0:0] c1_b_source,
  input wire [31:0] c1_b_address,
  input wire [2:0] c1_b_size,
  input wire [0:0] c1_c_valid,
  input wire [0:0] c1_c_ready,
  input wire [2:0] c1_c_opcode,
  input wire [2:0] c1_c_param,
  input wire [0:0] c1_c_source,
  input wire [511:0] c1_c_data,
  input wire [31:0] c1_c_address,
  input wire [2:0] c1_c_size,
  input wire [0:0] c1_c_corrupt,
  input wire [0:0] c1_d_valid,
  input wire [0:0] c1_d_ready,
  input wire [2:0] c1_d_opcode,
  input wire [2:0] c1_d_param,
  input wire [0:0] c1_d_source,
  input wire [8:0] c1_d_sink,
  input wire [511:0] c1_d_data,
  input wire [2:0] c1_d_size,
  input wire [0:0] c1_d_denied,
  input wire [0:0] c1_d_corrupt,
  input wire [0:0] c1_e_valid,
  input wire [0:0] c1_e_ready,
  input wire [8:0] c1_e_sink
);
integer permission[0:1];
reg acquire[0:1][0:1];
reg release_pending[0:1][0:1];
reg grant[0:1][0:511];
integer acquire_age[0:1][0:1];
integer grant_age[0:1][0:511];
reg probe[0:1];
integer probe_source[0:1];
integer probe_cap[0:1];
integer probe_age[0:1];
integer i,j,next_permission;
integer why;
integer projection_previous;
reg bad;
reg reset_seen = 0;
always @(posedge clock or posedge reset) begin
  bad = 0; why = 0;
  if (reset) begin
    projection_previous=0;
    reset_seen = 1;
    for(i=0;i<2;i=i+1) begin
      permission[i]=0; probe[i]=0; probe_age[i]=0;
      for(j=0;j<2;j=j+1) begin
        acquire[i][j]=0; release_pending[i][j]=0; acquire_age[i][j]=0;
      end
      for(j=0;j<512;j=j+1) begin grant[i][j]=0; grant_age[i][j]=0; end
    end
  end else if(!reset_seen) begin
    if($realtime>0) $fatal(1,"rvw TL-C monitor requires reset before clocks");
  end else begin
    for(i=0;i<2;i=i+1) begin
      if(probe[i]) begin probe_age[i]=probe_age[i]+1; if(probe_age[i]>10000) begin bad=1; if(why==0) why=1; end end
      for(j=0;j<2;j=j+1) if(acquire[i][j] || release_pending[i][j]) begin
        acquire_age[i][j]=acquire_age[i][j]+1; if(acquire_age[i][j]>10000) begin bad=1; if(why==0) why=2; end
      end
      for(j=0;j<512;j=j+1) if(grant[i][j]) begin
        grant_age[i][j]=grant_age[i][j]+1; if(grant_age[i][j]>10000) begin bad=1; if(why==0) why=3; end
      end
    end
    if(c0_a_valid && c0_a_ready) begin
      if(c0_a_size!=6) begin bad=1; if(why==0) why=4; end
      if((c0_a_param==0 || c0_a_param==1) && permission[0]!=0) begin bad=1; if(why==0) why=5; end
      if(c0_a_param==2 && permission[0]!=1) begin bad=1; if(why==0) why=6; end
      if(c0_a_param>2) begin bad=1; if(why==0) why=7; end
      if((c0_a_opcode!=6 && c0_a_opcode!=7) || c0_a_address!=32'h80080000) begin bad=1; if(why==0) why=8; end
      if(acquire[0][c0_a_source] || release_pending[0][c0_a_source]) begin bad=1; if(why==0) why=9; end
      acquire[0][c0_a_source]=1; acquire_age[0][c0_a_source]=0;
    end
    if(c0_b_valid && c0_b_ready) begin
      if(c0_b_address!=32'h80080000 || c0_b_size!=6) begin bad=1; if(why==0) why=10; end
      if((c0_b_opcode!=6 && c0_b_opcode!=7) || probe[0] || c0_b_param>2) begin bad=1; if(why==0) why=11; end
      probe[0]=1; probe_source[0]=c0_b_source; probe_cap[0]=c0_b_param; probe_age[0]=0;
    end
    if(c1_a_valid && c1_a_ready) begin
      if(c1_a_size!=6) begin bad=1; if(why==0) why=12; end
      if((c1_a_param==0 || c1_a_param==1) && permission[1]!=0) begin bad=1; if(why==0) why=13; end
      if(c1_a_param==2 && permission[1]!=1) begin bad=1; if(why==0) why=14; end
      if(c1_a_param>2) begin bad=1; if(why==0) why=15; end
      if((c1_a_opcode!=6 && c1_a_opcode!=7) || c1_a_address!=32'h80080000) begin bad=1; if(why==0) why=16; end
      if(acquire[1][c1_a_source] || release_pending[1][c1_a_source]) begin bad=1; if(why==0) why=17; end
      acquire[1][c1_a_source]=1; acquire_age[1][c1_a_source]=0;
    end
    if(c1_b_valid && c1_b_ready) begin
      if(c1_b_address!=32'h80080000 || c1_b_size!=6) begin bad=1; if(why==0) why=18; end
      if((c1_b_opcode!=6 && c1_b_opcode!=7) || probe[1] || c1_b_param>2) begin bad=1; if(why==0) why=19; end
      probe[1]=1; probe_source[1]=c1_b_source; probe_cap[1]=c1_b_param; probe_age[1]=0;
    end
    if(c0_c_valid && c0_c_ready) begin
      if(c0_c_address!=32'h80080000 || c0_c_size!=6 || c0_c_corrupt) begin bad=1; if(why==0) why=20; end
      if(c0_c_opcode<4 || c0_c_opcode>7) begin bad=1; if(why==0) why=21; end
      case(c0_c_param)
        0: begin if(permission[0]!=2) begin bad=1; if(why==0) why=22; end next_permission=1; end
        1: begin if(permission[0]!=2) begin bad=1; if(why==0) why=23; end next_permission=0; end
        2: begin if(permission[0]!=1) begin bad=1; if(why==0) why=24; end next_permission=0; end
        3: begin if(permission[0]!=2) begin bad=1; if(why==0) why=25; end next_permission=2; end
        4: begin if(permission[0]!=1) begin bad=1; if(why==0) why=26; end next_permission=1; end
        5: begin if(permission[0]!=0) begin bad=1; if(why==0) why=27; end next_permission=0; end
        default: begin next_permission=0; begin bad=1; if(why==0) why=28; end end
      endcase
      if(1 && permission[0]==2 && next_permission<2 && !c0_c_opcode[0]) begin bad=1; if(why==0) why=29; end
      if(c0_c_opcode[0] && c0_c_data!=expected_data) begin bad=1; if(why==0) why=30; end
      if(c0_c_opcode==4 || c0_c_opcode==5) begin
        if(!probe[0] || probe_source[0]!=c0_c_source) begin bad=1; if(why==0) why=31; end
        if((probe_cap[0]==2 && next_permission!=0) || (probe_cap[0]==1 && next_permission>1)) begin bad=1; if(why==0) why=32; end
        probe[0]=0;
      end else begin
        if(release_pending[0][c0_c_source] || acquire[0][c0_c_source]) begin bad=1; if(why==0) why=33; end
        release_pending[0][c0_c_source]=1; acquire_age[0][c0_c_source]=0;
      end
      permission[0]=next_permission;
    end
    if(c1_c_valid && c1_c_ready) begin
      if(c1_c_address!=32'h80080000 || c1_c_size!=6 || c1_c_corrupt) begin bad=1; if(why==0) why=34; end
      if(c1_c_opcode<4 || c1_c_opcode>7) begin bad=1; if(why==0) why=35; end
      case(c1_c_param)
        0: begin if(permission[1]!=2) begin bad=1; if(why==0) why=36; end next_permission=1; end
        1: begin if(permission[1]!=2) begin bad=1; if(why==0) why=37; end next_permission=0; end
        2: begin if(permission[1]!=1) begin bad=1; if(why==0) why=38; end next_permission=0; end
        3: begin if(permission[1]!=2) begin bad=1; if(why==0) why=39; end next_permission=2; end
        4: begin if(permission[1]!=1) begin bad=1; if(why==0) why=40; end next_permission=1; end
        5: begin if(permission[1]!=0) begin bad=1; if(why==0) why=41; end next_permission=0; end
        default: begin next_permission=0; begin bad=1; if(why==0) why=42; end end
      endcase
      if(1 && permission[1]==2 && next_permission<2 && !c1_c_opcode[0]) begin bad=1; if(why==0) why=43; end
      if(c1_c_opcode[0] && c1_c_data!=expected_data) begin bad=1; if(why==0) why=44; end
      if(c1_c_opcode==4 || c1_c_opcode==5) begin
        if(!probe[1] || probe_source[1]!=c1_c_source) begin bad=1; if(why==0) why=45; end
        if((probe_cap[1]==2 && next_permission!=0) || (probe_cap[1]==1 && next_permission>1)) begin bad=1; if(why==0) why=46; end
        probe[1]=0;
      end else begin
        if(release_pending[1][c1_c_source] || acquire[1][c1_c_source]) begin bad=1; if(why==0) why=47; end
        release_pending[1][c1_c_source]=1; acquire_age[1][c1_c_source]=0;
      end
      permission[1]=next_permission;
    end
    if(c0_d_valid && c0_d_ready) begin
      if(c0_d_size!=6 || c0_d_denied || c0_d_corrupt) begin bad=1; if(why==0) why=48; end
      if(c0_d_opcode==4 || c0_d_opcode==5) begin
        if(!acquire[0][c0_d_source] || grant[0][c0_d_sink] || c0_d_param>1) begin bad=1; if(why==0) why=49; end
        next_permission=(c0_d_param==0)?2:1;
        if((next_permission==2 && permission[1]!=0) || (next_permission==1 && permission[1]==2)) begin bad=1; if(why==0) why=50; end
        if(c0_d_opcode==5 && c0_d_data!=expected_data) begin bad=1; if(why==0) why=51; end
        permission[0]=next_permission; acquire[0][c0_d_source]=0;
        grant[0][c0_d_sink]=1; grant_age[0][c0_d_sink]=0;
      end else if(c0_d_opcode==6) begin
        if(!release_pending[0][c0_d_source]) begin bad=1; if(why==0) why=52; end
        release_pending[0][c0_d_source]=0;
      end else begin bad=1; if(why==0) why=53; end
    end
    if(c1_d_valid && c1_d_ready) begin
      if(c1_d_size!=6 || c1_d_denied || c1_d_corrupt) begin bad=1; if(why==0) why=54; end
      if(c1_d_opcode==4 || c1_d_opcode==5) begin
        if(!acquire[1][c1_d_source] || grant[1][c1_d_sink] || c1_d_param>1) begin bad=1; if(why==0) why=55; end
        next_permission=(c1_d_param==0)?2:1;
        if((next_permission==2 && permission[0]!=0) || (next_permission==1 && permission[0]==2)) begin bad=1; if(why==0) why=56; end
        if(c1_d_opcode==5 && c1_d_data!=expected_data) begin bad=1; if(why==0) why=57; end
        permission[1]=next_permission; acquire[1][c1_d_source]=0;
        grant[1][c1_d_sink]=1; grant_age[1][c1_d_sink]=0;
      end else if(c1_d_opcode==6) begin
        if(!release_pending[1][c1_d_source]) begin bad=1; if(why==0) why=58; end
        release_pending[1][c1_d_source]=0;
      end else begin bad=1; if(why==0) why=59; end
    end
    if(c0_e_valid && c0_e_ready) begin
      if(!grant[0][c0_e_sink]) begin bad=1; if(why==0) why=60; end
      grant[0][c0_e_sink]=0;
    end
    if(c1_e_valid && c1_e_ready) begin
      if(!grant[1][c1_e_sink]) begin bad=1; if(why==0) why=61; end
      grant[1][c1_e_sink]=0;
    end
    // Generated finite permission projection; channel/data checks remain separate.
    if(!((projection_previous==0 && (permission[0]+3*permission[1])==0) || (projection_previous==0 && (permission[0]+3*permission[1])==3) || (projection_previous==0 && (permission[0]+3*permission[1])==6) || (projection_previous==0 && (permission[0]+3*permission[1])==1) || (projection_previous==0 && (permission[0]+3*permission[1])==4) || (projection_previous==0 && (permission[0]+3*permission[1])==2) || (projection_previous==3 && (permission[0]+3*permission[1])==0) || (projection_previous==3 && (permission[0]+3*permission[1])==3) || (projection_previous==3 && (permission[0]+3*permission[1])==6) || (projection_previous==3 && (permission[0]+3*permission[1])==1) || (projection_previous==3 && (permission[0]+3*permission[1])==4) || (projection_previous==3 && (permission[0]+3*permission[1])==2) || (projection_previous==6 && (permission[0]+3*permission[1])==0) || (projection_previous==6 && (permission[0]+3*permission[1])==3) || (projection_previous==6 && (permission[0]+3*permission[1])==6) || (projection_previous==6 && (permission[0]+3*permission[1])==1) || (projection_previous==6 && (permission[0]+3*permission[1])==4) || (projection_previous==6 && (permission[0]+3*permission[1])==2) || (projection_previous==1 && (permission[0]+3*permission[1])==0) || (projection_previous==1 && (permission[0]+3*permission[1])==3) || (projection_previous==1 && (permission[0]+3*permission[1])==6) || (projection_previous==1 && (permission[0]+3*permission[1])==1) || (projection_previous==1 && (permission[0]+3*permission[1])==4) || (projection_previous==1 && (permission[0]+3*permission[1])==2) || (projection_previous==4 && (permission[0]+3*permission[1])==0) || (projection_previous==4 && (permission[0]+3*permission[1])==3) || (projection_previous==4 && (permission[0]+3*permission[1])==6) || (projection_previous==4 && (permission[0]+3*permission[1])==1) || (projection_previous==4 && (permission[0]+3*permission[1])==4) || (projection_previous==4 && (permission[0]+3*permission[1])==2) || (projection_previous==2 && (permission[0]+3*permission[1])==0) || (projection_previous==2 && (permission[0]+3*permission[1])==3) || (projection_previous==2 && (permission[0]+3*permission[1])==6) || (projection_previous==2 && (permission[0]+3*permission[1])==1) || (projection_previous==2 && (permission[0]+3*permission[1])==4) || (projection_previous==2 && (permission[0]+3*permission[1])==2))) begin bad=1; if(why==0) why=62; end
    projection_previous=permission[0]+3*permission[1];
    if(bad) $fatal(1,"rvw TL-C monitor violation code=%0d state=%0d,%0d reset=%0d",why,permission[0],permission[1],reset);
  end
end
endmodule

module rvw_tlc_monitor(
  input wire clock,
  input wire reset,
  input wire [511:0] expected_data,
  input wire [0:0] c0_a_valid,
  input wire [0:0] c0_a_ready,
  input wire [2:0] c0_a_opcode,
  input wire [2:0] c0_a_param,
  input wire [0:0] c0_a_source,
  input wire [31:0] c0_a_address,
  input wire [2:0] c0_a_size,
  input wire [0:0] c0_b_valid,
  input wire [0:0] c0_b_ready,
  input wire [2:0] c0_b_opcode,
  input wire [2:0] c0_b_param,
  input wire [0:0] c0_b_source,
  input wire [31:0] c0_b_address,
  input wire [2:0] c0_b_size,
  input wire [0:0] c0_c_valid,
  input wire [0:0] c0_c_ready,
  input wire [2:0] c0_c_opcode,
  input wire [2:0] c0_c_param,
  input wire [0:0] c0_c_source,
  input wire [63:0] c0_c_data,
  input wire [31:0] c0_c_address,
  input wire [2:0] c0_c_size,
  input wire [0:0] c0_c_corrupt,
  input wire [0:0] c0_d_valid,
  input wire [0:0] c0_d_ready,
  input wire [2:0] c0_d_opcode,
  input wire [2:0] c0_d_param,
  input wire [0:0] c0_d_source,
  input wire [8:0] c0_d_sink,
  input wire [63:0] c0_d_data,
  input wire [2:0] c0_d_size,
  input wire [0:0] c0_d_denied,
  input wire [0:0] c0_d_corrupt,
  input wire [0:0] c0_e_valid,
  input wire [0:0] c0_e_ready,
  input wire [8:0] c0_e_sink,
  input wire [0:0] c1_a_valid,
  input wire [0:0] c1_a_ready,
  input wire [2:0] c1_a_opcode,
  input wire [2:0] c1_a_param,
  input wire [0:0] c1_a_source,
  input wire [31:0] c1_a_address,
  input wire [2:0] c1_a_size,
  input wire [0:0] c1_b_valid,
  input wire [0:0] c1_b_ready,
  input wire [2:0] c1_b_opcode,
  input wire [2:0] c1_b_param,
  input wire [0:0] c1_b_source,
  input wire [31:0] c1_b_address,
  input wire [2:0] c1_b_size,
  input wire [0:0] c1_c_valid,
  input wire [0:0] c1_c_ready,
  input wire [2:0] c1_c_opcode,
  input wire [2:0] c1_c_param,
  input wire [0:0] c1_c_source,
  input wire [63:0] c1_c_data,
  input wire [31:0] c1_c_address,
  input wire [2:0] c1_c_size,
  input wire [0:0] c1_c_corrupt,
  input wire [0:0] c1_d_valid,
  input wire [0:0] c1_d_ready,
  input wire [2:0] c1_d_opcode,
  input wire [2:0] c1_d_param,
  input wire [0:0] c1_d_source,
  input wire [8:0] c1_d_sink,
  input wire [63:0] c1_d_data,
  input wire [2:0] c1_d_size,
  input wire [0:0] c1_d_denied,
  input wire [0:0] c1_d_corrupt,
  input wire [0:0] c1_e_valid,
  input wire [0:0] c1_e_ready,
  input wire [8:0] c1_e_sink
);
reg c0_c_reset_seen = 0;
integer c0_c_count;
integer c0_c_age;
reg [511:0] c0_c_buffer;
reg [511:0] c0_c_full;
reg [42:0] c0_c_header;
wire c0_c_last = !(c0_c_opcode[0]) || c0_c_count==7;
always @* begin
  c0_c_full=c0_c_buffer;
  c0_c_full[c0_c_count*64 +: 64]=c0_c_data;
end
always @(posedge clock or posedge reset) begin
  if(reset) begin
    c0_c_reset_seen<=1;
    c0_c_count<=0; c0_c_age<=0; c0_c_buffer<=0; c0_c_header<=0;
  end else if(!c0_c_reset_seen) begin
    if($realtime>0) $fatal(1,"rvw TL-C collector requires reset before clocks");
  end else begin
    if(c0_c_count!=0) begin
      c0_c_age<=c0_c_age+1;
      if(c0_c_age>=10000) $fatal(1,"rvw TL-C incomplete data message");
    end
    if(c0_c_valid && c0_c_ready) begin
      if(c0_c_corrupt) $fatal(1,"rvw TL-C data error outside success profile");
      if(c0_c_count==0) c0_c_header<={c0_c_opcode,c0_c_param,c0_c_source,c0_c_address,c0_c_size,c0_c_corrupt};
      else if(c0_c_header!={c0_c_opcode,c0_c_param,c0_c_source,c0_c_address,c0_c_size,c0_c_corrupt}) $fatal(1,"rvw TL-C data message header changed");
      c0_c_buffer<=c0_c_full;
      if(c0_c_last) begin c0_c_count<=0; c0_c_age<=0; end
      else begin
        c0_c_count<=c0_c_count+1;
        if(c0_c_count==0) c0_c_age<=0;
      end
    end
  end
end
reg c0_d_reset_seen = 0;
integer c0_d_count;
integer c0_d_age;
reg [511:0] c0_d_buffer;
reg [511:0] c0_d_full;
reg [20:0] c0_d_header;
wire c0_d_last = !((c0_d_opcode==5)) || c0_d_count==7;
always @* begin
  c0_d_full=c0_d_buffer;
  c0_d_full[c0_d_count*64 +: 64]=c0_d_data;
end
always @(posedge clock or posedge reset) begin
  if(reset) begin
    c0_d_reset_seen<=1;
    c0_d_count<=0; c0_d_age<=0; c0_d_buffer<=0; c0_d_header<=0;
  end else if(!c0_d_reset_seen) begin
    if($realtime>0) $fatal(1,"rvw TL-C collector requires reset before clocks");
  end else begin
    if(c0_d_count!=0) begin
      c0_d_age<=c0_d_age+1;
      if(c0_d_age>=10000) $fatal(1,"rvw TL-C incomplete data message");
    end
    if(c0_d_valid && c0_d_ready) begin
      if((c0_d_corrupt || c0_d_denied)) $fatal(1,"rvw TL-C data error outside success profile");
      if(c0_d_count==0) c0_d_header<={c0_d_opcode,c0_d_param,c0_d_source,c0_d_sink,c0_d_size,c0_d_denied,c0_d_corrupt};
      else if(c0_d_header!={c0_d_opcode,c0_d_param,c0_d_source,c0_d_sink,c0_d_size,c0_d_denied,c0_d_corrupt}) $fatal(1,"rvw TL-C data message header changed");
      c0_d_buffer<=c0_d_full;
      if(c0_d_last) begin c0_d_count<=0; c0_d_age<=0; end
      else begin
        c0_d_count<=c0_d_count+1;
        if(c0_d_count==0) c0_d_age<=0;
      end
    end
  end
end
reg c1_c_reset_seen = 0;
integer c1_c_count;
integer c1_c_age;
reg [511:0] c1_c_buffer;
reg [511:0] c1_c_full;
reg [42:0] c1_c_header;
wire c1_c_last = !(c1_c_opcode[0]) || c1_c_count==7;
always @* begin
  c1_c_full=c1_c_buffer;
  c1_c_full[c1_c_count*64 +: 64]=c1_c_data;
end
always @(posedge clock or posedge reset) begin
  if(reset) begin
    c1_c_reset_seen<=1;
    c1_c_count<=0; c1_c_age<=0; c1_c_buffer<=0; c1_c_header<=0;
  end else if(!c1_c_reset_seen) begin
    if($realtime>0) $fatal(1,"rvw TL-C collector requires reset before clocks");
  end else begin
    if(c1_c_count!=0) begin
      c1_c_age<=c1_c_age+1;
      if(c1_c_age>=10000) $fatal(1,"rvw TL-C incomplete data message");
    end
    if(c1_c_valid && c1_c_ready) begin
      if(c1_c_corrupt) $fatal(1,"rvw TL-C data error outside success profile");
      if(c1_c_count==0) c1_c_header<={c1_c_opcode,c1_c_param,c1_c_source,c1_c_address,c1_c_size,c1_c_corrupt};
      else if(c1_c_header!={c1_c_opcode,c1_c_param,c1_c_source,c1_c_address,c1_c_size,c1_c_corrupt}) $fatal(1,"rvw TL-C data message header changed");
      c1_c_buffer<=c1_c_full;
      if(c1_c_last) begin c1_c_count<=0; c1_c_age<=0; end
      else begin
        c1_c_count<=c1_c_count+1;
        if(c1_c_count==0) c1_c_age<=0;
      end
    end
  end
end
reg c1_d_reset_seen = 0;
integer c1_d_count;
integer c1_d_age;
reg [511:0] c1_d_buffer;
reg [511:0] c1_d_full;
reg [20:0] c1_d_header;
wire c1_d_last = !((c1_d_opcode==5)) || c1_d_count==7;
always @* begin
  c1_d_full=c1_d_buffer;
  c1_d_full[c1_d_count*64 +: 64]=c1_d_data;
end
always @(posedge clock or posedge reset) begin
  if(reset) begin
    c1_d_reset_seen<=1;
    c1_d_count<=0; c1_d_age<=0; c1_d_buffer<=0; c1_d_header<=0;
  end else if(!c1_d_reset_seen) begin
    if($realtime>0) $fatal(1,"rvw TL-C collector requires reset before clocks");
  end else begin
    if(c1_d_count!=0) begin
      c1_d_age<=c1_d_age+1;
      if(c1_d_age>=10000) $fatal(1,"rvw TL-C incomplete data message");
    end
    if(c1_d_valid && c1_d_ready) begin
      if((c1_d_corrupt || c1_d_denied)) $fatal(1,"rvw TL-C data error outside success profile");
      if(c1_d_count==0) c1_d_header<={c1_d_opcode,c1_d_param,c1_d_source,c1_d_sink,c1_d_size,c1_d_denied,c1_d_corrupt};
      else if(c1_d_header!={c1_d_opcode,c1_d_param,c1_d_source,c1_d_sink,c1_d_size,c1_d_denied,c1_d_corrupt}) $fatal(1,"rvw TL-C data message header changed");
      c1_d_buffer<=c1_d_full;
      if(c1_d_last) begin c1_d_count<=0; c1_d_age<=0; end
      else begin
        c1_d_count<=c1_d_count+1;
        if(c1_d_count==0) c1_d_age<=0;
      end
    end
  end
end

rvw_tlc_message_monitor complete_messages(
  .clock(clock),
  .reset(reset),
  .expected_data(expected_data),
  .c0_a_valid(c0_a_valid),
  .c0_a_ready(c0_a_ready),
  .c0_a_opcode(c0_a_opcode),
  .c0_a_param(c0_a_param),
  .c0_a_source(c0_a_source),
  .c0_a_address(c0_a_address),
  .c0_a_size(c0_a_size),
  .c0_b_valid(c0_b_valid),
  .c0_b_ready(c0_b_ready),
  .c0_b_opcode(c0_b_opcode),
  .c0_b_param(c0_b_param),
  .c0_b_source(c0_b_source),
  .c0_b_address(c0_b_address),
  .c0_b_size(c0_b_size),
  .c0_c_valid(c0_c_valid && c0_c_last),
  .c0_c_ready(c0_c_ready),
  .c0_c_opcode(c0_c_opcode),
  .c0_c_param(c0_c_param),
  .c0_c_source(c0_c_source),
  .c0_c_data(c0_c_full),
  .c0_c_address(c0_c_address),
  .c0_c_size(c0_c_size),
  .c0_c_corrupt(c0_c_corrupt),
  .c0_d_valid(c0_d_valid && c0_d_last),
  .c0_d_ready(c0_d_ready),
  .c0_d_opcode(c0_d_opcode),
  .c0_d_param(c0_d_param),
  .c0_d_source(c0_d_source),
  .c0_d_sink(c0_d_sink),
  .c0_d_data(c0_d_full),
  .c0_d_size(c0_d_size),
  .c0_d_denied(c0_d_denied),
  .c0_d_corrupt(c0_d_corrupt),
  .c0_e_valid(c0_e_valid),
  .c0_e_ready(c0_e_ready),
  .c0_e_sink(c0_e_sink),
  .c1_a_valid(c1_a_valid),
  .c1_a_ready(c1_a_ready),
  .c1_a_opcode(c1_a_opcode),
  .c1_a_param(c1_a_param),
  .c1_a_source(c1_a_source),
  .c1_a_address(c1_a_address),
  .c1_a_size(c1_a_size),
  .c1_b_valid(c1_b_valid),
  .c1_b_ready(c1_b_ready),
  .c1_b_opcode(c1_b_opcode),
  .c1_b_param(c1_b_param),
  .c1_b_source(c1_b_source),
  .c1_b_address(c1_b_address),
  .c1_b_size(c1_b_size),
  .c1_c_valid(c1_c_valid && c1_c_last),
  .c1_c_ready(c1_c_ready),
  .c1_c_opcode(c1_c_opcode),
  .c1_c_param(c1_c_param),
  .c1_c_source(c1_c_source),
  .c1_c_data(c1_c_full),
  .c1_c_address(c1_c_address),
  .c1_c_size(c1_c_size),
  .c1_c_corrupt(c1_c_corrupt),
  .c1_d_valid(c1_d_valid && c1_d_last),
  .c1_d_ready(c1_d_ready),
  .c1_d_opcode(c1_d_opcode),
  .c1_d_param(c1_d_param),
  .c1_d_source(c1_d_source),
  .c1_d_sink(c1_d_sink),
  .c1_d_data(c1_d_full),
  .c1_d_size(c1_d_size),
  .c1_d_denied(c1_d_denied),
  .c1_d_corrupt(c1_d_corrupt),
  .c1_e_valid(c1_e_valid),
  .c1_e_ready(c1_e_ready),
  .c1_e_sink(c1_e_sink)
);
endmodule
