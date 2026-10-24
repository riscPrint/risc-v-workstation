"""Run bounded cover plus unbounded safety proof; only the latter can exclude a point."""
from argparse import Namespace
from collections import Counter
import copy
import json
import os
from pathlib import Path
import re
import shutil
import subprocess

from rvw.common.proc import run_group
from rvw.common.capture import CaptureError
from rvw.results import write_json
from rvw.formal.common import async_state_problems, clock_probe_cmds, clock_problems
from rvw.formal.tools import Toolchain

from . import captured
from .captured import sha256
from . import source_snapshot

# /2: `dependencies` records every file Yosys read through `include` (round 8).
# /3: every included and listed file is a resolution record (`file_record`: the path as opened, every
# symbolic link met while looking it up, the resolved path, the content), so a retargeted link is
# stale (round 9).
# /4: every excluded point carries its cone cover (`cone`): each bit of the state it reads changes under
# the harness (round 14: a hold by assumption passed the global sanity cover).
# /5: rows and generated jobs are verified against the hashed plan and elaboration snapshot.
# /6: refuse asynchronous state controls, including when rechecking the saved netlist on apply.
# /7: every front end reads one frozen RTL/include snapshot, with verified per-job copies.
EXCLUSIONS_SCHEMA = 'rvw.coverage-exclusions/7'
# SIGTERM to SIGKILL for sby: below the MCP job grace (rvw.mcp.jobs.Job.GRACE_S), see formal/common.py.
TOOL_GRACE_S = 10.0


@captured.command
def run_job(argv, cwd, log, timeout):
    """Runs a solver job in its own process group; a timeout, error or MCP cancel stops the tree."""
    bindings = getattr(captured.current(), '_coverage_proof_tools', None)
    environment = bindings.env if bindings is not None else captured.environment()
    with Path(log).open('w') as stream:
        try:
            return run_group(argv, cwd=cwd, stdout=stream, stderr=subprocess.STDOUT, timeout=timeout,
                             grace=TOOL_GRACE_S, env=environment).returncode
        except FileNotFoundError as exc:
            raise ValueError(f'tool not installed: {argv[0]}') from exc


# Yosys turns an unknown name (a typo, or a hierarchical reference `dut.q`, which read_verilog does
# not resolve) into a free undriven wire: a cover on it is trivially reachable, an assert on it fails.
FREE_WIRE = re.compile(r"is implicitly declared|is used but has no driver")
# Input ports named like these are resets too (their polarity is never taken from the name).
RESET_NAMES = ('reset', 'rst', 'reset_n', 'rst_n', 'resetn', 'rstn', 'nreset', 'nrst', 'aresetn')
# Every reset-like input of every register, latch and memory cell Yosys has after `proc; opt_dff`:
# `[(input, polarity parameter or None for active high)]`; each bit is one reset path. A synchronous
# clear (`if (c) q <= 0`) is an `$sdff*` too, an asynchronous load (`$aldff*`) loads its `AD` value.
FF_RESETS = {
    '$sdff': [('SRST', 'SRST_POLARITY')], '$sdffe': [('SRST', 'SRST_POLARITY')], '$sdffce': [('SRST', 'SRST_POLARITY')],
    '$adff': [('ARST', 'ARST_POLARITY')], '$adffe': [('ARST', 'ARST_POLARITY')], '$adlatch': [('ARST', 'ARST_POLARITY')],
    '$aldff': [('ALOAD', 'ALOAD_POLARITY')], '$aldffe': [('ALOAD', 'ALOAD_POLARITY')],
    '$dffsr': [('SET', 'SET_POLARITY'), ('CLR', 'CLR_POLARITY')], '$dffsre': [('SET', 'SET_POLARITY'), ('CLR', 'CLR_POLARITY')],
    '$dlatchsr': [('SET', 'SET_POLARITY'), ('CLR', 'CLR_POLARITY')], '$sr': [('SET', 'SET_POLARITY'), ('CLR', 'CLR_POLARITY')],
    '$memrd_v2': [('ARST', None), ('SRST', None)], '$mem_v2': [('RD_ARST', None), ('RD_SRST', None)],
}
# State cells with no reset input.
NO_RESET = {'$dff', '$dffe', '$ff', '$dlatch', '$memrd', '$memwr', '$memwr_v2', '$meminit', '$meminit_v2', '$mem'}
# Any other cell type that looks like state (a gate-level `$_SDFF_PP0_` written by hand, a newer
# Yosys cell) is not modelled: its resets cannot be read, so the guard refuses.
STATE_LIKE = re.compile(r'(?i)^\$(?:_.*(?:FF|SR|LATCH).*|.*(?:ff|latch|mem|fsm).*|sr)$')
# Clock inputs are not reset paths (a stopped clock fails the sanity cover's `!$stable`).
CLOCK_PORTS = {'CLK', 'RD_CLK', 'WR_CLK'}
# Cells whose output is a free value in the formal flow.
FREE_CELLS = {'$anyseq', '$anyconst', '$allseq', '$allconst', '$anyinit'}
_SV_WORDS = {'and', 'or', 'not', 'inside', 'dist', 'with'}


def _identifiers(expression):
    """Signal names an expression reads (not literals such as 5'd31, not $functions)."""
    out = []
    for m in re.finditer(r"(?<!['$\w])[A-Za-z_][\w$]*(?:\.[A-Za-z_][\w$]*)*", expression):
        start = m.start()
        if start and expression[start - 1] == "'":
            continue
        if m.group(0) not in _SV_WORDS and m.group(0) not in out:
            out.append(m.group(0))
    return out


# Every reset port of a design instance is found by name in the elaborated netlist.
_NAME = re.compile(r'[A-Za-z_][\w$]*')
# Round 15: names and paths that go into a Yosys script or an SBY job file. Yosys runs a script line
# that starts with `!` as a shell command, and splits on whitespace and `;`; a name that starts with
# `-` is an option. Only these characters are written; anything else refuses before any tool runs.
SAFE_BASENAME = re.compile(r'[A-Za-z0-9_][A-Za-z0-9_.+-]*', re.ASCII)
SAFE_PATH = re.compile(r'/[A-Za-z0-9_./+,@=~-]*', re.ASCII)


def check_script_paths(sources, out):
    """Refuses (ValueError), before any tool runs, a source or work directory that cannot be written
    into a Yosys script or SBY job file as it is: the scripts read each source by its basename and
    the SBY `[files]` section lists the absolute paths of the sources and of the job harness."""
    names = [Path(p).name for p in sources]
    for p, name in zip(sources, names):
        if not SAFE_BASENAME.fullmatch(name) or not SAFE_PATH.fullmatch(str(p)):
            raise ValueError(f'formal source path {str(p)!r} has characters a Yosys or SBY script cannot hold: '
                             'use letters, digits and _ . + - in file names (not first: . + -), and also / , @ = ~ '
                             'in directories')
    if len(set(names)) != len(names):
        raise ValueError('formal sources must have unique basenames (the jobs read them side by side)')
    if not SAFE_PATH.fullmatch(str(out)):
        raise ValueError(f'work directory {str(out)!r} has characters an SBY job file cannot hold: use letters, '
                         'digits and _ . + - / , @ = ~')


def check_top(top):
    if not isinstance(top, str) or not re.fullmatch(r'[A-Za-z_][\w$]*', top, re.ASCII):
        raise ValueError('invalid formal top name')


def _read_lines(files, dump=None):
    """The solver's front end: one `read_verilog -formal -sv` per file, in order, by basename. With
    `dump` (the guard), each read also writes its preprocessor output to `<dump><i>.txt`."""
    if any(not SAFE_BASENAME.fullmatch(p.name) for p in files):
        raise ValueError('formal source names cannot go into a Yosys script')
    if dump is None:
        return ''.join(f'read_verilog -formal -sv {p.name}\n' for p in files)
    return ''.join(f'tee -q -o {dump}{i}.txt read_verilog -formal -sv -ppdump {p.name}\n' for i, p in enumerate(files))


@captured.command
def file_record(path):
    return captured.record(captured.file(path), path)


@captured.command
def stale_record(record):
    """Why a resolution record no longer holds (None when it does): the same path, looked up again,
    must meet the same links, end at the same file and read the same bytes."""
    try:
        now = file_record(record['opened'])
    except (OSError, ValueError, KeyError, TypeError) as exc:
        return f'cannot resolve: {exc}'
    for field, what in (('links', 'symbolic links'), ('resolved', 'resolved path'), ('sha256', 'contents')):
        if now[field] != record.get(field):
            return f'{what} changed'
    return None


# The Yosys preprocessor marks every file it opens (`include`d ones too) with `file_push "<path>"`,
# the path as opened, relative to the working directory.
FILE_PUSH = re.compile(r'^`file_push "(.*)"$', re.M)
# Files the front end reads while elaborating, which the preprocessor does not mark: refused.
FILE_READS = source_snapshot.FILE_READS


