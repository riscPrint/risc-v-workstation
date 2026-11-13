"""Name the project bindings each SoC verification consumer needs."""

HELP = {
 'protocol': {'command':'Run the generated monitors on RTL. Publish fresh rvw.soc-verify-evidence/1 with positive checks and status pass. A generated bind file alone is insufficient.'},
 'registers': {'capture':'Path to independently sampled peripheral APB JSONL from a native run.',
               'write_read':'List region.register names that need checked reads after writes. Or bind a command that publishes scoped native evidence.'},
 'vip': {'composition':'Path to the project soc-compose JSON with one device binder per map region.',
         'classpath_file':'Path to a file containing the compiled SpinalSoc runtime classpath. Supply idle_inputs for exported inputs.'},
 'uvm': {'composition':'Path to the project soc-compose JSON with one device binder per map region.',
         'classpath_file':'Path to a file containing the compiled SpinalSoc runtime classpath. Supply idle_inputs for exported inputs.'},
 'decode': {'classpath_file':'Path to a file containing the SpinalSoc runtime classpath. The built-in consumer proves Fabric.connect for the selected windows.'},
 'connectivity': {'database':'Path to a SpinalDB database of the elaborated SoC.',
                  'manifest':'Path to the formal connection table, with source, target, clock/reset and activation bindings.'},
 'cdc_rdc': {'database':'Path to a SpinalDB database with clock/reset domains. Supply intent and required_libraries only for actual crossings. A single-domain design cannot earn multi-domain signoff.'},
}


def diagnose(kind, entry, model):
    if entry.get('command'):
        return dict(missing_bindings=[], binding_help={}, needed_evidence='Inspect the consumer log and result. A successful exit needs fresh evidence with the selected map hash, kind, verdict and positive checks.')
    fields = HELP[kind]
    missing = [key for key in fields if not entry.get(key)]
    if kind == 'registers' and not any(r['registers'] for r in model['regions']):
        missing.insert(0, 'map.regions[].registers')
    help = {('checks.'+kind+'.'+key): fields[key] for key in missing if key in fields}
    if 'map.regions[].registers' in missing:
        help['map.regions[].registers'] = 'Declare the implemented MMIO registers with offsets, widths, access, reset and side effects.'
    paths = [key if key.startswith('map.') else 'checks.'+kind+'.'+key for key in missing]
    return dict(missing_bindings=paths, binding_help=help,
                needed_evidence='Bindings select a consumer. Native runtime or proof results must still close its declared scope.')
