#!/usr/bin/env python3
"""Import an explicit SystemRDL or IP-XACT register-map subset. Fail on unsupported semantics."""
import argparse
from pathlib import Path
import xml.etree.ElementTree as ET


def integer(text):
    return int(text, 0) if text.lower().startswith(('0x', '0b', '0o')) else int(text)


def pack(name, address, width, fields):
    reset = write = w1c = rc = occupied = 0
    for offset, size, value, access, onwrite, onread in fields:
        mask = ((1 << size) - 1) << offset
        if size <= 0 or offset < 0 or offset + size > width or occupied & mask:
            raise ValueError('overlapping or out-of-range field')
        if value < 0 or value >= 1 << size:
            raise ValueError('reset does not fit field')
        if access not in ('r', 'rw', 'w') or onwrite not in (None, 'woclr') or onread not in (None, 'rclr'):
            raise ValueError('unsupported field access or side effect')
        if onwrite and access == 'r' or onread and access == 'w':
            raise ValueError('side effect conflicts with access')
        occupied |= mask
        reset |= value << offset
        if access in ('rw', 'w'):
            if onwrite == 'woclr':
                w1c |= mask
            else:
                write |= mask
        if onread == 'rclr':
            rc |= mask
    return name, dict(address=address, width=width, reset=reset, writeMask=write, w1cMask=w1c, readClearMask=rc)


def ipxact(path):
    root = ET.parse(path).getroot()
    for node in root.iter():
        node.tag = node.tag.split('}')[-1]
    supported = {'component', 'vendor', 'library', 'name', 'version', 'memoryMaps', 'memoryMap',
                 'addressBlock', 'baseAddress', 'range', 'width', 'usage', 'register', 'addressOffset',
                 'size', 'access', 'field', 'bitOffset', 'bitWidth', 'modifiedWriteValue', 'readAction',
                 'resets', 'reset', 'value', 'addressUnitBits', 'description', 'displayName', 'volatile'}
    if any(n.tag not in supported for n in root.iter()):
        raise ValueError('unsupported IP-XACT element')
    def value(node, tag, default=None):
        found = node.find(tag)
        return default if found is None else found.text.strip()
    unsupported = {'registerFile', 'dim', 'alternateRegisters', 'bank', 'writeConstraint', 'vendorExtensions',
                   'parameters', 'isPresent', 'resetMask', 'aliasOf', 'accessPolicies', 'enumeratedValues'}
    if any(n.tag in unsupported for n in root.iter()):
        raise ValueError('unsupported IP-XACT construct')
    result = []
    for mm in root.findall('.//memoryMap'):
        if value(mm, 'addressUnitBits', '8') != '8':
            raise ValueError('only byte address units are supported')
    for block in root.findall('.//addressBlock'):
        if value(block, 'usage', 'register') != 'register':
            raise ValueError('only register address blocks are supported')
        base = integer(value(block, 'baseAddress'))
        for reg in block.findall('register'):
            width = integer(value(reg, 'size'))
            if any(reg.find(t) is not None for t in ('reset', 'resets', 'modifiedWriteValue', 'readAction')):
                raise ValueError('put reset and side effects on explicit fields')
            fields = []
            for f in reg.findall('field'):
                access = value(f, 'access', value(reg, 'access', 'read-write'))
                access = {'read-only': 'r', 'read-write': 'rw', 'write-only': 'w'}.get(access, access)
                ow = value(f, 'modifiedWriteValue')
                ow = {'oneToClear': 'woclr'}.get(ow, ow)
                read = value(f, 'readAction')
                read = {'clear': 'rclr'}.get(read, read)
                if len(f.findall('resets/reset')) != 1 or f.find('resets/reset/mask') is not None:
                    raise ValueError('one complete explicit reset per field is required')
                fields.append((integer(value(f, 'bitOffset')), integer(value(f, 'bitWidth')),
                               integer(value(f, 'resets/reset/value')), access, ow, read))
            if not fields:
                raise ValueError('explicit fields are required')
            result.append(pack(value(reg, 'name'), base + integer(value(reg, 'addressOffset')), width, fields))
    return result


def systemrdl(path):
    from systemrdl import RDLCompiler
    from systemrdl.node import RegNode, FieldNode
    compiler = RDLCompiler()
    compiler.compile_file(str(path))
    root = compiler.elaborate()
    result = []
    for reg in root.descendants(unroll=True):
        if not isinstance(reg, RegNode):
            continue
        fields = []
        for f in reg.fields():
            for prop in ('hwset', 'hwclr', 'counter', 'singlepulse', 'swwe', 'swwel', 'swmod', 'swacc'):
                if f.get_property(prop):
                    raise ValueError(f'unsupported SystemRDL property {prop}')
            enum = lambda x: None if x is None else x.name
            reset = f.get_property('reset')
            if reset is None or not isinstance(reset, int):
                raise ValueError('explicit integer field reset is required')
            fields.append((f.low, f.width, reset, enum(f.get_property('sw')),
                           enum(f.get_property('onwrite')), enum(f.get_property('onread'))))
        result.append(pack(reg.get_path().replace('[', '_').replace(']', ''), reg.absolute_address,
                           reg.get_property('regwidth'), fields))
    return result


def convert(path, fmt):
    registers = (ipxact if fmt == 'ipxact' else systemrdl)(path)
    if not registers:
        raise ValueError('no registers')
    names = [n for n, _ in registers]
    import re
    if len(set(names)) != len(names) or any(not re.fullmatch(r'[A-Za-z_][A-Za-z0-9_.]*', n) for n in names):
        raise ValueError('duplicate or unsupported register name')
    lines = ['version=1', 'registers=' + ','.join(names)]
    for name, values in registers:
        lines.extend(f'{name}.{k}={v}' for k, v in values.items())
    return '\n'.join(lines) + '\n'


if __name__ == '__main__':
    parser = argparse.ArgumentParser(__doc__)
    parser.add_argument('format', choices=('systemrdl', 'ipxact'))
    parser.add_argument('input', type=Path)
    parser.add_argument('output', type=Path)
    args = parser.parse_args()
    args.output.write_text(convert(args.input, args.format))