@captured.command
def dependencies(work, dumps, copies):
    """The files Yosys read beyond the listed sources: `(records, problems)`, `records` keyed by the
    path as Yosys opened it (`file_record`, so a symbolic link on the way is part of it). `dumps` are the
    `-ppdump` outputs of the guard's reads, run in `work`, one per file of `copies` (the sources
    and the harness copied there, already hashed), in order. Each dump must list its own file, or
    the files Yosys read are unknown. An absolute path is hashed. A relative path must be one of
    the copies: the solver runs in the job's `src/`, which holds only those, so a relative include
    of anything else resolves differently there or not at all. A file read during elaboration
    (`$readmemh`, `$fopen`, ...) is not modelled and refuses."""
    hashes, problems = {}, []
    work = Path(work).resolve()
    names = [Path(c).name for c in copies]
    for dump, own in zip(dumps, names):
        text = captured.read_text(dump, errors='replace') if Path(dump).exists() else None
        pushed = FILE_PUSH.findall(text) if text is not None else []
        if own not in pushed:
            problems.append(f'the preprocessor output for {own} does not list the files Yosys read')
            continue
        for name in pushed:
            path = Path(name)
            if path.is_absolute():
                if not path.is_file():
                    problems.append(f'included file {name} is not a readable file')
                    continue
                try:
                    hashes[name] = file_record(name)
                except (OSError, ValueError) as exc:
                    problems.append(f'included file {name} cannot be resolved: {exc}')
            elif path.name in names and (work / path).resolve() == work / path.name:
                continue
            else:
                problems.append(f'relative include {name} is not one of the listed sources (the solver reads '
                                'from another directory): list it in `sources` or include it by absolute path')
        for call in sorted(set(FILE_READS.findall(text))):
            problems.append(f'{call} reads a file during elaboration; such inputs are not hashed')
    return hashes, problems


@captured.command
def elaborate(out, sources, template, top, timeout=60, clock='clk', *, yosys):
    """Elaborates the harness exactly as the solver jobs read it (same files in the same order, same
    front end, no defines, files side by side as in the job's `src/`), then `hierarchy -check -top`,
    `proc` and `write_json`. Returns the netlist record: `modules` (Yosys JSON), `source_modules`
    (the modules the source files define, before the harness is read), `ff_modules` (after
    `opt_dff`), `unbound_modules`/`bound_modules` (then `opt_expr; opt_dff` per module, and after
    `flatten`: see `bound_resets`), `path`/`sha256` of the JSON, or `error` when Yosys cannot
    elaborate it."""
    work = Path(out) / 'guard'
    files = [Path(p).resolve() for p in sources]
    check_script_paths(files, Path(out).resolve())
    check_top(top)
    work.mkdir(parents=True, exist_ok=True)
    for p in files:
        shutil.copyfile(p, work / p.name)
    harness = work / 'guard.sv'
    while harness.name in {p.name for p in files}:
        harness = work / ('_' + harness.name)
    harness.write_text(template)
    # Include a sampled cover at the marker so its edge is checked too, even when the original
    # harness has no state of its own. Keep this separate from the reset/cone netlists.
    clock_harness = work / 'clock-guard.sv'
    while clock_harness.name in {p.name for p in files + [harness]}:
        clock_harness = work / ('_' + clock_harness.name)
    clock_harness.write_text(template.replace('// RVW_POINT', 'cover (!$initstate);'))
    script = work / 'guard.ys'
    # `opt_dff` (after the netlist is written) turns reset muxes into `$sdff` cells with a polarity:
    # `ffs.json` is where reset polarity is read from (`reset_paths`). Then the same netlist twice
    # through `opt_expr; opt_dff`: per module (`unbound.json`), and flattened, so every instance
    # connection is bound and the harness's constants reach the design (`bound.json`, round 13: a
    # `.seed(1'b0)` tie turns `if (hold) q <= seed` into a reset that only shows there).
    script.write_text(_read_lines(files, 'pp-source-') + 'tee -q -o source-modules.txt ls\n'
                      + _read_lines([harness], 'pp-harness-')
                      + f'hierarchy -check -top {top}\nproc\nwrite_json netlist.json\nopt_dff\nwrite_json ffs.json\n'
                      + 'design -save rvw_guard\nopt_expr\nopt_dff\nwrite_json unbound.json\n'
                      + 'design -load rvw_guard\nflatten\nopt_expr\nopt_dff\nwrite_json bound.json\n'
                      + 'design -reset\n' + _read_lines(files + [clock_harness])
                      + f'hierarchy -check -top {top}\nproc\nwrite_json clock-raw.json\n'
                      + 'setattr -set keep 1 */c:*\n'
                      + clock_probe_cmds(top, Path('clock-cells.json')))
    record = {"path": str(work / 'netlist.json'), "script": str(script), "log": str(work / 'guard.log'),
              "harness": str(harness), "clock_harness": str(clock_harness)}
    try:
        rc = run_job([yosys, '-q', '-s', script.name], work, work / 'guard.log', timeout)
    except (subprocess.TimeoutExpired, ValueError) as exc:  # timeout or no yosys: no netlist, nothing inferred
        return {**record, "error": f'yosys could not elaborate the harness: {exc}'}
    if rc != 0 or not (work / 'netlist.json').exists():
        tail = captured.read_text(work / 'guard.log', errors='replace').strip().splitlines()[-3:]
        return {**record, "error": f'yosys could not elaborate the harness (exit {rc}): {" | ".join(tail)}'}
    listed = captured.read_text(work / 'source-modules.txt').splitlines()
    record["source_modules"] = sorted(line.strip() for line in listed if line.startswith('  ') and line.strip())
    record["modules"] = json.loads(captured.read_text(work / 'netlist.json'))['modules']
    record["ff_modules"] = json.loads(captured.read_text(work / 'ffs.json'))['modules']
    record["unbound_modules"] = json.loads(captured.read_text(work / 'unbound.json'))['modules']
    record["bound_modules"] = json.loads(captured.read_text(work / 'bound.json'))['modules']
    problems = clock_problems(work / 'clock-cells.json', top, clock)
    port = record['modules'].get(top, {}).get('ports', {}).get(clock, {})
    if port.get('direction') != 'input' or len(port.get('bits', [])) != 1 \
            or not isinstance(port['bits'][0], int):
        problems.append(f'clock {clock} must be a one-bit harness input')
    # The formal helper checks explicit CLK/TRG inputs. A global-clock FF has no such input.
    raw = json.loads(captured.read_text(work / 'clock-raw.json'))['modules']
    for module, body in raw.items():
        for name, cell in body['cells'].items():
            if cell['type'] in ('$ff', '$_FF_'):
                problems.append(f"{module}.{name}: global clock state is not the rising edge of {clock}")
    record['clock'] = {'clock': clock, 'problems': problems}
    record["sha256"] = sha256(work / 'netlist.json')
    dumps = [work / f'pp-source-{i}.txt' for i in range(len(files))] + [work / 'pp-harness-0.txt']
    record["dependencies"], record["dependency_problems"] = dependencies(work, dumps, files + [harness])
    return record


def _sv_name(name):
    """`name` as SystemVerilog source: escaped when it is not a plain identifier."""
    return name if _NAME.fullmatch(name) and name not in _NOT_NAMES else f'\\{name} '


_NOT_NAMES = {'module', 'endmodule', 'input', 'output', 'inout', 'wire', 'reg', 'logic', 'assign', 'begin',
              'end', 'if', 'else', 'always', 'initial', 'and', 'or', 'not', 'buf', 'xor', 'nand', 'nor', 'xnor'}


def _base(modules, kind):
    return modules[kind].get('attributes', {}).get('hdlname', kind)


def _user_cells(modules, module):
    return [(name, cell) for name, cell in sorted(modules[module]['cells'].items()) if cell['type'] in modules]


def _expression(modules, scope, bits):
    """The harness-top SystemVerilog expression for `bits` in the module path `scope`
    (`[(module, cell name, cell)]`, the top first), or None when it has no plain name there:
    constants, a named top-level net, `!`/`~` of one, or a wrapper port traced to its parent."""
    if bits and all(isinstance(b, str) for b in bits):
        return f"{len(bits)}'b" + ''.join(reversed(bits))
    module = scope[-1][0]
    body = modules[module]
    for kind in ('$not', '$logic_not'):
        for cell in body['cells'].values():
            if cell['type'] == kind and cell['connections'].get('Y') == bits and len(bits) == 1 \
                    and len(cell['connections'].get('A', [])) == 1:
                inner = _expression(modules, scope, cell['connections']['A'])
                return f'!({inner})' if inner else None
    if len(scope) == 1:
        names = sorted(n for n, net in body['netnames'].items() if not net['hide_name'] and net['bits'] == bits)
        return _sv_name(min(names, key=lambda n: (len(n), n))) if names else None
    for port, info in sorted(body['ports'].items()):
        if info['bits'] == bits and info['direction'] == 'input':
            parent = scope[-1][2]['connections'].get(port)
            return _expression(modules, scope[:-1], parent) if parent else None
    return None


def _param(value):
    return int(value, 2) if isinstance(value, str) else int(value)


