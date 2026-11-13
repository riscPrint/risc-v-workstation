"""Out-of-order structure rules for wide cores: multi-lane ROB pointers, a ghost
free-list mask and youngest-older-store forwarding. Bindings come from project data."""
NAMES = ('rob_pointers', 'freelist_ghost', 'store_forward_window')

PORTS = {
    'rob_pointers': ('alloc_ptr', 'free_ptr', 'push', 'pop'),
    'freelist_ghost': ('alloc_fire', 'alloc_valid', 'alloc_tags', 'free_valid', 'free_tags'),
    'store_forward_window': ('active', 'is_load', 'hits', 'selected', 'start_ptr', 'end_ptr'),
}


def _log2(entries):
    bits = max(1, (entries - 1).bit_length())
    if 1 << bits != entries:
        raise ValueError('entries must be a power of two')
    return bits


def _popcount(name, lanes, step, width):
    terms = ' + '.join(f"({name}[{i}] ? {width}'d{step} : {width}'d0)" for i in range(lanes))
    return terms or f"{width}'d0"


def render(kind, width, entries, lanes=None):
    """Render one template. `lanes` maps lane parameters for the multi-lane kinds."""
    lanes = dict(lanes or {})
    if kind not in NAMES or type(entries) is not int or not 2 <= entries <= 1024:
        raise ValueError('invalid out-of-order template parameters')
    for key, value in lanes.items():
        if type(value) is not int or not 1 <= value <= 16:
            raise ValueError(f'{key} must be in 1..16')
    if kind == 'rob_pointers':
        # A ROB as two wrapping pointers. Each set push (pop) lane moves the
        # allocation (free) pointer by push_step (pop_step) entries.
        bits = _log2(entries) + 1
        p, q = lanes.get('push_lanes', 1), lanes.get('pop_lanes', 1)
        ps, qs = lanes.get('push_step', 1), lanes.get('pop_step', 1)
        if p * ps > entries or q * qs > entries:
            raise ValueError('lanes times step exceeds entries')
        ports = f'input [{bits-1}:0] alloc_ptr, free_ptr, input [{p-1}:0] push, input [{q-1}:0] pop'
        body = f'''wire [{bits-1}:0] occupancy = alloc_ptr - free_ptr;
wire [{bits-1}:0] pushed = {_popcount('push', p, ps, bits)};
wire [{bits-1}:0] popped = {_popcount('pop', q, qs, bits)};
reg armed = 0;
reg [{bits-1}:0] last_alloc, last_free, last_pushed, last_popped;
always @(posedge clk) begin
 armed <= !reset;
 last_alloc <= alloc_ptr; last_free <= free_ptr; last_pushed <= pushed; last_popped <= popped;
 if(!reset) begin
  assert(occupancy <= {entries});
  assert(popped <= occupancy);
  assert({{1'b0,occupancy}} - {{1'b0,popped}} + {{1'b0,pushed}} <= {entries});
  if(armed) begin
   assert(alloc_ptr == last_alloc + last_pushed);
   assert(free_ptr == last_free + last_popped);
  end
 end
end'''
    elif kind == 'freelist_ghost':
        # The free list may live in a RAM; the check keeps its own free-tag mask
        # from allocate (pop) and free (push) events. Empty after reset.
        if entries > 1 << width:
            raise ValueError('tag width cannot represent all entries')
        a, f = lanes.get('alloc_lanes', 1), lanes.get('free_lanes', 1)
        ports = (f'input alloc_fire, input [{a-1}:0] alloc_valid, input [{a*width-1}:0] alloc_tags, '
                 f'input [{f-1}:0] free_valid, input [{f*width-1}:0] free_tags')
        lines = []
        for i in range(a):
            tag = f'alloc_tags[{i*width} +: {width}]'
            lines.append(f'''  if(alloc_fire && alloc_valid[{i}]) begin
   assert({tag} < {entries});
   assert(free_set[{tag}]);''')
            lines += [f'   if(alloc_valid[{j}]) assert({tag} != alloc_tags[{j*width} +: {width}]);' for j in range(i+1, a)]
            lines.append('  end')
        for i in range(f):
            tag = f'free_tags[{i*width} +: {width}]'
            lines.append(f'''  if(free_valid[{i}]) begin
   assert({tag} < {entries});
   assert(!free_set[{tag}]);''')
            lines += [f'   if(free_valid[{j}]) assert({tag} != free_tags[{j*width} +: {width}]);' for j in range(i+1, f)]
            lines.append('  end')
        allocs = ' | '.join(f"(alloc_fire && alloc_valid[{i}] ? ({entries}'d1 << alloc_tags[{i*width} +: {width}]) : {entries}'d0)" for i in range(a))
        frees = ' | '.join(f"(free_valid[{i}] ? ({entries}'d1 << free_tags[{i*width} +: {width}]) : {entries}'d0)" for i in range(f))
        body = f'''reg [{entries-1}:0] free_set = 0;
wire [{entries-1}:0] allocations = {allocs};
wire [{entries-1}:0] releases = {frees};
always @(posedge clk) begin
 if(reset) free_set <= 0;
 else begin
''' + '\n'.join(lines) + '''
  free_set <= (free_set & ~allocations) | releases;
 end
end'''
    else:
        # Forwarding legality and age: a forwarding store must be live, older
        # than the load ([start_ptr, end_ptr) of a wrapping store queue), and
        # the youngest such store that matches.
        bits = _log2(entries)
        ports = (f'input active, is_load, input [{entries-1}:0] hits, selected, '
                 f'input [{bits}:0] start_ptr, end_ptr')
        body = f'''wire [{bits}:0] window = end_ptr - start_ptr;
function automatic [{bits-1}:0] age(input integer i);
 age = end_ptr[{bits-1}:0] - 1'b1 - i[{bits-1}:0];
endfunction
integer i, j;
always @(posedge clk) if(!reset && active && is_load) begin
 assert(window <= {entries});
 assert((selected & (selected - 1'b1)) == 0);
 assert((selected & ~hits) == 0);
 assert((selected != 0) == (hits != 0));
 for(i=0;i<{entries};i=i+1) if(hits[i]) begin
  assert(age(i) < window);
  for(j=0;j<{entries};j=j+1) if(selected[j] && j != i) assert(age(j) < age(i));
 end
end'''
    return f'module rvw_{kind}(input clk, reset, ' + ports + ');\n' + body + '\nendmodule\n'
