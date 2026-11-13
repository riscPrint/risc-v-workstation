`timescale 1ns/1ps

// Seeded semantic endpoints. No PCIe TLP, Ethernet PHY or JEDEC wire model.
module contracts_top(input bit clk, reset_n, buggy, valid,
 input bit [2:0] protocol, command,
 input bit [7:0] address, tag,
 input bit [63:0] data,
 output bit ready, response_valid,
 output bit [7:0] response_tag,
 output bit [3:0] response_status,
 output bit [63:0] response_data);
 bit [63:0] memory[256];
 bit [63:0] coherent_memory;
 bit row_open;
 assign ready=1;
 always @(posedge clk) begin
  response_valid<=0; response_status<=0;
  if(!reset_n) begin
   foreach(memory[i]) memory[i]<=0;
   coherent_memory<=0; row_open<=0; response_data<=0;
  end else if(valid) begin
   response_valid<=1; response_tag<=tag;
   if(protocol==1 && (command==1 || command==2)) response_status<=1;
   case(protocol)
    0: case(command) // PCIe semantic config, writes, reads and DMA target.
     0: response_data<=64'h56781234;
     1: response_data<=data;
     2: begin memory[address]<=data; response_data<=0; end
     3: response_data<=memory[address] ^ 64'(buggy);
     default: response_data<=0;
    endcase
    1: case(command) // Ethernet eight-byte client packet and host buffer.
     0: begin memory[address]<=data; response_data<=0; end
     1: response_data<=memory[address] ^ 64'(buggy);
     2: begin memory[address]<=data ^ 64'(buggy); response_data<=8; end
     default: response_data<=0;
    endcase
    2: case(command) // Reduced single-bank DRAM command/data endpoint.
     0: begin row_open<=1; response_data<=0; end
     1: begin row_open<=0; response_data<=0; end
     2: response_data<=row_open ? memory[address] ^ 64'(buggy) : 64'hffffffffffffffff;
     3: begin if(row_open) memory[address]<=data; response_data<=0; end
     default: response_data<=0;
    endcase
    3: begin // Reduced coherent request to completion bridge, one line.
     if(command==2) begin coherent_memory<=data; response_data<=data ^ 64'(buggy); end
     else response_data<=coherent_memory ^ 64'(buggy);
    end
    default: response_data<=0;
   endcase
  end
 end
endmodule