def _outside_source(body, ff_modules, bits):
    """What the fan-in of `bits` in `body` reads from outside the module's own state, or None when it
    reads only constants and the module's own registers (followed through them, clocks aside): an
    input port, a submodule output, an undriven or undefined bit, or a free formal value."""
    inputs = {b: name for name, info in body['ports'].items() if info['direction'] in ('input', 'inout')
              for b in info['bits'] if not isinstance(b, str)}
    drivers = {}
    for name, cell in body['cells'].items():
        directions = cell.get('port_directions', {})
        for port, conn in cell['connections'].items():
            if directions.get(port) == 'output':
                for b in conn:
                    if not isinstance(b, str):
                        drivers[b] = (name, cell)
    todo, seen = list(bits), set()
    while todo:
        bit = todo.pop()
        if isinstance(bit, str):
            if bit in ('0', '1'):
                continue
            return f'an undefined constant ({bit})'
        if bit in seen:
            continue
        seen.add(bit)
        if bit in inputs:
            return f'input port {inputs[bit]}'
        if bit not in drivers:
            return 'an undriven net'
        name, cell = drivers[bit]
        kind = cell['type']
        if kind in ff_modules or not kind.startswith('$'):
            return f'the output of instance {name} ({kind})'
        if kind in FREE_CELLS:
            return f'a free value ({kind} {name})'
        directions = cell.get('port_directions', {})
        for port, conn in cell['connections'].items():
            if directions.get(port) == 'input' and port not in CLOCK_PORTS:
                todo.extend(conn)
    return None


def _inverters(body):
    return {cell['connections']['Y'][0]: cell['connections']['A'][0]
            for cell in body['cells'].values()
            if cell['type'] in ('$not', '$logic_not')
            and len(cell['connections'].get('A', [])) == 1
            and len(cell['connections'].get('Y', [])) == 1}


def _trace_inverters(bit, inverters, stop):
    parity, seen = 0, set()
    while bit not in stop and bit in inverters and bit not in seen:
        seen.add(bit)
        bit, parity = inverters[bit], parity ^ 1
    return bit, parity


def _reset_bits(cell, what, problems):
    for signal, polarity in FF_RESETS[cell['type']]:
        if polarity and polarity not in cell.get('parameters', {}):
            problems.append(f'{what} has no {polarity} (its resets cannot be read)')
            continue
        active = (_param(cell['parameters'][polarity]) & 1) if polarity else 1
        yield signal, active, cell['connections'].get(signal, [])


def reset_paths(ff_modules, module, memo=None):
    """`(levels, problems)` for `module` (after `opt_dff`). `levels` is `{input port: {levels}}`: for
    each 1-bit input port, the port values that force a register to its reset value, in the module
    or (through instance connections) below it. Every reset path is collected: each bit of every
    reset-like input of every register, latch and memory cell (`FF_RESETS`; a synchronous clear is
    one too) and every reset port of a submodule. A path is modelled when it reaches an input port
    through `$not`/`$logic_not` only. A path through other logic is a problem when that logic reads
    anything from outside the module's own state (`_outside_source`: an input port such as the
    `warm` of `reset || warm`, a submodule output, a free value): the harness could hold it. Logic
    that reads only the module's own registers and constants (a counter wrapping to 0) is design
    behavior, not a reset the harness controls. A state cell type not in `FF_RESETS`/`NO_RESET` is
    a problem: its resets cannot be read."""
    memo = {} if memo is None else memo
    if module in memo:
        return memo[module]
    memo[module] = ({}, [])  # an instance cycle (not valid Verilog) reads as no evidence, not a crash
    body = ff_modules[module]
    inverters = _inverters(body)
    ports = {info['bits'][0]: name for name, info in body['ports'].items()
             if info['direction'] == 'input' and len(info['bits']) == 1 and not isinstance(info['bits'][0], str)}
    levels = {name: set() for name in ports.values()}
    problems = []

    def path(bit, active, what):
        """One reset path: `bit` resets at level `active` (None: unknown)."""
        if isinstance(bit, str):
            if bit in ('0', '1') and active is not None and int(bit) != active:
                return  # tied inactive: no reset
            if bit in ('0', '1'):
                return  # tied active: the design's own constant, not something the harness holds
            problems.append(f'{module}: {what} is undefined ({bit})')
            return
        # Follow every inverter before finding a module input port.
        end, parity = _trace_inverters(bit, inverters, stop=())
        port = ports.get(end)
        if port is not None and active is not None:
            levels[port].add(active ^ parity)
            return
        outside = _outside_source(body, ff_modules, [end])
        if outside is not None:
            problems.append(f'{module}: {what} is driven by logic that reads {outside}; only a plain or inverted '
                            'input port is modelled as a reset')

    for name, cell in sorted(body['cells'].items()):
        kind, conn = cell['type'], cell['connections']
        if kind in FF_RESETS:
            for signal, active, bits in _reset_bits(cell, f'{module}: {kind} {name}', problems):
                for i, bit in enumerate(bits):
                    path(bit, active, f'{kind} {name} {signal}' + (f'[{i}]' if len(bits) > 1 else ''))
        elif kind in ff_modules:
            sub_levels, sub_problems = reset_paths(ff_modules, kind, memo)
            problems.extend(f'{p} (in {module}.{name})' for p in sub_problems)
            for sub, found in sorted(sub_levels.items()):
                if not found:
                    continue
                bits = conn.get(sub, [])
                if len(bits) != 1:
                    problems.append(f'{module}: reset port {sub} of instance {name} is unconnected')
                    continue
                for level in sorted(found):
                    path(bits[0], level, f'reset port {sub} of instance {name}')
        elif kind not in NO_RESET and STATE_LIKE.match(kind):
            problems.append(f'{module}: state cell {name} of type {kind} is not modelled (its resets cannot be read)')
        elif not kind.startswith('$') and kind not in ff_modules:
            problems.append(f'{module}: instance {name} of {kind} has no netlist (its resets cannot be read)')
    memo[module] = (levels, problems)
    return memo[module]


def instance_resets(netlist, top):
    """The resets the elaborated harness gives its design instances: `(resets, instances, problems)`.
    A design instance is an instance of a module the source files define, or a harness module with
    no instances of its own; harness modules with instances (wrappers) are walked through. Its
    resets are the input ports that reset a register (`reset_paths`) and the input ports named
    like a reset (`RESET_NAMES`); a reset path `reset_paths` does not model is a problem. The polarity is read from the registers, never from the name: a
    reset port whose registers do not all reset at one level, or that resets none, cannot be
    checked and is a problem. Each reset's connection is traced to a harness-top expression. An
    instance with no reset, an unconnected one, or one that does not trace to a top-level name is a
    problem: `resets` is only trustworthy when `problems` is empty and `resets` is not."""
    modules, sources = netlist['modules'], set(netlist['source_modules'])
    ff_modules = netlist.get('ff_modules') or {}
    resets, instances, problems = [], [], []
    memo = {}

    def walk(scope, path):
        for name, cell in _user_cells(modules, scope[-1][0]):
            kind = cell['type']
            here = path + [name]
            inner = scope + [(kind, name, cell)]
            if _base(modules, kind) not in sources and _user_cells(modules, kind):
                walk(inner, here)
                continue
            label = f"{_base(modules, kind)} {'.'.join(here)}"
            if kind in ff_modules:
                levels, unmodelled = reset_paths(ff_modules, kind, memo)
                problems.extend(f'{label}: {p}' for p in unmodelled)
            else:
                levels = {}
                problems.append(f'{label}: the netlist after opt_dff has no module {kind}')
            ports = [p for p, info in sorted(modules[kind]['ports'].items())
                     if info['direction'] == 'input' and (p.lower() in RESET_NAMES or levels.get(p))]
            found = []
            if not ports:
                problems.append(f'{label} has no reset: no input port resets a register and none is named like '
                                f'a reset ({"/".join(RESET_NAMES)})')
            for port in ports:
                if len(levels.get(port, ())) != 1:
                    problems.append(f'{label} port {port}: its polarity cannot be read from the netlist ('
                                    + ('registers reset at both levels' if levels.get(port) else
                                       'it resets no register through a plain or inverted connection')
                                    + '); set `reset` and `reset_active_low`')
                    continue
                low = levels[port] == {0}
                bits = cell['connections'].get(port)
                expression = _expression(modules, scope, bits) if bits else None
                if expression is None:
                    problems.append(f'{label} port {port} is ' + ('unconnected' if not bits else
                                    'not wired to a named harness-top signal or constant'))
                    continue
                found.append({"port": port, "expression": expression, "active_low": low})
                if (expression, low) not in resets:
                    resets.append((expression, low))
            instances.append({"instance": '.'.join(here), "module": _base(modules, kind), "resets": found})

    if top not in modules:
        return [], [], [f'the netlist has no top module {top}']
    walk([(top, None, None)], [])
    return resets, instances, problems


def _state_bits(body):
    """`Counter({src: bits})` of the register and latch outputs (`Q`) in one module body."""
    out = Counter()
    for cell in body['cells'].values():
        kind = cell['type']
        if 'Q' in cell['connections'] and _is_state(kind):
            out[cell.get('attributes', {}).get('src') or '(no source location)'] += len(cell['connections']['Q'])
    return out


