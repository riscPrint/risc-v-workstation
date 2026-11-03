typedef enum logic [1:0] { IDLE = 0, ACTIVE = 1, FINISH = 2 } state_t;
module RtlTiny(input clk, reset, input go, output state_t state);
always @(posedge clk) begin
  if (reset) state <= IDLE;
  else case (state)
    IDLE: if (go) state <= ACTIVE;
    ACTIVE: state <= FINISH;
    FINISH: state <= IDLE;
    default: state <= IDLE;
  endcase
end
endmodule
