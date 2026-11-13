"""Bounded input and runtime variants of the pinned upstream benchmarks."""
from pathlib import Path
import re
import shutil


START = '''.section .text.init
.globl _start
_start:
.option push
.option norelax
  la gp, __global_pointer$
.option pop
  la tp, _end
  la sp, _end
  li t0, 0x20000
  add sp, sp, t0
  li a0, 0
  li a1, 1
  tail _init
'''

CHECK = '''  return Int_Glob != 5 || Bool_Glob != 1 || Ch_1_Glob != 'A' || Ch_2_Glob != 'B'
    || Arr_1_Glob[8] != 7 || Arr_2_Glob[8][7] != Number_Of_Runs + 10
    || Ptr_Glob->Ptr_Comp != Next_Ptr_Glob || Ptr_Glob->Discr != Ident_1
    || Ptr_Glob->variant.var_1.Enum_Comp != Ident_3 || Ptr_Glob->variant.var_1.Int_Comp != 17
    || Next_Ptr_Glob->Ptr_Comp != Next_Ptr_Glob || Next_Ptr_Glob->Discr != Ident_1
    || Next_Ptr_Glob->variant.var_1.Enum_Comp != Ident_2 || Next_Ptr_Glob->variant.var_1.Int_Comp != 18
    || strcmp(Ptr_Glob->variant.var_1.Str_Comp, "DHRYSTONE PROGRAM, SOME STRING")
    || strcmp(Next_Ptr_Glob->variant.var_1.Str_Comp, "DHRYSTONE PROGRAM, SOME STRING")
    || Int_1_Loc != 5 || Int_2_Loc != 13 || Int_3_Loc != 7 || Enum_Loc != Ident_2
    || strcmp(Str_1_Loc, "DHRYSTONE PROGRAM, 1'ST STRING")
    || strcmp(Str_2_Loc, "DHRYSTONE PROGRAM, 2'ND STRING");'''


def prepare(source, out, bench, options):
    """Keep all edits in build output; leave the captured source tree unchanged."""
    root = out / 'runtime'
    src = root / 'benchmarks'
    src.mkdir(parents=True)
    shutil.copytree(source / 'env', root / 'env')
    for name in ('common', bench):
        shutil.copytree(source / 'benchmarks' / name, src / name)
    if options.get('RUNTIME') in ('user-counters', 'no-counters'):
        (src / 'common/crt.S').write_text(START)
    if bench in ('qsort', 'rsort') and 'SORT_SIZE' in options:
        size = int(options['SORT_SIZE'])
        if not 2 <= size <= 2048:
            raise ValueError('sort size must be between 2 and 2048')
        dataset = src / bench / 'dataset1.h'
        original = dataset.read_text()
        match = re.search(r'input_data\[DATA_SIZE\]\s*=\s*\{([^}]+)\}', original, re.S)
        values = [int(v.strip()) for v in match[1].split(',') if v.strip()][:size]
        if len(values) != size:
            raise ValueError('upstream sort input changed')
        # Preserve the pinned input prefix. Python sorting provides the expected output.
        text = '// See upstream LICENSE for license details.\n#define DATA_SIZE ' + str(size) + '\n'
        for name, numbers in (('input_data', values), ('verify_data', sorted(values))):
            text += 'type ' + name + '[DATA_SIZE] = {' + ','.join(map(str, numbers)) + '};\n'
        dataset.write_text(text)
    if bench == 'spmv' and 'SPMV_ROWS' in options:
        rows = int(options['SPMV_ROWS'])
        if not 1 <= rows <= 500:
            raise ValueError('spmv rows must be between 1 and 500')
        dataset = src / bench / 'dataset1.h'
        dataset.write_text(re.sub(r'^#define R 500$', '#define R ' + str(rows), dataset.read_text(), flags=re.M))
    if bench == 'dhrystone':
        main = src / bench / 'dhrystone_main.c'
        text = main.read_text()
        if text.count('  return 0;') != 1:
            raise ValueError('upstream Dhrystone checker insertion changed')
        text = text.replace('  return 0;', CHECK)
        text = text.replace('if (User_Time < Too_Small_Time)', 'if (0)')
        main.write_text(text)
        header = src / bench / 'dhrystone.h'
        runs = int(options.get('DHRYSTONE_RUNS', '10'))
        if runs < 1:
            raise ValueError('Dhrystone runs must be positive')
        header.write_text(re.sub(r'#define NUMBER_OF_RUNS\s+500', '#define NUMBER_OF_RUNS ' + str(runs), header.read_text()))
    if options.get('RUNTIME') == 'user-counters':
        # Direct counter reads can also occur in a benchmark's timer header.
        for path in src.rglob('*'):
            if path.suffix in ('.h', '.c', '.S'):
                text = path.read_text()
                text = re.sub(r'\bmcycleh?\b', lambda m: m[0][1:], text)
                text = re.sub(r'\bminstreth?\b', lambda m: m[0][1:], text)
                path.write_text(text)
    if options.get('RUNTIME') == 'no-counters':
        # C1 supplies timing. Do not require optional architectural counters.
        for path in src.rglob('*'):
            if path.suffix in ('.h', '.c'):
                text = re.sub(r'\bread_csr\(\s*m?(?:cycle|instret)h?\s*\)', '0', path.read_text())
                if path.name == 'dhrystone_main.c':
                    prefixes = ('Microseconds =', 'Dhrystones_Per_Second =',
                                'printf("Microseconds for one run through Dhrystone:',
                                'printf("Dhrystones per Second:')
                    text = '\n'.join(line for line in text.splitlines() if not line.strip().startswith(prefixes)) + '\n'
                path.write_text(text)
    return src