def _hierarchy_bits(modules, module, memo):
    """`_state_bits` of `module` and every instance below it."""
    if module not in memo:
        memo[module] = Counter()  # an instance cycle (not valid Verilog) counts once, not forever
        total = _state_bits(modules[module])
        for _, cell in _user_cells(modules, module):
            total += _hierarchy_bits(modules, cell['type'], memo)
        memo[module] = total
    return memo[module]


def pinned_state(netlist, top):
    """Register bits that the harness's bindings make constant: problems (empty when none). The same
    netlist went through `opt_expr; opt_dff` per module and flattened (`elaborate`); `opt_dff`
    removes a register whose reset is always active, whose enable or clock never fires, or whose
    next value is its constant initial value. A register bit that is there per module and gone once
    the instance connections are bound is held by the harness (`.hold(1'b1)` with `.seed(1'b0)`):
    a point that reads it is unreachable only because of the tie, so nothing may be excluded."""
    unbound, bound = netlist.get('unbound_modules'), netlist.get('bound_modules')
    if not unbound or not bound or top not in unbound or top not in bound:
        return ['the netlist with the instance connections bound is missing']
    expected, got = _hierarchy_bits(unbound, top, {}), _state_bits(bound[top])
    if sum(got.values()) >= sum(expected.values()):
        return []
    lost = sorted((src, n - got.get(src, 0)) for src, n in expected.items() if n > got.get(src, 0))
    return [f'binding the harness connections makes {sum(expected.values()) - sum(got.values())} register bit(s) '
            'constant (' + ', '.join(f'{n} at {src}' for src, n in lost) + '): the harness pins design state']


def _reset_key(expression, low):
    """`(name, active low)` of a reset term with its `!(...)` wrappers removed."""
    while expression.startswith('!(') and expression.endswith(')'):
        expression, low = expression[2:-1], not low
    return expression, low


def bound_resets(netlist, top):
    """`(resets, problems)` from the netlist with every instance connection bound and the harness's
    constants propagated (`bound_modules`, after `flatten; opt_expr; opt_dff`). A design input that
    is no reset on its own can become one there: `if (hold) q <= seed` with `.seed(1'b0)` is an
    `$sdff` whose reset is the harness's `hold`. Each reset bit of each state cell (`FF_RESETS`) is
    traced through `$not`/`$logic_not` to a net of the harness top (a name the unflattened harness
    top has, not one flattening made): `resets` is `[{"expression", "active_low", "registers"}]`,
    `registers` the source locations of the cells it resets. A bit that reaches no harness net is a
    problem when its logic reads an input, a free value or an unflattened instance
    (`_outside_source`); a bit tied active, an undefined one, an unflattened instance and an
    unmodelled state cell are problems."""
    bound = (netlist.get('bound_modules') or {}).get(top)
    if bound is None:
        return [], ['the netlist with the instance connections bound is missing']
    harness = {n for n, net in netlist['modules'][top]['netnames'].items() if not net['hide_name']}
    # The harness top's own registers (its bookkeeping, `if (rst) cnt <= 0`) are not design state:
    # a cell is the harness's when its source location is that of a state cell of the harness top
    # and of none below it (per module, `unbound_modules`). When unsure it is the design's.
    unbound = netlist.get('unbound_modules') or {}
    own = set(_state_bits(unbound[top])) if top in unbound else set()
    below = set()
    for _, sub in (_user_cells(unbound, top) if top in unbound else []):
        below |= set(_hierarchy_bits(unbound, sub['type'], {}))
    own -= below
    names = {}
    for n, net in sorted(bound['netnames'].items()):
        if net['hide_name'] or n not in harness or 'hdlname' in net.get('attributes', {}):
            continue
        bits = net['bits']
        for i, bit in enumerate(bits):
            if isinstance(bit, str) or (len(bits) > 1 and net.get('upto')):
                continue
            expression = _sv_name(n) if len(bits) == 1 else f'{_sv_name(n)}[{net.get("offset", 0) + i}]'
            if bit not in names or (len(expression), expression) < (len(names[bit]), names[bit]):
                names[bit] = expression
    inverters = _inverters(bound)
    found, problems = {}, []
    for name, cell in sorted(bound['cells'].items()):
        kind, conn = cell['type'], cell['connections']
        where = cell.get('attributes', {}).get('src') or name
        if not kind.startswith('$'):
            problems.append(f'instance {name} of {kind} is not flattened (its resets cannot be read)')
            continue
        if cell.get('attributes', {}).get('src') in own:
            continue
        if kind not in FF_RESETS:
            if kind not in NO_RESET and STATE_LIKE.match(kind):
                problems.append(f'state cell {name} of type {kind} is not modelled (its resets cannot be read)')
            continue
        for signal, active, bits in _reset_bits(cell, f'{kind} at {where}', problems):
            for bit in bits:
                what = f'{kind} {signal} at {where}'
                if isinstance(bit, str):
                    if bit in ('0', '1') and int(bit) != active:
                        continue
                    problems.append(f'{what} is ' + ('tied active (held in reset)' if bit in ('0', '1')
                                                     else f'undefined ({bit})') + ' once the harness is bound')
                    continue
                # Bound traces stop at the first named harness net.
                bit, parity = _trace_inverters(bit, inverters, stop=names)
                if bit in names:
                    found.setdefault((names[bit], (active ^ parity) == 0), set()).add(where)
                    continue
                outside = _outside_source(bound, {}, [bit])
                if outside is not None:
                    problems.append(f'{what} is driven by logic that reads {outside} once the harness is bound; '
                                    'only a harness-top net, plain or inverted, is modelled as a reset')
    for expression, low in found:
        if (expression, not low) in found and not low:
            problems.append(f'{expression} resets registers at both levels once the harness is bound')
    resets = [{"expression": e, "active_low": low, "registers": sorted(found[(e, low)])} for e, low in sorted(found)]
    return resets, problems


# Placeholder wires of the cone cover (round 14): implicitly declared at the point marker, bound to
# the flattened design nets with `connect -set` before anything is cleaned.
CONE_WIRE = 'rvw_cone_'
# A flattened design bit as `point_cone` names it (written into the cone job's script).
CONE_SIGNAL = re.compile(r'[A-Za-z_][\w$]*(?:\.[A-Za-z_][\w$]*)*(?:\[\d+\])?', re.ASCII)
def _is_state(kind):
    return kind in FF_RESETS or kind in NO_RESET or bool(STATE_LIKE.match(kind))


def _module_maps(modules, module, memo):
    """Per module: `(drivers, inputs, names)`: `drivers` maps an output bit of a cell to
    `(cell name, cell, port, index)`, `inputs` an input port bit to `(port, index)`, `names` a bit to
    `(net name, bit position or None)` of its shortest plain non-hidden net name. The position counts
    from the LSB, as Yosys `connect` reads `name[i]` (not the declared index of `reg [7:4]`); a net
    declared `[0:N]` is never used, as its mapping is not checked."""
    if module in memo:
        return memo[module]
    body = modules[module]
    drivers = {}
    for name, cell in body['cells'].items():
        kind = cell['type']
        if kind in modules:
            directions = {p: info['direction'] for p, info in modules[kind]['ports'].items()}
        else:
            directions = cell.get('port_directions', {})
        for port, conn in cell['connections'].items():
            if directions.get(port) in ('output', 'inout'):
                for i, b in enumerate(conn):
                    if not isinstance(b, str):
                        drivers[b] = (name, cell, port, i)
    inputs = {b: (name, i) for name, info in body['ports'].items() if info['direction'] in ('input', 'inout')
              for i, b in enumerate(info['bits']) if not isinstance(b, str)}
    names = {}
    for n, net in sorted(body['netnames'].items()):
        if net['hide_name'] or not _NAME.fullmatch(n) or n in _NOT_NAMES or net.get('upto'):
            continue
        bits = net['bits']
        for i, b in enumerate(bits):
            if isinstance(b, str):
                continue
            index = None if len(bits) == 1 else i
            if b not in names or (len(n), n) < (len(names[b][0]), names[b][0]):
                names[b] = (n, index)
    memo[module] = (drivers, inputs, names)
    return memo[module]


