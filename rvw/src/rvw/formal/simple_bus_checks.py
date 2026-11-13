"""Sampled protocol safety monitors. Payload ports contain every enabled sideband."""
NAMES = ('axis', 'apb', 'ahb_lite')


def render(kind, width, entries):
    if kind not in NAMES or not 1 <= width <= 4096 or not 1 <= entries <= 1024:
        raise ValueError('invalid simple bus check parameters')
    head = f'module rvw_{kind}(input clk, reset, '
    if kind == 'axis':
        ports = f'input valid, ready, input [{width-1}:0] payload'
        body = f'''reg stalled=0;
reg [{width-1}:0] previous_payload;
always @(posedge clk) begin
 if(reset) stalled<=0;
 else begin
  if(stalled) begin assert(valid); assert(payload == previous_payload); end
  stalled<=valid && !ready;
  previous_payload<=payload;
 end
end'''
    elif kind == 'apb':
        ports = f'input select, enable, ready, error, input [{width-1}:0] request'
        body = f'''reg selected=0, enabled=0, completed=0;
reg [{width-1}:0] previous_request;
always @(posedge clk) begin
 if(reset) begin selected<=0; enabled<=0; completed<=0; end
 else begin
  if(select && enable) begin
   assert(selected);
   assert(request == previous_request);
  end
  if(selected && !completed) begin
   assert(select);
   assert(enable);
  end
  if(selected && enabled && completed && select) assert(!enable);
  selected<=select; enabled<=enable; completed<=select && enable && ready;
  previous_request<=request;
 end
end'''
    else:
        # AHB address phase advances only with HREADY. The request payload is
        # HADDR/HWRITE/HSIZE/HBURST/HPROT/HMASTLOCK, excluding HWDATA (data phase).
        ports = f'''input select, ready, response_error, input [1:0] transfer,
input [{width-1}:0] request'''
        body = f'''reg stalled=0, previous_error=0, previous_ready=1;
reg [1:0] previous_transfer;
reg previous_select;
reg [{width-1}:0] previous_request;
always @(posedge clk) begin
 if(reset) begin stalled<=0; previous_error<=0; previous_ready<=1; end
 else begin
  if(stalled && previous_select && previous_transfer[1] && !previous_error) begin
   assert(select == previous_select);
   assert(request == previous_request);
   if(previous_transfer[1] && !response_error) assert(transfer == previous_transfer);
  end
  if(response_error && ready) assert(previous_error && !previous_ready);
  if(previous_error && !previous_ready) assert(response_error && ready);
  stalled<=!ready;
  previous_transfer<=transfer; previous_select<=select;
  previous_request<=request; previous_error<=response_error; previous_ready<=ready;
 end
end'''
    return head + ports + ');\n' + body + '\nendmodule\n'
