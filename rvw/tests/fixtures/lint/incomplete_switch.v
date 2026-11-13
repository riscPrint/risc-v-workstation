module IncompleteSwitch(input [1:0] select, input data, output reg result);
  always @* case (select)
    0: result = data;
    1: result = !data;
  endcase
endmodule