def point_cone(netlist, top, expression):
    """The signals a point reads, traced through its combinational fan-in in the elaborated netlist
    (after `proc`, not flattened, so a harness tie is told apart from a design constant):
    `(signals, problems)`. `signals` are the flattened names (`d.q[3]`, bit positions from the LSB; `seed`) of every bit the
    point's value comes from: register and latch outputs, harness-top input ports and free values
    (`$anyseq`, `$anyconst`). The trace stops there; a register's next-state logic is not part of the
    cone. A point is only excludable when each of these bits can change under the harness (the cone
    cover in `prove`), so a register held by a reset, a tie or an assumption refuses the exclusion.
    Problems (each refuses the exclusion): a name the harness top does not have, a constant the
    harness itself puts in the cone (a constant net the point reads, or a constant tie on an
    instance port made in a harness module; constants of the design's own modules and constant
    operands of logic are the design's), a source bit with no plain name, memory read data, an
    undriven bit, an instance with no netlist."""
    modules = netlist['modules']
    sources = set(netlist.get('source_modules') or [])
    if top not in modules:
        return [], [f'the netlist has no top module {top}']
    memo, problems, signals, seen = {}, [], [], set()
    top_names = {n: net for n, net in modules[top]['netnames'].items() if not net['hide_name']}
    if any(n.startswith(CONE_WIRE) for n in top_names):
        problems.append(f'the harness top already has a net named {CONE_WIRE}*: the cone cover cannot bind its wires')
    todo = []
    for ident in _identifiers(expression):
        if ident not in top_names:
            problems.append(f'{ident} is not a net of the harness top {top}')
            continue
        for bit in top_names[ident]['bits']:
            if isinstance(bit, str):
                problems.append(f'the point reads {ident}, which the harness holds at a constant ({bit})')
            else:
                todo.append(((top,), (), (), bit))

    def harness_module(module):
        return _base(modules, module) not in sources

    def source(kinds_of, scope_path, bit, what):
        _, _, names = _module_maps(modules, kinds_of[-1], memo)
        if bit not in names or any(not _NAME.fullmatch(p) for p in scope_path):
            problems.append(f"{what} in {'.'.join(scope_path) or top} has no plain net name to observe it by")
            return
        name, index = names[bit]
        # After `flatten`, `d.q` is the instance's net only if no module on the way already has a net
        # of that name (an escaped `\d.q ` in the harness would take it and the design's be renamed).
        full = list(scope_path) + [name]
        clash = [kinds_of[j] for j in range(len(scope_path))
                 if '.'.join(full[j:]) in modules[kinds_of[j]]['netnames']]
        if clash:
            problems.append(f"{'.'.join(full)}: module {clash[0]} has a net of the same name, so the "
                            'flattened name is ambiguous')
            return
        signal = '.'.join(full) + ('' if index is None else f'[{index}]')
        if signal not in signals:
            signals.append(signal)

    # A scope is `(module, ...)` with the instance path `(name, ...)` and the instance cells below the top.
    while todo:
        kinds, path, cells, bit = todo.pop()
        if (path, bit) in seen:
            continue
        seen.add((path, bit))
        module = kinds[-1]
        drivers, inputs, _ = _module_maps(modules, module, memo)
        if bit in drivers:
            name, cell, port, i = drivers[bit]
            kind = cell['type']
            if kind in FREE_CELLS:
                source(kinds, path, bit, f'free value {kind}')
            elif kind in modules:
                inner = modules[kind]['ports'][port]['bits'][i]
                if isinstance(inner, str):
                    if inner not in ('0', '1') or harness_module(kind):
                        problems.append(f'output {port} of instance {name} ({_base(modules, kind)}) is the constant {inner}')
                    continue
                todo.append((kinds + (kind,), path + (name,), cells + (cell,), inner))
            elif _is_state(kind):
                if port == 'Q':
                    source(kinds, path, bit, f'register {kind} {name}')
                else:
                    problems.append(f"the point reads {kind} {name} output {port} in {'.'.join(path) or top} "
                                    '(memory data): its change cannot be observed by name')
            elif not kind.startswith('$'):
                problems.append(f'instance {name} of {kind} has no netlist (its cone cannot be read)')
            else:
                directions = cell.get('port_directions', {})
                for p, conn in cell['connections'].items():
                    if directions.get(p) == 'input' and p not in CLOCK_PORTS:
                        todo.extend((kinds, path, cells, b) for b in conn if not isinstance(b, str))
        elif bit in inputs:
            port, i = inputs[bit]
            if not path:
                source(kinds, path, bit, f'input port {port}')
                continue
            outer = cells[-1]['connections'].get(port, [])
            if i >= len(outer):
                problems.append(f"input {port} of instance {'.'.join(path)} is unconnected")
                continue
            if isinstance(outer[i], str):
                if harness_module(kinds[-2]) or outer[i] not in ('0', '1'):
                    problems.append(f"the harness ties input {port} of instance {'.'.join(path)} to the constant "
                                    f'{outer[i]}, which the point reads')
                continue
            todo.append((kinds[:-1], path[:-1], cells[:-1], outer[i]))
        else:
            problems.append(f"the point reads an undriven bit in {'.'.join(path) or top}")
    if not signals and not problems:
        problems.append('the point reads no register, input or free value: nothing shows the harness can drive it')
    return signals, problems


def cone_statement(plan, signals):
    """The cone cover at the point marker: one cover per bit, each reached only when that bit changes
    after the initial step with every reset of the sanity plan inactive."""
    terms = ['!$initstate'] + [f'({r["expression"]})' if r['active_low'] else f'!({r["expression"]})'
                               for r in plan.get('resets') or []]
    return ' '.join(f"cover ({' && '.join(terms)} && !$stable({CONE_WIRE}{i}));" for i in range(len(signals)))


def harness_inputs(netlist, top):
    """Names of the harness top module's input ports, from the elaborated netlist."""
    return sorted(p for p, info in netlist['modules'][top]['ports'].items() if info['direction'] == 'input')


def sanity_plan(config, netlist):
    """The automatic vacuity check: a cover that must be reachable in the same harness, or the
    environment cannot be trusted to exclude anything. It needs the reset to be released and some
    design state to change after the initial step:

        cover (!$initstate && <every reset inactive> && !$stable({state}));

    `netlist` is the harness elaborated by Yosys exactly as the solver reads it (`elaborate`); the
    plan never reads instances or ports from SystemVerilog text. The reset is `reset` (a
    harness-scope expression, with `reset_active_low`) when the config has that key (`"reset": null`
    states that the harness has no reset). Otherwise it is every design instance's reset port
    traced to the harness top (`instance_resets`); if any instance's reset cannot be determined, or
    none has one, or Yosys cannot elaborate the harness, the plan refuses: a renamed reset held
    forever would make every proof vacuous. `sanity_state` (SV expressions) overrides the default
    state: the signals the point expressions read, minus the harness's input ports (a free input
    always changes, so it proves nothing). Every name the state reads must be a net of the
    elaborated harness top: Yosys makes an unknown name a free wire, which always changes."""
    top = config.get('top')
    resets, problems, instances = [], [], []
    bound_record, pinned = None, []
    if 'reset' in config:
        if config['reset'] is not None:
            if not isinstance(config.get('reset_active_low'), bool):
                problems.append('`reset` is stated without `reset_active_low` (true or false): the polarity '
                                'is never guessed')
            resets.append((config['reset'], bool(config.get('reset_active_low'))))
    elaborated = netlist is not None and 'error' not in netlist
    if not elaborated:
        problems.append((netlist or {}).get('error', 'the harness was not elaborated'))
    else:
        if 'reset' not in config:
            resets, instances, problems = instance_resets(netlist, top)
        # Resets that only exist once the harness is bound (round 13). A traced one joins the sanity
        # cover's reset terms. A path it cannot trace refuses unless the plan states `reset`: the
        # stated expression is then the user's account of the resets, as for any reset through logic.
        bound, untraced = bound_resets(netlist, top)
        if 'reset' not in config:
            problems += untraced
        known = {_reset_key(r, low) for r, low in resets}
        for item in bound:
            if (item['expression'], item['active_low']) not in known:
                resets.append((item['expression'], item['active_low']))
                known.add((item['expression'], item['active_low']))
        bound_record, pinned = {"resets": bound, "untraced": untraced}, pinned_state(netlist, top)
    inputs = harness_inputs(netlist, top) if elaborated and top in netlist['modules'] else []
    state = config.get('sanity_state')
    ignored = []
    if state is None:
        state = []
        for point in config['points']:
            for n in _identifiers(point['expression']):
                if n in inputs:
                    if n not in ignored:
                        ignored.append(n)
                elif n not in state:
                    state.append(n)
    for e in [r for r, _ in resets] + list(state):
        if not isinstance(e, str) or any(c in e for c in ';\n\r'):
            raise ValueError('reset and sanity_state must be single SystemVerilog expressions')
    plan = {"reset": resets[0][0] if resets else None, "reset_active_low": resets[0][1] if resets else False,
            "resets": [{"expression": r, "active_low": low} for r, low in resets],
            "instances": instances, "bound": bound_record, "pinned": pinned, "state": list(state),
            "ignored_inputs": ignored, "expression": None}
    if netlist is not None:
        plan["netlist"] = {k: netlist.get(k) for k in ('path', 'sha256', 'script', 'log')}
        plan["dependencies"] = dict(netlist.get('dependencies') or {})
    unresolved = (netlist or {}).get('dependency_problems') or []
    plan["clock"] = (netlist or {}).get("clock")
    # Recompute from the saved raw netlist on import too. The stored clock verdict checks CLK/TRG
    # only and cannot establish that ARST/ALOAD/set/clear or latch events are modelled.
    plan['state_controls'] = {'problems': async_state_problems((netlist or {}).get('modules'))}
    if unresolved:
        plan["error"] = 'unresolved file dependencies: ' + '; '.join(unresolved)
        return plan
    if problems or (not resets and 'reset' not in config):
        why = '; '.join(problems) if problems else 'the harness top module instantiates nothing with a reset port'
        plan["error"] = (f"no reset found in the elaborated harness ({why}): set `reset` to the "
                         "harness's reset expression for the design, or `\"reset\": null` if it has none")
        return plan
    clock = plan['clock']
    if not isinstance(clock, dict) or clock.get('problems') != [] or clock.get('clock') != config.get('clock', 'clk'):
        why = '; '.join((clock or {}).get('problems') or ['missing or mismatched clock probe'])
        plan['error'] = f"unsupported clock model: {why}; every clock/trigger must use the rising edge of " \
            f"{config.get('clock', 'clk')} (sby multiclock off)"
        return plan
    if plan['state_controls']['problems']:
        plan['error'] = 'unsupported asynchronous state model: ' + '; '.join(plan['state_controls']['problems'])
        return plan
    if not state:
        plan["error"] = ("no state signal to check: the point expressions read no signal other than harness "
                         "inputs; set sanity_state")
        return plan
    nets = {n for n, net in netlist['modules'][top]['netnames'].items() if not net['hide_name']} \
        if top in netlist['modules'] else set()
    unknown = [n for e in state for n in _identifiers(e) if n not in nets]
    if unknown:
        plan["error"] = (f"sanity state reads names that are not signals of the harness top {top}: "
                         f"{', '.join(unknown)} (Yosys would make them free wires)")
        return plan
    terms = ['!$initstate'] + [f'({r})' if low else f'!({r})' for r, low in resets]
    terms.append(f"!$stable({{{', '.join(state)}}})")
    plan["expression"] = ' && '.join(terms)
    return plan


