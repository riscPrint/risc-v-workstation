module cocotb_top(
  input logic clk, reset_n,
  input logic s_tvalid,
  output logic s_tready,
  input logic [31:0] s_tdata,
  input logic [3:0] s_tkeep,
  input logic [3:0] s_tstrb,
  input logic s_tlast,
  input logic [1:0] s_tid,
  input logic [1:0] s_tdest,
  input logic [3:0] s_tuser,
  output logic m_tvalid,
  input logic m_tready,
  output logic [31:0] m_tdata,
  output logic [3:0] m_tkeep,
  output logic [3:0] m_tstrb,
  output logic m_tlast,
  output logic [1:0] m_tid,
  output logic [1:0] m_tdest,
  output logic [3:0] m_tuser
);
axis_if s(clk),m(clk);
assign s.reset_n=reset_n;
assign m.reset_n=reset_n;
assign s.tvalid=s_tvalid;
assign s_tready=s.tready;
assign s.tdata=s_tdata;
assign s.tkeep=s_tkeep;
assign s.tstrb=s_tstrb;
assign s.tlast=s_tlast;
assign s.tid=s_tid;
assign s.tdest=s_tdest;
assign s.tuser=s_tuser;
assign m_tvalid=m.tvalid;
assign m.tready=m_tready;
assign m_tdata=m.tdata;
assign m_tkeep=m.tkeep;
assign m_tstrb=m.tstrb;
assign m_tlast=m.tlast;
assign m_tid=m.tid;
assign m_tdest=m.tdest;
assign m_tuser=m.tuser;
axis_fifo dut(s,m);
endmodule
