// Digital aperture abstraction. Each bit can resolve to the old or new sample.
// This does not model voltage, MTBF, setup/hold, or resolution time.
module rvw_cdc_sample #(parameter WIDTH=1)(
  input clk, reset, tick,
  input [WIDTH-1:0] value, choose_old,
  output reg [WIDTH-1:0] sampled
);
  reg [WIDTH-1:0] previous, first;
  always @(posedge clk) begin
    if (reset) begin previous <= 0; first <= 0; sampled <= 0; end
    else begin
      previous <= value;
      if (tick) begin
        first <= (previous & choose_old) | (value & ~choose_old);
        sampled <= first;
      end
    end
  end
endmodule