def _sby(out, name, mode, depth, timeout, files, top, binds=None, isolated_covers=0):
    """The job file. `binds` (the cone cover) are flattened design signals: `{CONE_WIRE}<i>` is bound to
    the i-th with `connect -set` right after `proc; flatten`, before `prep` cleans unread logic."""
    check_script_paths(files, out)
    check_top(top)
    if not SAFE_BASENAME.fullmatch(name):
        raise ValueError('invalid formal job name')
    if binds and not all(CONE_SIGNAL.fullmatch(s) for s in binds):
        raise ValueError('cone signals must be plain flattened names')
    bind = _cone_bind(top, binds)
    sby = out / f'{name}.sby'
    sby.write_text(_sby_text(mode, depth, timeout, files, top, bind, isolated_covers))
    return sby


def _cone_bind(top, binds):
    if not binds:
        return ''
    return (f'hierarchy -check -top {top}\nproc\nflatten\ncd {top}\n'
            + ''.join(f'connect -set {CONE_WIRE}{i} {s}\n' for i, s in enumerate(binds)) + 'cd ..\n')


def _sby_text(mode, depth, timeout, files, top, bind='', isolated_covers=0):
    # Only the generated sanity/cone covers determine these jobs' aggregate cover status.
    # Lower processes before selection so covers in both the harness and DUT are cells.
    # Keep every assumption and assertion, and every generated per-bit cone cover.
    covers = (f'hierarchy -check -top {top}\nproc\n'
              f'select -assert-count {isolated_covers} {top}/c:rvw_generated_cover_*\n'
              f'chformal -cover -remove {top}/c:rvw_generated_cover_* %n\n') if isolated_covers else ''
    return (f'[options]\nmode {mode}\ndepth {depth}\n'
            f'timeout {int(timeout)}\n\n[engines]\nsmtbmc z3\n\n[script]\n'
            + _read_lines(files) + bind + covers
            + f'prep -top {top}\n\n[files]\n'
            + ''.join(f'{p}\n' for p in files))


def _job_harness(template, statement, isolated_covers):
    if isolated_covers:
        labels = iter(range(isolated_covers))
        statement = re.sub(r'\bcover (?=\()', lambda _: f'rvw_generated_cover_{next(labels)}: cover ', statement)
    return template.replace('// RVW_POINT', statement)


def _run(out, name, mode, statement, template, sources, config, timeout, binds=None, frozen=None,
         isolated_covers=0):
    """One SBY job on the harness with `statement` at the marker; returns its evidence record."""
    if '`' in statement:
        raise ValueError('source snapshot: generated properties cannot contain preprocessor directives or macros')
    job = out / name
    harness = out / f'{name}.sv'
    top = config['top']
    check_top(top)
    if not SAFE_BASENAME.fullmatch(name):
        raise ValueError('invalid formal job name')
    files = sources + [harness]
    check_script_paths(files, out)
    if binds and not all(CONE_SIGNAL.fullmatch(s) for s in binds):
        raise ValueError('cone signals must be plain flattened names')
    # Validate before writing either generated file or starting a tool.
    harness.write_text(_job_harness(template, statement, isolated_covers))
    sby = _sby(out, name, mode, int(config.get("depth", 20)), timeout, files, top, binds, isolated_covers)
    log = out / f'{name}.log'
    tools = config['_tools']
    rc = run_job([tools['sby'], '--yosys', tools['yosys'], '--smtbmc', tools['yosys-smtbmc'],
                  '--witness', tools['yosys-witness'], '-d', str(job), str(sby)], out, log, timeout + 5)
    status = captured.read_text(job / 'status').split()[0] if (job / 'status').exists() else 'ERROR'
    text = captured.read_text(log, errors='replace') if log.exists() else ''
    if binds:  # the cone cover's own placeholders are implicitly declared on purpose
        ours = re.compile(r"[^\n]*\\" + CONE_WIRE + r"(\d+)' is implicitly declared[^\n]*")
        text = ours.sub(lambda m: '' if int(m.group(1)) < len(binds) else m.group(0), text)
    evidence = {"status": status, "exit_code": rc, "directory": str(job),
            "status_sha256": sha256(job / 'status') if (job / 'status').exists() else None,
            "sby": str(sby), "sby_sha256": sha256(sby),
            "harness": str(harness), "harness_sha256": sha256(harness),
            "free_wires": sorted(set(m.group(0) for m in re.finditer(r"[^\n]*(?:" + FREE_WIRE.pattern + r")[^\n]*", text)))}
    if frozen:
        reference, manifest = frozen
        expected = source_snapshot.input_hashes(manifest,
                    [(job / 'src' / p.name, sha256(p)) for p in files])
        source_snapshot.check_inputs(expected, expected)
        evidence.update(snapshot_sha256=reference['sha256'], input_hashes=expected)
    return evidence


