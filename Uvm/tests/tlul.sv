interface tl_if(input bit clk);
  bit reset=1;
  bit a_valid, a_ready, d_valid, d_ready=1;
  bit [2:0] a_opcode, d_opcode;
  bit [3:0] a_mask=15;
  bit [1:0] a_size=2;
  bit [31:0] a_address, a_data, d_data;
  bit [3:0] a_source, d_source;
  bit rvfi_valid;
  bit [63:0] rvfi_order;
  bit [31:0] rvfi_insn, rvfi_mem_addr, rvfi_mem_rdata, rvfi_rd_wdata;
endinterface

// A four-word RAM with a synthetic load retirement observation, not a CPU.
module tiny_ram(tl_if b);
  bit [31:0] mem[4];
  bit [63:0] order;
  assign b.a_ready = !b.d_valid;
  always @(posedge b.clk) begin
    if (b.reset) begin
      foreach(mem[i]) mem[i] <= 0;
      b.d_valid <= 0; b.rvfi_valid <= 0; order <= 0;
    end else begin
      if (b.d_valid && b.d_ready) b.d_valid <= 0;
      b.rvfi_valid <= 0;
      if (b.a_valid && b.a_ready) begin
        b.d_valid <= 1;
        b.d_source <= b.a_source;
        b.d_opcode <= b.a_opcode == 4 ? 1 : 0;
        b.d_data <= b.a_opcode == 4 ? mem[b.a_address >> 2] : 0;
        if (b.a_opcode == 0) mem[b.a_address >> 2] <= b.a_data;
        else begin
          b.rvfi_valid <= 1;
          b.rvfi_order <= order; order <= order + 1;
          b.rvfi_insn <= (b.a_address << 20) | 32'h2083; // lw x1, address(x0)
          b.rvfi_mem_addr <= b.a_address;
          b.rvfi_mem_rdata <= mem[b.a_address >> 2];
          b.rvfi_rd_wdata <= mem[b.a_address >> 2] ^ ( $test$plusargs("corrupt") ? 1 : 0);
        end
      end
    end
  end
endmodule
