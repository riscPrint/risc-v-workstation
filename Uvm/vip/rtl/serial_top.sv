`timescale 1ns/1ps

module serial_top(
 input clk,reset_n,buggy,
 input spi_cs_n,spi_sclk,spi_mosi, output spi_miso,
 input rx,output tx,
 input i2c_scl_low,i2c_sda_low, output i2c_scl,i2c_sda,
 input [7:0] gpio_external,gpio_direction,gpio_output,
 output [7:0] gpio_sampled,gpio_irq
);
 assign spi_miso=spi_mosi^buggy;
 // Change data bit zero while retaining the UART start/stop framing.
 int uart_cycles;
 always @(posedge clk) begin
   if(!reset_n) uart_cycles<=0;
   else if(uart_cycles==0 && !rx) uart_cycles<=1;
   else if(uart_cycles!=0) uart_cycles<=uart_cycles==88 ? 0 : uart_cycles+1;
 end
 assign tx=rx^(buggy && uart_cycles>=8 && uart_cycles<16);
 bit sub_low,old_scl=1,old_sda=1,active; int bits;
 assign i2c_scl=!i2c_scl_low;
 assign i2c_sda=!(i2c_sda_low|sub_low);
 always @(posedge clk) begin
   if(!reset_n) begin bits=0;active=0;sub_low=0;end
   else begin
     if(old_scl && i2c_scl && old_sda!=i2c_sda) begin active=!i2c_sda;bits=0;end
     if(active && !old_scl && i2c_scl) bits++;
     if(old_scl && !i2c_scl) begin
       if(bits==9) bits=0;
       sub_low=active && bits==8 && !buggy;
     end
   end
   old_scl=i2c_scl; old_sda=i2c_sda;
 end
 bit [7:0] sync0,sync1,previous;
 always @(posedge clk) begin
   if(!reset_n) begin sync0<=0;sync1<=0;previous<=0;end
   else begin sync0<=(gpio_output&gpio_direction)|(gpio_external&~gpio_direction);sync1<=sync0;previous<=sync1;end
 end
 assign gpio_sampled=reset_n ? sync1 : 0;
 assign gpio_irq=!reset_n ? 0 : ((sync1&~previous&8'h01)|(~sync1&previous&8'h02)|
   (sync1&8'h04)|(~sync1&8'h08))^{7'b0,buggy};
endmodule
