// APB word-spaced 16550 register interface. Baud = clk/(16*divisor).
module rvw_uart16550 (
 input wire clk, reset,
 input wire [7:0] PADDR, input wire PSEL, PENABLE, PWRITE,
 input wire [31:0] PWDATA, output reg [31:0] PRDATA,
 output wire PREADY, PSLVERROR,
 input wire rxd, output wire txd, output wire irq,
 input wire cts_n, dsr_n, ri_n, dcd_n,
 output wire rts_n, dtr_n, out1_n, out2_n, rx_ready_n, tx_ready_n
);
 reg [7:0] lcr, scratch;
 reg [3:0] ier;
 reg [4:0] mcr;
 reg [15:0] divisor;
 reg fifo_enable,dma_mode,tx_dma_ready,rx_dma_ready;
 reg [1:0] trigger_select;
 reg [7:0] tx_mem [0:15];
 reg [10:0] rx_mem [0:15]; // data, parity, framing, break
 reg [3:0] tx_rd,tx_wr,rx_rd,rx_wr;
 reg [4:0] tx_count,rx_count;
 reg overrun,head_error_cleared,tx_irq_pending,previous_tx_empty;
 reg [26:0] timeout_counter;
 reg [3:0] modem_previous,modem_delta;
 reg [1:0] rx_sync;
 reg [3:0] modem_meta,modem_sync;
 wire [3:0] modem = mcr[4] ? {mcr[3],mcr[2],mcr[0],mcr[1]} : ~modem_sync;
 wire [3:0] modem_edges = {(modem[3]^modem_previous[3]),(modem_previous[2] & ~modem[2]),
                           (modem[1]^modem_previous[1]),(modem[0]^modem_previous[0])};
 wire [4:0] capacity = fifo_enable ? 5'd16 : 5'd1;
 wire [3:0] data_bits = {2'b0,lcr[1:0]}+4'd5;
 wire [20:0] bit_ticks = {1'b0,divisor,4'b0};
 wire [20:0] stop_ticks = !tx_frame_lcr[2] ? bit_ticks :
                         (tx_length==5 ? bit_ticks+(bit_ticks>>1) : bit_ticks<<1);
 wire [5:0] frame_half_bits = ((6'd2+{2'b0,data_bits}+{5'b0,lcr[3]})<<1) +
                              (lcr[2] ? (data_bits==5 ? 6'd1 : 6'd2) : 6'd0);
 wire [26:0] timeout_ticks = (bit_ticks * frame_half_bits)<<1;
 wire access = PSEL && PENABLE && !PSLVERROR;
 wire wr = access && PWRITE;
 wire rd = access && !PWRITE;
 wire [2:0] address = PADDR[4:2];
 wire tx_write = wr && address==0 && !lcr[7] && tx_count<capacity;
 wire rx_read = rd && address==0 && !lcr[7] && rx_count!=0;
 wire fcr_write = wr && address==2;
 wire rx_clear = fcr_write && (PWDATA[1] || PWDATA[0]!=fifo_enable);
 wire tx_clear = fcr_write && (PWDATA[2] || PWDATA[0]!=fifo_enable);
 wire lsr_read = rd && address==5;
 wire msr_read = rd && address==6;
 wire [2:0] head_error = rx_count!=0 && !head_error_cleared ? rx_mem[rx_rd][10:8] : 0;
 reg [4:0] fifo_errors;
 wire receiver_error = overrun || |head_error;
 wire [4:0] trigger_level = !fifo_enable ? 1 :
                            trigger_select==0 ? 1 : trigger_select==1 ? 4 : trigger_select==2 ? 8 : 14;
 wire line_irq = ier[2] && receiver_error;
 wire data_irq = ier[0] && rx_count>=trigger_level;
 wire timeout_irq = ier[0] && fifo_enable && rx_count!=0 && timeout_counter==0;
 wire thre_irq = ier[1] && tx_irq_pending;
 wire modem_irq = ier[3] && |modem_delta;
 wire [3:0] interrupt_id = line_irq ? 4'h6 : data_irq ? 4'h4 : timeout_irq ? 4'hc :
                           thre_irq ? 4'h2 : modem_irq ? 4'h0 : 4'h1;
 assign irq = !interrupt_id[0];
 assign rts_n = mcr[4] | ~mcr[1]; assign dtr_n = mcr[4] | ~mcr[0];
 assign out1_n = mcr[4] | ~mcr[2]; assign out2_n = mcr[4] | ~mcr[3];
 assign rx_ready_n = dma_mode && fifo_enable ? !rx_dma_ready : (rx_count==0);
 assign tx_ready_n = dma_mode && fifo_enable ? !tx_dma_ready : (tx_count!=0);
 assign PREADY = 1'b1;
 assign PSLVERROR = |PADDR[1:0] || |PADDR[7:5];
 localparam IDLE=0, START=1, DATA=2, PARITY=3, STOP=4;
 reg [2:0] tx_state,rx_state;
 reg tx_line,tx_parity,rx_parity_bad,rx_previous,rx_all_zero;
 reg [7:0] tx_shift,rx_shift;
 reg [3:0] tx_index,rx_index,tx_length,rx_length;
 reg [20:0] tx_timer,rx_timer;
 reg [7:0] tx_frame_lcr,rx_frame_lcr;
 reg rx_push;
 reg [10:0] rx_value;
 wire internal_tx = lcr[6] ? 1'b0 : tx_line;
 wire serial_in = mcr[4] ? internal_tx : rx_sync[1];
 wire tx_take = tx_state==IDLE && tx_count!=0 && divisor!=0 && !tx_clear;
 wire rx_store = rx_push && (rx_count<capacity || rx_read);
 wire clear_head_error = rx_count!=0 && !head_error_cleared && |rx_mem[rx_rd][10:8] && (lsr_read || rx_read);
 wire new_fifo_error = rx_store && |rx_value[10:8];
 assign txd = mcr[4] ? 1'b1 : internal_tx;
 function automatic parity_bit(input [7:0] value,input [3:0] length,input [7:0] config_lcr);
   integer i; reg p;
   begin
     p=0;
     for(i=0;i<8;i=i+1) if(i<length) p=p^value[i];
     parity_bit=config_lcr[5] ? ~config_lcr[4] : (p ^ ~config_lcr[4]);
   end
 endfunction
 always @* begin
   PRDATA=0;
   case(address)
    0: PRDATA=lcr[7] ? {24'b0,divisor[7:0]} : (rx_count!=0 ? {24'b0,rx_mem[rx_rd][7:0]} : 0);
    1: PRDATA=lcr[7] ? {24'b0,divisor[15:8]} : {28'b0,ier};
    2: PRDATA={24'b0,{2{fifo_enable}},2'b0,interrupt_id};
    3: PRDATA={24'b0,lcr};
    4: PRDATA={27'b0,mcr};
    5: PRDATA={24'b0,(fifo_enable && fifo_errors!=0),(tx_count==0 && tx_state==IDLE),
                (tx_count==0),head_error[2],head_error[1],head_error[0],overrun,(rx_count!=0)};
    6: PRDATA={24'b0,modem,modem_delta};
    7: PRDATA={24'b0,scratch};
   endcase
 end
 always @(posedge clk or posedge reset) begin
  if(reset) begin
   lcr<=0; ier<=0; mcr<=0; divisor<=1; scratch<=0;
   fifo_enable<=0; dma_mode<=0;tx_dma_ready<=1;rx_dma_ready<=0;trigger_select<=0;
   tx_rd<=0;tx_wr<=0;rx_rd<=0;rx_wr<=0;tx_count<=0;rx_count<=0;
   overrun<=0;head_error_cleared<=0;fifo_errors<=0;
   tx_irq_pending<=0;previous_tx_empty<=1;timeout_counter<=0;
   modem_previous<=0;modem_delta<=0;rx_sync<=3;modem_meta<=15;modem_sync<=15;
  end else begin
   rx_sync<={rx_sync[0],rxd}; modem_meta<={dcd_n,ri_n,dsr_n,cts_n};modem_sync<=modem_meta;
   modem_previous<=modem; modem_delta<=(msr_read ? 4'b0 : modem_delta)|modem_edges;
   previous_tx_empty<=tx_count==0;
   if(tx_count==0 && !previous_tx_empty) tx_irq_pending<=1;
   if(rd && address==2 && interrupt_id==2) tx_irq_pending<=0;
   if(wr) case(address)
    0: if(lcr[7]) divisor[7:0]<=PWDATA[7:0];
    1: if(lcr[7]) divisor[15:8]<=PWDATA[7:0]; else begin
         ier<=PWDATA[3:0]; if(PWDATA[1] && !ier[1] && tx_count==0) tx_irq_pending<=1;
       end
    3: lcr<=PWDATA[7:0];
    4: mcr<=PWDATA[4:0];
    7: scratch<=PWDATA[7:0];
   endcase
   if(fcr_write) begin fifo_enable<=PWDATA[0];dma_mode<=PWDATA[3];trigger_select<=PWDATA[7:6];end
   if(tx_count==0) tx_dma_ready<=1;
   if(tx_write && tx_count+1'b1==capacity) tx_dma_ready<=0;
   if(tx_clear) tx_dma_ready<=1;
   if(tx_write) begin tx_mem[tx_wr]<=PWDATA[7:0];tx_wr<=tx_wr+1'b1;tx_irq_pending<=0;end
   if(tx_take) tx_rd<=tx_rd+1'b1;
   case({tx_write,tx_take}) 2'b10:tx_count<=tx_count+1'b1;2'b01:tx_count<=tx_count-1'b1;default:;endcase
   if(tx_clear) begin tx_rd<=0;tx_wr<=0;tx_count<=0;end
   if(lsr_read) begin overrun<=0;head_error_cleared<=1;end
   if(rx_read) begin rx_rd<=rx_rd+1'b1;head_error_cleared<=0;end
   if(rx_store) begin rx_mem[rx_wr]<=rx_value;rx_wr<=rx_wr+1'b1;if(rx_count==0) head_error_cleared<=0;end
   if(rx_push && !rx_store) overrun<=1;
   case({rx_store,rx_read}) 2'b10:rx_count<=rx_count+1'b1;2'b01:rx_count<=rx_count-1'b1;default:;endcase
   case({new_fifo_error,clear_head_error}) 2'b10:fifo_errors<=fifo_errors+1'b1;2'b01:fifo_errors<=fifo_errors-1'b1;default:;endcase
   if(rx_count>=trigger_level || (rx_count!=0 && timeout_counter==0)) rx_dma_ready<=1;
   if((rx_read && rx_count==1 && !rx_store) || rx_clear || (rx_count==0 && !rx_store)) rx_dma_ready<=0;
   if(rx_push || rx_read || rx_count==0) timeout_counter<=timeout_ticks;
   else if(timeout_counter!=0) timeout_counter<=timeout_counter-1'b1;
   if(rx_clear) begin rx_rd<=0;rx_wr<=0;rx_count<=0;overrun<=0;head_error_cleared<=0;fifo_errors<=0;timeout_counter<=timeout_ticks;end
  end
 end
 always @(posedge clk or posedge reset) begin
  if(reset) begin tx_state<=IDLE;tx_line<=1;tx_timer<=0;tx_shift<=0;tx_index<=0;tx_length<=8;tx_parity<=0;tx_frame_lcr<=0;end
  else if(tx_take) begin
   tx_shift<=tx_mem[tx_rd];tx_length<=data_bits;tx_frame_lcr<=lcr;
   tx_parity<=parity_bit(tx_mem[tx_rd],data_bits,lcr);
   tx_line<=0;tx_state<=START;tx_timer<=bit_ticks-1'b1;tx_index<=0;
  end else if(tx_state!=IDLE && divisor!=0) begin
   if(tx_timer!=0) tx_timer<=tx_timer-1'b1;
   else begin
    tx_timer<=bit_ticks-1'b1;
    case(tx_state)
     START:begin tx_state<=DATA;tx_line<=tx_shift[0];end
     DATA:if(tx_index+1<tx_length) begin tx_shift<=tx_shift>>1;tx_line<=tx_shift[1];tx_index<=tx_index+1'b1;end
          else if(tx_frame_lcr[3]) begin tx_line<=tx_parity;tx_state<=PARITY;end
          else begin tx_line<=1;tx_state<=STOP;tx_timer<=stop_ticks-1'b1;end
     PARITY:begin tx_line<=1;tx_state<=STOP;tx_timer<=stop_ticks-1'b1;end
     STOP:begin tx_state<=IDLE;tx_line<=1;end
     default:tx_state<=IDLE;
    endcase
   end
  end
 end
 always @(posedge clk or posedge reset) begin
  if(reset) begin rx_state<=IDLE;rx_timer<=0;rx_shift<=0;rx_index<=0;rx_length<=8;
    rx_frame_lcr<=0;rx_parity_bad<=0;rx_push<=0;rx_value<=0;rx_previous<=1;rx_all_zero<=1;end
  else begin
   rx_push<=0;rx_previous<=serial_in;
   if(rx_state==IDLE) begin
    if(rx_previous && !serial_in && divisor!=0) begin
     rx_state<=START;rx_timer<=(bit_ticks>>1)-1'b1;rx_length<=data_bits;rx_frame_lcr<=lcr;
     rx_index<=0;rx_shift<=0;rx_parity_bad<=0;rx_all_zero<=1;
    end
   end else if(divisor!=0) begin
    if(rx_timer!=0) rx_timer<=rx_timer-1'b1;
    else begin
     rx_timer<=bit_ticks-1'b1;
     case(rx_state)
      START:if(serial_in) rx_state<=IDLE;else rx_state<=DATA;
      DATA:begin
       rx_shift[rx_index[2:0]]<=serial_in;rx_all_zero<=rx_all_zero && !serial_in;
       if(rx_index+1<rx_length) rx_index<=rx_index+1'b1;
       else rx_state<=rx_frame_lcr[3] ? PARITY : STOP;
      end
      PARITY:begin rx_parity_bad<=serial_in!=parity_bit(rx_shift,rx_length,rx_frame_lcr);
                   rx_all_zero<=rx_all_zero && !serial_in;rx_state<=STOP;end
      STOP:begin rx_value<={(!serial_in && rx_all_zero),!serial_in,rx_parity_bad,rx_shift};rx_push<=1;rx_state<=IDLE;end
      default:rx_state<=IDLE;
     endcase
    end
   end
  end
 end
endmodule