@captured.persistent
def prove(config_path, database_path, out, timeout=60):
    given = [Path(os.path.join(os.getcwd(), str(p))) for p in (config_path, database_path)]
    config_item, database_item = captured.current().files(given)
    captured.seed([config_item, database_item])
    config_path, database_path = Path(config_item.resolved), Path(database_item.resolved)
    config_bytes, database_bytes = config_item.copy.read_bytes(), database_item.copy.read_bytes()
    config = json.loads(config_bytes)
    data = json.loads(database_bytes)
    out = Path(out).resolve()
    written = [config_path.parent / s for s in config['sources']] + [config_path.parent / config['harness']]
    sources = [p.resolve() for p in written[:-1]]
    harness_path = written[-1].resolve()
    # Round 15: every name a script holds is checked before anything is written or run.
    check_top(config.get('top'))
    check_top(config.get('clock', 'clk'))
    check_script_paths(sources, out)
    for path in given + written + [harness_path, config_path, database_path]:
        check_script_paths([path], out)

    # Seed resolved aliases from the same captured bytes, including symlink lookups.
    items = captured.current().files(written)
    captured.seed(items)
    hashes = {item.resolved: item.sha256 for item in [config_item, database_item, *items]}
    # Each listed file as written (sources and harness relative to the plan, plan and database as
    # given): a symbolic link retargeted later makes the exclusions stale.
    files = {str(p): captured.record(item, p) for p, item in zip(given + written, [config_item, database_item, *items])}
    points = {p['id']: p for p in data['points']}
    ids = [p['point_id'] for p in config['points']]
    if len(set(ids)) != len(ids):
        raise ValueError('formal plan has duplicate point ids')
    for point in config['points']:
        if '`' in point['expression']:
            raise ValueError('source snapshot: point expressions cannot contain preprocessor directives or macros')
    reference, manifest = source_snapshot.create(out, sources, harness_path, check_script_paths, captured.current())
    for entry in manifest['entries']:
        if entry['opened'] in hashes and entry['record']['sha256'] != hashes[entry['opened']]:
            raise ValueError(f"proof input changed before the source snapshot: {entry['opened']}")
    sources = [Path(p) for p in manifest['sources']]
    template = captured.read_bytes(manifest['harness']).decode('utf-8')
    if template.count('// RVW_POINT') != 1:
        raise ValueError('formal harness must contain exactly one // RVW_POINT marker inside its top module')
    frozen = reference, manifest
    # Vacuity guard: an over-constrained harness (reset held forever, contradictory assumptions)
    # proves every point unreachable. Its sanity cover must be reachable or nothing is excluded.
    # Reuse formal's release-launcher bindings. Pinning only sby/smtbmc is not
    # enough: the release Python launcher prepends its bin directory before
    # smtio resolves `z3`. These bindings preserve the selected solver first.
    try:
        tools = Toolchain(captured.current(), Namespace(engine='smtbmc:z3'), out / 'tool-bindings')
    except CaptureError as exc:
        if exc.cause == 'input_not_captured:tool:yosys-smtbmc':
            raise CaptureError('input_not_captured:tool:z3', str(exc)) from exc
        raise
    captured.current()._coverage_proof_tools = tools
    config['_tools'] = {name: str(tool.path) for name, tool in tools.commands.items()}
    netlist = elaborate(out, sources, template, config['top'], timeout, clock=config.get('clock', 'clk'), yosys=config['_tools']['yosys'])
    # The guard must discover only includes already captured and redirected before it started.
    unexpected = set(netlist.get('dependencies', {})) - {e['path'] for e in manifest['entries']}
    if unexpected:
        raise ValueError(f'guard read files outside the source snapshot: {sorted(unexpected)}')
    netlist['dependencies'] = manifest['dependencies']
    guard_files = sources + [Path(netlist['harness']), Path(netlist['clock_harness'])]
    expected = source_snapshot.input_hashes(manifest,
                [(out / 'guard' / p.name, sha256(p)) for p in guard_files])
    source_snapshot.check_inputs(expected, expected)
    netlist.update(snapshot_sha256=reference['sha256'], input_hashes=expected)
    plan = sanity_plan(config, netlist)
    snapshot = out / 'guard' / 'evidence.json'
    snapshot.write_text(json.dumps({'netlist': netlist, 'config': str(config_path),
                                    'inputs': hashes, 'files': files, 'source_snapshot': reference}, indent=2) + '\n')
    # Files the front end read through `include: resolution records, checked again below.
    depends = plan.get('dependencies') or {}
    if plan.get('expression'):
        sanity = {**plan, **_run(out, 'sanity-cover', 'cover', f"cover ({plan['expression']});", template, sources,
                                 config, timeout, frozen=frozen, isolated_covers=1)}
        sanity['passed'] = sanity['status'] == 'PASS' and sanity['exit_code'] == 0 and not sanity['free_wires'] \
            and not plan['pinned']
        if not sanity['passed']:
            sanity['error'] = ('sanity cover not reached: the harness never releases reset or never changes '
                               'state, so its proofs are vacuous' if sanity['status'] != 'PASS' else
                               'sanity cover reads undeclared or undriven signals (free wires)' if sanity['free_wires']
                               else '; '.join(plan['pinned']))
            if plan['pinned'] and (sanity['status'] != 'PASS' or sanity['free_wires']):
                sanity['error'] = '; '.join([sanity['error']] + plan['pinned'])
    else:
        sanity = {**plan, "passed": False}
    rows = []
    for index, point in enumerate(config['points']):
        pid = point['point_id']
        if pid not in points:
            raise ValueError(f'point {pid} is absent from coverage database')
        if points[pid]['count']:
            raise ValueError(f'point {pid} has simulation hits and cannot be unreachable')
        # A user-selected expression is a reviewed mapping, not automatic cone extraction.
        expression = point['expression']
        if any(c in expression for c in ';\n\r'):
            raise ValueError('point expression must be a single SystemVerilog expression')
        row = {"point_id": pid, "expression": expression, "reason": point['reason'],
               "snapshot_sha256": reference['sha256'],
               "mapping": "user-reviewed-expression", "assumptions": config.get('assumptions', 'See hashed formal harness'),
               "jobs": {}}
        if not plan.get('clock') or plan['clock']['problems'] or plan['state_controls']['problems']:
            row.update(unreachable=False, refused=sanity.get('error', 'clock probe failed'))
            rows.append(row)
            continue
        for mode in ('cover', 'prove'):
            statement = f'cover ({expression});' if mode == 'cover' else f'assert (!({expression}));'
            row['jobs'][mode] = _run(out, f'{index}-{mode}', mode, statement, template, sources, config, timeout,
                                     frozen=frozen)
        proven = (row['jobs']['prove']['status'] == 'PASS' and row['jobs']['prove']['exit_code'] == 0
                  and row['jobs']['cover']['status'] != 'PASS')
        free = row['jobs']['prove']['free_wires'] or row['jobs']['cover']['free_wires']
        row['unreachable'] = proven and sanity['passed'] and not free
        if proven and not row['unreachable']:
            row['refused'] = (sanity.get('error') or 'sanity cover failed') if not sanity['passed'] else \
                'the point expression reads undeclared or undriven signals (free wires)'
        if row['unreachable']:
            # Round 14: the sanity cover shows that some state changes; the point is only excludable
            # when every bit of its own cone can change under the same harness. A hold by reset, tie or
            # assumption on the state the point reads leaves a cone bit stable: refused.
            signals, problems = point_cone(netlist, config['top'], expression)
            row['cone'] = {"signals": signals, "problems": problems}
            if not problems:
                row['cone'].update(_run(out, f'{index}-cone', 'cover', cone_statement(plan, signals), template,
                                        sources, config, timeout, binds=signals, frozen=frozen, isolated_covers=len(signals)))
            row['cone']['passed'] = not problems and row['cone']['status'] == 'PASS' \
                and row['cone']['exit_code'] == 0 and not row['cone']['free_wires']
            if not row['cone']['passed']:
                row['unreachable'] = False
                row['refused'] = ('cannot show that the state the point reads can change: ' + '; '.join(problems)
                                  if problems else
                                  'a signal the point reads never changes under this harness (cone cover '
                                  f"{row['cone']['status']}: held by a reset, a tie or an assumption, or constant "
                                  'within the depth), so the proof may only reflect the environment')
        rows.append(row)
    tools.verify()
    bindings = tools.bindings()
    result = {"schema": EXCLUSIONS_SCHEMA, "point_universe": data['point_universe'],
              "config": str(config_path), "config_sha256": hashes[str(config_path)],
              "work_dir": str(out), "timeout": timeout,
              "source_snapshot": reference,
              "elaboration": {"path": str(snapshot), "sha256": sha256(snapshot)},
              "database": str(database_path), "database_sha256": database_item.sha256,
              "inputs": hashes, "files": files, "dependencies": depends, "sanity": sanity, "points": rows,
              "tools": {name: {"executable": binding['input']['resolved'],
                                "sha256": binding['input']['sha256'],
                                "version": binding['command']['version']}
                        for name, binding in bindings.items()},
              "tool_bindings": bindings, "capture": captured.current().record(), "cache_key": None,
              "replay": ['rvw', 'cov', 'prove', str(database_path), '--config', str(config_path),
                         '--work-dir', str(out) + '-replay', '--timeout', str(timeout), '--json'],
              "note": "Exclusions depend on the reviewed point-expression mapping and hashed harness assumptions."}
    write_json(out / 'exclusions.json', result)
    return result


@captured.command
def apply_exclusions(data, path):
    obj = json.loads(captured.read_text(path))
    if obj.get('schema') != EXCLUSIONS_SCHEMA:
        raise ValueError(f'exclusions have schema {obj.get("schema")}, not {EXCLUSIONS_SCHEMA} (older files do not '
                         'establish the current plan, synchronous-state and source snapshot guards); rerun rvw cov prove')
    if obj['point_universe'] != data['point_universe']:
        raise ValueError('exclusions do not match this coverage point universe')
    if not isinstance(obj.get('dependencies'), dict) or not isinstance(obj.get('files'), dict):
        raise ValueError('exclusions do not record their file dependencies; rerun rvw cov prove')
    for file, expected in obj['inputs'].items():
        if not Path(file).is_file() or sha256(file) != expected:
            raise ValueError(f'stale proof input: {file}')
    # Every included and listed file is looked up again as it was opened: links, target, contents.
    for file, record in list(obj['files'].items()) + list(obj['dependencies'].items()):
        why = stale_record(record) if isinstance(record, dict) and record.get('opened') == file else 'no resolution record'
        if why:
            raise ValueError(f'stale proof input: {file} ({why})')
    # Check RTL for chosen points, rather than requiring an unrelated unit proof
    # to read every source file in a whole-core coverage database.
    excluded_ids = {p['point_id'] for p in obj['points'] if p.get('unreachable')}
    proof_sources = {p['fields'].get('f', '') for p in data['points'] if p['id'] in excluded_ids}
    for name in proof_sources:
        source = data['sources'][name]
        if not source['sha256'] or sha256(source['path']) != source['sha256']:
            raise ValueError(f'coverage source is missing or changed: {source["path"]}')
        listed = obj['files'].get(source['path']) or {}
        if obj['inputs'].get(source['path']) != source['sha256'] and listed.get('sha256') != source['sha256']:
            raise ValueError(f'coverage source was not a proof input: {source["path"]}')
    result = copy.deepcopy(data)
    by_id = {p['id']: p for p in result['points']}
    for item in obj['points']:
        if not item.get('unreachable'):
            continue
        proof = item['jobs']['prove']
        cover = item['jobs']['cover']
        if proof['status'] != 'PASS' or proof['exit_code'] != 0 or cover['status'] == 'PASS' \
                or proof.get('free_wires') or cover.get('free_wires'):
            raise ValueError('only successful unbounded proofs without a conflicting cover witness may exclude points')
        cone = item.get('cone') or {}
        if not cone.get('passed') or cone.get('status') != 'PASS' or cone.get('exit_code') != 0 \
                or cone.get('free_wires') or cone.get('problems') or not cone.get('signals'):
            raise ValueError(f"point {item['point_id']} lacks a passing cone cover (the state it reads must be shown "
                             'to change under the harness); rerun rvw cov prove')
        for job in (proof, cover, cone):
            for file, expected in ((Path(job['directory']) / 'status', job['status_sha256']),
                                   (job['sby'], job['sby_sha256']), (job['harness'], job['harness_sha256'])):
                if sha256(file) != expected:
                    raise ValueError(f'changed proof evidence: {file}')
        point = by_id.get(item['point_id'])
        if point is None or point['count']:
            raise ValueError('excluded point missing or hit in simulation')
        point['exclusion'] = item
    if excluded_ids:
        sanity = obj.get('sanity') or {}
        if not sanity.get('passed') or sanity.get('status') != 'PASS' or sanity.get('exit_code') != 0 \
                or sanity.get('free_wires'):
            raise ValueError('exclusions lack a passing vacuity check (sanity cover); rerun rvw cov prove')
        for file, expected in ((Path(sanity['directory']) / 'status', sanity['status_sha256']),
                               (sanity['sby'], sanity['sby_sha256']), (sanity['harness'], sanity['harness_sha256'])):
            if sha256(file) != expected:
                raise ValueError(f'changed proof evidence: {file}')
    _check_plan_binding(obj)
    return result


