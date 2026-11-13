module axis_fifo(axis_if s, axis_if m);
  assign s.tready=!m.tvalid || m.tready;
  always @(posedge s.clk or negedge s.reset_n) begin
    if(!s.reset_n) begin m.tvalid<=0; m.tdata<=0; m.tkeep<=0; m.tstrb<=0; m.tlast<=0; m.tid<=0; m.tdest<=0; m.tuser<=0; end
    else if(s.tready) begin
      m.tvalid<=s.tvalid;
      if(s.tvalid) begin
        m.tdata<=s.tdata ^ ($test$plusargs("buggy") ? 32'h01010101 : 0);
        m.tkeep<=s.tkeep; m.tstrb<=s.tstrb; m.tlast<=s.tlast;
        m.tid<=s.tid; m.tdest<=s.tdest; m.tuser<=s.tuser;
      end
    end
  end
endmodule
