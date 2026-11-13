"""Generate a bounded TL-C monitor from project-selected SpinalDB signals."""
import json
from pathlib import Path
import re
import sqlite3


FIELDS = {
    'a_valid': 1, 'a_ready': 1, 'a_opcode': 3, 'a_param': 3,
    'a_source': 'source', 'a_address': 'address', 'a_size': 'size',
    'b_valid': 1, 'b_ready': 1, 'b_opcode': 3, 'b_param': 3, 'b_source': 'source', 'b_address': 'address', 'b_size': 'size',
    'c_valid': 1, 'c_ready': 1, 'c_opcode': 3, 'c_param': 3, 'c_source': 'source', 'c_data': 'data', 'c_address': 'address', 'c_size': 'size', 'c_corrupt': 1,
    'd_valid': 1, 'd_ready': 1, 'd_opcode': 3, 'd_param': 3, 'd_source': 'source', 'd_sink': 'sink', 'd_data': 'data', 'd_size': 'size', 'd_denied': 1, 'd_corrupt': 1,
    'e_valid': 1, 'e_ready': 1, 'e_sink': 'sink',
}


def monitor(source_bits, sink_bits, address_bits, data_bits, line_address, bound, dirty, size_bits=4, projection=None):
    widths = dict(source=source_bits, sink=sink_bits, address=address_bits, data=data_bits, size=size_bits)
    ports = ['input wire clock', 'input wire reset', f'input wire [{data_bits-1}:0] expected_data']
    for c in range(2):
        for name, width in FIELDS.items():
            w = widths.get(width, width)
            ports.append(f'input wire [{w-1}:0] c{c}_{name}')
    text = 'module rvw_tlc_monitor(\n  ' + ',\n  '.join(ports) + '\n);\n'
    text += f'''integer permission[0:1];
reg acquire[0:1][0:{(1 << source_bits)-1}];
reg release_pending[0:1][0:{(1 << source_bits)-1}];
reg grant[0:1][0:{(1 << sink_bits)-1}];
integer acquire_age[0:1][0:{(1 << source_bits)-1}];
integer grant_age[0:1][0:{(1 << sink_bits)-1}];
reg probe[0:1];
integer probe_source[0:1];
integer probe_cap[0:1];
integer probe_age[0:1];
integer i,j,next_permission;
reg bad;
reg reset_seen = 0;
always @(posedge clock or posedge reset) begin
  bad = 0;
  if (reset) begin
    reset_seen = 1;
    for(i=0;i<2;i=i+1) begin
      permission[i]=0; probe[i]=0; probe_age[i]=0;
      for(j=0;j<{1 << source_bits};j=j+1) begin
        acquire[i][j]=0; release_pending[i][j]=0; acquire_age[i][j]=0;
      end
      for(j=0;j<{1 << sink_bits};j=j+1) begin grant[i][j]=0; grant_age[i][j]=0; end
    end
  end else if(!reset_seen) begin
    if($realtime>0) $fatal(1,"rvw TL-C monitor requires reset before clocks");
  end else begin
    for(i=0;i<2;i=i+1) begin
      if(probe[i]) begin probe_age[i]=probe_age[i]+1; if(probe_age[i]>{bound}) bad=1; end
      for(j=0;j<{1 << source_bits};j=j+1) if(acquire[i][j] || release_pending[i][j]) begin
        acquire_age[i][j]=acquire_age[i][j]+1; if(acquire_age[i][j]>{bound}) bad=1;
      end
      for(j=0;j<{1 << sink_bits};j=j+1) if(grant[i][j]) begin
        grant_age[i][j]=grant_age[i][j]+1; if(grant_age[i][j]>{bound}) bad=1;
      end
    end
'''
    line_size = (data_bits//8).bit_length()-1
    # Normalize same-cycle actions: requests, probes, shrinks, grants, acknowledgments.
    for c in range(2):
        p = f'c{c}_'
        text += f'''    if({p}a_valid && {p}a_ready) begin
      if({p}a_size!={line_size}) bad=1;
      if(({p}a_param==0 || {p}a_param==1) && permission[{c}]!=0) bad=1;
      if({p}a_param==2 && permission[{c}]!=1) bad=1;
      if({p}a_param>2) bad=1;
      if(({p}a_opcode!=6 && {p}a_opcode!=7) || {p}a_address!={address_bits}'h{line_address:x}) bad=1;
      if(acquire[{c}][{p}a_source] || release_pending[{c}][{p}a_source]) bad=1;
      acquire[{c}][{p}a_source]=1; acquire_age[{c}][{p}a_source]=0;
    end
    if({p}b_valid && {p}b_ready) begin
      if({p}b_address!={address_bits}'h{line_address:x} || {p}b_size!={line_size}) bad=1;
      if(({p}b_opcode!=6 && {p}b_opcode!=7) || probe[{c}] || {p}b_param>2) bad=1;
      probe[{c}]=1; probe_source[{c}]={p}b_source; probe_cap[{c}]={p}b_param; probe_age[{c}]=0;
    end
'''
    for c in range(2):
        p = f'c{c}_'
        text += f'''    if({p}c_valid && {p}c_ready) begin
      if({p}c_address!={address_bits}'h{line_address:x} || {p}c_size!={line_size} || {p}c_corrupt) bad=1;
      if({p}c_opcode<4 || {p}c_opcode>7) bad=1;
      case({p}c_param)
        0: begin if(permission[{c}]!=2) bad=1; next_permission=1; end
        1: begin if(permission[{c}]!=2) bad=1; next_permission=0; end
        2: begin if(permission[{c}]!=1) bad=1; next_permission=0; end
        3: begin if(permission[{c}]!=2) bad=1; next_permission=2; end
        4: begin if(permission[{c}]!=1) bad=1; next_permission=1; end
        5: begin if(permission[{c}]!=0) bad=1; next_permission=0; end
        default: begin next_permission=0; bad=1; end
      endcase
      if({int(dirty)} && permission[{c}]==2 && next_permission<2 && !{p}c_opcode[0]) bad=1;
      if({p}c_opcode[0] && {p}c_data!=expected_data) bad=1;
      if({p}c_opcode==4 || {p}c_opcode==5) begin
        if(!probe[{c}] || probe_source[{c}]!={p}c_source) bad=1;
        if((probe_cap[{c}]==2 && next_permission!=0) || (probe_cap[{c}]==1 && next_permission>1)) bad=1;
        probe[{c}]=0;
      end else begin
        if(release_pending[{c}][{p}c_source] || acquire[{c}][{p}c_source]) bad=1;
        release_pending[{c}][{p}c_source]=1; acquire_age[{c}][{p}c_source]=0;
      end
      permission[{c}]=next_permission;
    end
'''
    for c in range(2):
        p = f'c{c}_'
        text += f'''    if({p}d_valid && {p}d_ready) begin
      if({p}d_size!={line_size} || {p}d_denied || {p}d_corrupt) bad=1;
      if({p}d_opcode==4 || {p}d_opcode==5) begin
        if(!acquire[{c}][{p}d_source] || grant[{c}][{p}d_sink] || {p}d_param>1) bad=1;
        next_permission=({p}d_param==0)?2:1;
        if((next_permission==2 && permission[{1-c}]!=0) || (next_permission==1 && permission[{1-c}]==2)) bad=1;
        if({p}d_opcode==5 && {p}d_data!=expected_data) bad=1;
        permission[{c}]=next_permission; acquire[{c}][{p}d_source]=0;
        grant[{c}][{p}d_sink]=1; grant_age[{c}][{p}d_sink]=0;
      end else if({p}d_opcode==6) begin
        if(!release_pending[{c}][{p}d_source]) bad=1;
        release_pending[{c}][{p}d_source]=0;
      end else bad=1;
    end
'''
    for c in range(2):
        p = f'c{c}_'
        text += f'''    if({p}e_valid && {p}e_ready) begin
      if(!grant[{c}][{p}e_sink]) bad=1;
      grant[{c}][{p}e_sink]=0;
    end
'''
    if projection is not None:
        text = text.replace('integer i,j,next_permission;', 'integer i,j,next_permission;\ninteger projection_previous;')
        text = text.replace('  if (reset) begin', '  if (reset) begin\n    projection_previous=0;')
        edges = projection['edges']
        condition = ' || '.join(f'(projection_previous=={a[0]+3*a[1]} && (permission[0]+3*permission[1])=={b[0]+3*b[1]})' for a, b in edges)
        text += '    // Generated finite permission projection; channel/data checks remain separate.\n'
        text += f'    if(!({condition})) bad=1;\n'
        text += '    projection_previous=permission[0]+3*permission[1];\n'
    text = text.replace('integer i,j,next_permission;', 'integer i,j,next_permission;\ninteger why;')
    text = text.replace('  bad = 0;', '  bad = 0; why = 0;')
    pieces = text.split('bad=1;')
    text = pieces[0] + ''.join(f'begin bad=1; if(why==0) why={index}; end'+piece for index, piece in enumerate(pieces[1:], 1))
    return text + '    if(bad) $fatal(1,"rvw TL-C monitor violation code=%0d state=%0d,%0d reset=%0d",why,permission[0],permission[1],reset);\n  end\nend\nendmodule\n'



def generate(database, profile, out):
    config = json.loads(Path(profile).read_text())
    if config.get('schema') != 'rvw.tlc-bind/1' or not config.get('fairness'):
        raise ValueError('TL-C bind profile and named bounded fairness required')
    if config.get('oracle_kind') != 'independent-stimulus':
        raise ValueError('independent stimulus oracle declaration required')
    if config['line_bytes'] <= 0 or config['address_bits'] <= 0 or config['size_bits'] <= 0:
        raise ValueError('positive line, address and size widths required')
    address = int(config['line_address'], 0)
    if address < 0 or address >= 1 << config['address_bits'] or address % config['line_bytes']:
        raise ValueError('line address must fit the bus and be aligned')
    if config['line_bytes'] & (config['line_bytes']-1) or config['data_bits'] <= 0 or config['data_bits']%8 or config['line_bytes']*8%config['data_bits'] or config['line_bytes']*8 < config['data_bits']:
        raise ValueError('line must contain a positive whole number of equal power-of-two data beats')
    if (config['data_bits']//8) & ((config['data_bits']//8)-1):
        raise ValueError('power-of-two data beat width required')
    if config['line_bytes'].bit_length()-1 >= 1 << config['size_bits']:
        raise ValueError('line size does not fit the TL-C size field')
    if not (1 <= config['source_bits'] <= 8 and 1 <= config['sink_bits'] <= 8 and config['bound_cycles'] > 0):
        raise ValueError('invalid bounded monitor dimensions')
    if len(config['clients']) != 2:
        raise ValueError('two project-selected TL-C clients required')
    connection = sqlite3.connect(Path(database).resolve().as_uri()+'?mode=ro', uri=True)
    connection.row_factory = sqlite3.Row
    try:
        signals = {r['id']: dict(r) for r in connection.execute('SELECT * FROM signals')}
        bundles = {r['id']: dict(r) for r in connection.execute('SELECT * FROM bundles')}
        components = {r['id']: dict(r) for r in connection.execute('SELECT * FROM components')}
        clients = [bundles[c['bundle_id']] for c in config['clients']]
        if len({b['id'] for b in clients}) != 2:
            raise ValueError('two distinct project-selected Bus bundles required')
        type_evidence = []
        for bus in clients:
            name = bus['class_name'] or ''
            if name == 'spinal.lib.bus.tilelink.Bus':
                type_evidence.append('qualified-name')
            elif name == 'Bus' and config.get('bus_family') == 'spinal-tilelink':
                children = {b['class_name'].rsplit('.', 1)[-1] for b in bundles.values()
                            if b['component_id'] == bus['component_id'] and b.get('path', '').startswith(bus['path']+'.')}
                if not {'ChannelA', 'ChannelB', 'ChannelC', 'ChannelD', 'ChannelE'} <= children:
                    raise ValueError('Bus is missing the typed TileLink channel structure')
                type_evidence.append('declared-family-and-channel-structure')
            else:
                raise ValueError('selected bundles need a qualified TileLink type or declared family and channel structure')
        component = clients[0]['component_id']
        if clients[1]['component_id'] != component:
            raise ValueError('selected client ports must share one bind component')
        module = components[component]['module']
        def identifier(value):
            if not re.fullmatch(r'[A-Za-z_][A-Za-z0-9_$]*', value):
                raise ValueError('simple RTL identifiers required')
            return value
        module = identifier(module)
        widths = dict(source=config['source_bits'], sink=config['sink_bits'], address=config['address_bits'], data=config['data_bits'], size=config['size_bits'])
        mappings = []
        def signal(signal_id, width):
            row = signals[signal_id]
            if row['component_id'] != component or row['width'] != width or row.get('pruned', 0):
                raise ValueError('binding signal scope, width or pruning mismatch')
            return identifier(row['name'])
        for port, width in [('clock', 1), ('reset', 1), ('expected_data', config['line_bytes']*8)]:
            mappings.append(f'.{port}({signal(config[port], width)})')
        if any(config['expected_data'] in client['signals'].values() for client in config['clients']):
            raise ValueError('oracle must not be a captured channel field')
        for c, client in enumerate(config['clients']):
            if set(client['signals']) != set(FIELDS):
                raise ValueError('complete TL-C channel field mapping required')
            for name, width in FIELDS.items():
                bus = clients[c]
                if bus['class_name'] == 'Bus':
                    channel, field = name.split('_', 1)
                    suffix = '.'+field if field in ('valid', 'ready') else '.payload.'+field
                    if signals[client['signals'][name]].get('spinal_path') != bus['path']+'.'+channel+suffix:
                        raise ValueError('field mapping does not match its typed Bus member')
                mappings.append(f'.c{c}_{name}({signal(client["signals"][name], widths.get(width, width))})')
        from .permission_model import load as load_projection
        projection = load_projection()
        rtl = monitor(config['source_bits'], config['sink_bits'], config['address_bits'], config['line_bytes']*8,
                      int(config['line_address'], 0), config['bound_cycles'], config.get('trunk_dirty', False), config['size_bits'], projection)
        from .tilelink_beats import wrap
        rtl = wrap(rtl, FIELDS, config['source_bits'], config['sink_bits'], config['address_bits'], config['data_bits'],
                   config['size_bits'], config['line_bytes'], config['bound_cycles'])
        binding = f'bind {module} rvw_tlc_monitor rvw_tlc_bound(\n  '+',\n  '.join(mappings)+'\n);\n'
    finally:
        connection.close()
    output = Path(out)
    output.mkdir(parents=True, exist_ok=True)
    monitor_path, bind_path = output/'rvw_tlc_monitor.sv', output/'rvw_tlc_bind.sv'
    for path, data in [(monitor_path, rtl), (bind_path, binding)]:
        with path.open('x') as stream:
            stream.write(data)
    return {'schema': 'rvw.tlc-monitor/1', 'status': 'generated', 'monitor': str(monitor_path),
            'bind': str(bind_path), 'executed': False, 'permission_model': projection, 'fairness': config['fairness'],
            'beats_per_line': config['line_bytes']*8//config['data_bits'], 'bus_type_evidence': type_evidence,
            'scope': 'two-client single-line complete accepted messages; bounded progress'}
