"""Small reusable safety predicates. Parameters come from the specification."""
from pathlib import Path

from . import generated_checks

NAMES = ('rob', 'freelist', 'rename', 'issue', 'lsq', 'credit') + generated_checks.NAMES


def render(kind: str, entries: int = 4, width: int = 3) -> str:
    if kind not in NAMES or type(entries) is not int or not 1 <= entries <= 1024:
        raise ValueError('unknown template or entries outside 1..1024')
    if type(width) is not int or not 1 <= width <= 64:
        raise ValueError('width must be in 1..64')
    if kind in generated_checks.NAMES:
        return generated_checks.render(kind, width, entries)
    hdr = f'module rvw_{kind}(input clk, input reset, '
    if kind in ('rob', 'credit'):
        if entries >= 2**width:
            raise ValueError('width must represent entries without overflow')
        ports = f'input [{width-1}:0] count, input push, input pop'
        body = f'''reg armed=0;
always @(posedge clk) begin
  armed <= !reset;
  if (!reset) begin
    assert(count <= {entries});
    assert(!push || pop || count < {entries});
    assert(!pop || push || count > 0);
    if (armed) assert({{1'b0,count}} == {{1'b0,$past(count)}}
      + ($past(push) ? {width+1}'d1 : {width+1}'d0)
      - ($past(pop) ? {width+1}'d1 : {width+1}'d0));
  end
end'''
    elif kind == 'freelist':
        ports = f'input [{entries-1}:0] free_bits, allocated'
        body = 'always @(posedge clk) if (!reset) assert((free_bits & allocated) == 0);'
    elif kind == 'rename':
        ports = f'input [{entries-1}:0] valid, input [{entries*width-1}:0] tags'
        body = '\n'.join(f'always @(posedge clk) if (!reset && valid[{i}] && valid[{j}]) '
                         f'assert(tags[{i*width} +: {width}] != tags[{j*width} +: {width}]);'
                         for i in range(entries) for j in range(i+1, entries))
        if entries < 2:
            raise ValueError('rename needs at least two entries')
    elif kind == 'issue':
        ports = f'input [{entries-1}:0] issued, valid, ready'
        body = '''always @(posedge clk) if (!reset) begin
 assert((issued & ~valid) == 0);
 assert((issued & ~ready) == 0);
 assert((issued & (issued - 1'b1)) == 0);
end'''
    else:
        ports = f'input load_fire, older_store, address_match, forwarded, input [{width-1}:0] load_data, store_data'
        body = '''always @(posedge clk) if (!reset && load_fire && older_store && address_match) begin
 assert(forwarded);
 assert(load_data == store_data);
end'''
    return hdr + ports + ');\n' + body + '\nendmodule\n'


def run(args):
    text = render(args.kind, args.entries, args.width)
    Path(args.out).write_text(text)
    return 0