def _check_plan_binding(obj):
    """Read-only verification from hashed inputs. No solver or script writer runs on apply.

    A row cannot choose its point or jobs: the plan order fixes the point mapping and job paths.
    Rebuild every property and SBY job and recompute each excluded point's cone from the hashed
    elaboration snapshot. Existing hashes alone would only show that unrelated files were unchanged.
    """
    try:
        config_path = obj['config']
        if obj['inputs'].get(config_path) != obj['config_sha256'] or sha256(config_path) != obj['config_sha256']:
            raise ValueError('config is not a hashed plan input')
        config = json.loads(captured.read_text(config_path))
        out = Path(obj['work_dir'])
        snapshot = obj['elaboration']
        if snapshot['path'] != str(out / 'guard' / 'evidence.json') or sha256(snapshot['path']) != snapshot['sha256']:
            raise ValueError('elaboration snapshot changed')
        saved = json.loads(captured.read_text(snapshot['path']))
        if config_path != saved['config'] or obj['inputs'] != saved['inputs'] or obj['files'] != saved['files']:
            raise ValueError('input records differ from the elaboration snapshot')
        if obj['source_snapshot'] != saved['source_snapshot']:
            raise ValueError('source snapshot differs from the elaboration evidence')
        netlist = saved['netlist']
        if obj['dependencies'] != netlist.get('dependencies', {}):
            raise ValueError('dependency records differ from the elaboration snapshot')
        plan = sanity_plan(config, netlist)
        has_exclusions = any(row.get('unreachable') for row in obj['points'])
        if has_exclusions and (not plan.get('expression') or not plan.get('clock')
                               or plan['clock']['problems'] or plan['pinned']):
            raise ValueError('plan has no passing clock, synchronous-state and sanity guard: '
                             + plan.get('error', 'pinned state'))
        if any(obj['sanity'].get(k) != v for k, v in plan.items()):
            raise ValueError('sanity cover differs from the plan')
        sources = [(Path(config_path).parent / p).resolve() for p in config['sources']]
        harness_path = (Path(config_path).parent / config['harness']).resolve()
        for path in sources + [harness_path]:
            if obj['inputs'].get(str(path)) != sha256(path):
                raise ValueError(f'plan input not hashed: {path}')
        reference = obj['source_snapshot']
        manifest = source_snapshot.verify(reference, sources, harness_path, obj['files'], out, stale_record)
        if obj['dependencies'] != manifest['dependencies']:
            raise ValueError('dependencies differ from the source snapshot')
        sources = [Path(p) for p in manifest['sources']]
        template = captured.read_bytes(manifest['harness']).decode('utf-8')
        guard, clock_guard = Path(netlist['harness']), Path(netlist['clock_harness'])
        if captured.read_bytes(guard).decode('utf-8') != template \
                or captured.read_bytes(clock_guard).decode('utf-8') != template.replace('// RVW_POINT', 'cover (!$initstate);'):
            raise ValueError('guard harness differs from the source snapshot')
        expected_inputs = source_snapshot.input_hashes(manifest,
                            [(out / 'guard' / p.name, sha256(p)) for p in sources + [guard, clock_guard]])
        if netlist['snapshot_sha256'] != reference['sha256']:
            raise ValueError('guard used a different source snapshot')
        source_snapshot.check_inputs(netlist['input_hashes'], expected_inputs)
        rows = obj['points']
        mappings = config['points']
        if len(rows) != len(mappings) or len({p['point_id'] for p in mappings}) != len(mappings):
            raise ValueError('point rows do not match the plan')
        if plan.get('expression'):
            _check_bound_job(obj['sanity'], out, 'sanity-cover', 'cover',
                             f"cover ({plan['expression']});", template, sources, config, obj['timeout'],
                             frozen=(reference, manifest), isolated_covers=1)
        elif 'directory' in obj['sanity']:
            raise ValueError('unexpected sanity job for a refused guard')
        for i, (row, mapping) in enumerate(zip(rows, mappings)):
            if any(row.get(k) != mapping[k] for k in ('point_id', 'expression', 'reason')) \
                    or row.get('snapshot_sha256') != reference['sha256'] \
                    or row.get('mapping') != 'user-reviewed-expression' \
                    or row.get('assumptions') != config.get('assumptions', 'See hashed formal harness'):
                raise ValueError('point row differs from its reviewed plan mapping')
            if not plan.get('clock') or plan['clock']['problems'] or plan['state_controls']['problems']:
                if row['jobs']:
                    raise ValueError('unexpected point jobs for a refused clock or state model')
                continue
            expression = mapping['expression']
            for mode, statement in [('cover', f'cover ({expression});'), ('prove', f'assert (!({expression}));')]:
                _check_bound_job(row['jobs'][mode], out, f'{i}-{mode}', mode, statement,
                                 template, sources, config, obj['timeout'], frozen=(reference, manifest))
            if not row.get('unreachable') and 'cone' not in row:
                continue
            signals, problems = point_cone(netlist, config['top'], expression)
            cone = row['cone']
            if cone['signals'] != signals or cone['problems'] != problems:
                raise ValueError('cone cover differs from the reviewed plan point')
            if problems:
                if row.get('unreachable'):
                    raise ValueError('excluded point has cone problems')
                continue
            _check_bound_job(cone, out, f'{i}-cone', 'cover', cone_statement(plan, signals),
                             template, sources, config, obj['timeout'], binds=signals, frozen=(reference, manifest),
                             isolated_covers=len(signals))
    except (OSError, ValueError, KeyError, TypeError, IndexError) as exc:
        raise ValueError(f'exclusions do not bind to the hashed plan or proof evidence: {exc}; '
                         'rerun rvw cov prove') from exc


def _check_bound_job(job, out, name, mode, statement, template, sources, config, timeout, binds=None, frozen=None,
                     isolated_covers=0):
    if '`' in statement:
        raise ValueError('source snapshot: generated properties cannot contain preprocessor directives or macros')
    harness = out / f'{name}.sv'
    sby = out / f'{name}.sby'
    if job['directory'] != str(out / name) or job['harness'] != str(harness) or job['sby'] != str(sby):
        raise ValueError(f'{name}: job paths do not match the plan index and purpose')
    for file, expected_hash in ((out / name / 'status', job['status_sha256']),
                                (harness, job['harness_sha256']), (sby, job['sby_sha256'])):
        if sha256(file) != expected_hash:
            raise ValueError(f'{name}: changed proof evidence {file}')
    if captured.read_bytes(harness).decode('utf-8') != _job_harness(template, statement, isolated_covers):
        raise ValueError(f'{name}: generated property differs from the plan')
    expected = _sby_text(mode, int(config.get('depth', 20)), timeout, sources + [harness],
                         config['top'], _cone_bind(config['top'], binds), isolated_covers)
    if captured.read_text(sby) != expected:
        raise ValueError(f'{name}: SBY job differs from the plan')
    if captured.read_text(out / name / 'status').split()[0] != job['status']:
        raise ValueError(f'{name}: status differs from proof evidence')
    reference, manifest = frozen
    if job.get('snapshot_sha256') != reference['sha256']:
        raise ValueError(f'{name}: job used a different source snapshot')
    expected_inputs = source_snapshot.input_hashes(manifest,
                        [(out / name / 'src' / p.name, sha256(p)) for p in sources + [harness]])
    source_snapshot.check_inputs(job.get('input_hashes'), expected_inputs)
