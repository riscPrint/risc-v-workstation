"""Declared resource intent. No register names or reset ownership are inferred."""
NAMES = ('allocation_pool', 'freelist_conservation', 'cam_match', 'counter_bounds')


def render(kind, width, entries):
    if kind not in NAMES or not 1 <= width <= 64 or not 1 <= entries <= 1024:
        raise ValueError('invalid resource check parameters')
    head = f'module rvw_{kind}('
    if kind in ('allocation_pool','freelist_conservation'):
        if entries > 1 << width:
            raise ValueError('tag width cannot represent all entries')
        params=f"parameter [{entries-1}:0] INITIAL_LIVE = {entries}'d0"
        if kind=='freelist_conservation':params+=f", parameter [{entries-1}:0] USABLE = {entries}'d{(1<<entries)-1}"
        head = f"module rvw_{kind} #({params})("
        ports = f'''input clk, reset, input [{entries-1}:0] live,
input alloc0_valid, alloc1_valid, free0_valid, free1_valid,
input [{width-1}:0] alloc0, alloc1, free0, free1'''
        body = f'''reg [{entries-1}:0] expected=INITIAL_LIVE;
wire [{entries-1}:0] allocations = (alloc0_valid ? ({entries}'d1 << alloc0) : {entries}'d0) |
 (alloc1_valid ? ({entries}'d1 << alloc1) : {entries}'d0);
wire [{entries-1}:0] releases = (free0_valid ? ({entries}'d1 << free0) : {entries}'d0) |
 (free1_valid ? ({entries}'d1 << free1) : {entries}'d0);
always @(posedge clk) begin
 if(reset) expected<=INITIAL_LIVE;
 else begin
  assert(live == expected);
  if(alloc0_valid) assert(alloc0 < {entries});
  if(alloc1_valid) assert(alloc1 < {entries});
  if(free0_valid) assert(free0 < {entries});
  if(free1_valid) assert(free1 < {entries});
  assert(!(alloc0_valid && alloc1_valid && alloc0 == alloc1));
  assert(!(free0_valid && free1_valid && free0 == free1));
  assert((releases & ~expected) == 0);
  assert((allocations & expected & ~releases) == 0);
  expected <= (expected & ~releases) | allocations;
 end
end'''
        if kind=='freelist_conservation':
            ports=f'input [{entries-1}:0] free_bits, '+ports
            body+='''
always @(posedge clk) if(!reset) begin
 assert((free_bits & live)==0);
 assert((free_bits | live)==USABLE);
 if(alloc0_valid && alloc0 < ENTRIES) assert(USABLE[alloc0]);
 if(alloc1_valid && alloc1 < ENTRIES) assert(USABLE[alloc1]);
end
'''.replace('ENTRIES',str(entries))
    elif kind == 'cam_match':
        ports = f'input clk, reset, active, require_match, input [{entries-1}:0] match_bits'
        body = '''always @(posedge clk) if(!reset && active) begin
 assert((match_bits & (match_bits - 1'b1)) == 0);
 if(require_match) assert(match_bits != 0);
end'''
    else:
        if entries >= 1 << width:
            raise ValueError('counter width cannot represent upper bound')
        ports = f'input clk, reset, active, input [{width-1}:0] value'
        body = f'always @(posedge clk) if(!reset && active) assert(value <= {entries});'
    return head + ports + ');\n' + body + '\nendmodule\n'
