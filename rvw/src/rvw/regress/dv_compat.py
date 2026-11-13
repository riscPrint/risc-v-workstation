"""Worker-local corrections for the pinned open pygen memory stream.

The external checkout remains unchanged. The defective address, opcode and register handling statements
are corrected. All instruction choice and stream construction stay upstream.
"""
import inspect
import copy
import textwrap


def corrected_load_store_source(source):
    source = textwrap.dedent(source)
    anchors = ('    allowed_instr = []\n', '    for i in range(len(self.addr)):\n',
               '            else:  # unalligned load/store\n',
               '        instr = riscv_instr.get_load_store_instr(allowed_instr)')
    if any(source.count(a) != 1 for a in anchors):
        raise ValueError('pinned pygen memory stream changed; review compatibility patch')
    source = source.replace(anchors[0], '', 1)
    source = source.replace(anchors[1], anchors[1]+'        allowed_instr = []\n', 1)
    start = source.index(anchors[2])
    end = source.index(anchors[3], start)
    # Upstream attached this else to its RV64 condition, rather than to the
    # unaligned-access option. Move the complete block one level outward.
    source = source[:start] + ''.join(line[4:] if line.strip() else line
        for line in source[start:end].splitlines(keepends=True)) + source[end:]
    return source


def constrain_offsets(stream):
    """Keep every emitted address in its selected page, including access width."""
    base, size = int(stream.base), int(stream.max_load_store_offset)
    # Eight bytes also bounds the RV64 stream. Byte accesses retain this margin.
    if size < 8:
        raise ValueError('pygen data page is too small')
    stream.offset = [min(max(int(offset), -base), size-base-8) for offset in stream.offset]
    # Upstream used a separate random address for its alignment test. The
    # instruction emits base+offset, so that is the address it must test.
    stream.addr = [base+offset for offset in stream.offset]


def install_load_store_fix():
    from pygen_src.riscv_load_store_instr_lib import riscv_load_store_base_instr_stream as cls
    import random
    from pygen_src.riscv_instr_gen_config import cfg
    from pygen_src.riscv_instr_pkg import riscv_reg_t
    def prepare(stream):
        # Upstream disables its base-register exclusion constraint. ZERO cannot
        # hold a data-page address. Keep the new base out of destination choices.
        reserved = {int(reg) for reg in cfg.reserved_regs}
        if int(stream.rs1_reg) == 0 or int(stream.rs1_reg) in reserved:
            choices = [reg for reg in riscv_reg_t if int(reg) != 0 and int(reg) not in reserved]
            stream.rs1_reg = random.choice(choices)
        if stream.rs1_reg not in stream.reserved_rd:
            stream.reserved_rd.append(stream.rs1_reg)
        constrain_offsets(stream)
    source = corrected_load_store_source(inspect.getsource(cls.gen_load_store_instr))
    source = source.replace('    enable_compressed_load_store = 0',
                            '    _rvw_prepare(self)\n    enable_compressed_load_store = 0')
    source = source.replace('instr = riscv_instr.get_load_store_instr(allowed_instr)',
                            'instr = copy.deepcopy(riscv_instr.get_load_store_instr(allowed_instr))')
    namespace = dict(cls.gen_load_store_instr.__globals__)
    namespace['_rvw_prepare'] = prepare
    namespace['copy'] = copy
    exec(compile(source, '<rvw pinned pygen memory compatibility>', 'exec'), namespace)
    cls.gen_load_store_instr = namespace['gen_load_store_instr']
