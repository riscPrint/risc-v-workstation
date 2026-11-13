"""Spinal enum types for wave values, from a SpinalDB design database.

SpinalDB stores an enum signal's type as `<enum>@<encoding>[<width>]{<element>=<value hex>,...}`
(`State@seq[2]{idle=0,run=1}`). These helpers map wave signal names to their elements so
queries can print `run` instead of `0x1` and expressions can compare with `'run'`.
"""
from __future__ import annotations

import re

from .vcd import WaveError

_ENUM = re.compile(r'^(?P<name>[^@]+)@(?P<encoding>[^\[]+)\[(?P<width>\d+)\]\{(?P<elements>.*)\}$')


def parse_enum(type_text: str | None) -> dict | None:
    m = _ENUM.match(type_text or '')
    if not m:
        return None
    elements = {}
    for part in m.group('elements').split(','):
        if '=' not in part:
            continue
        name, value = part.rsplit('=', 1)
        try:
            elements[name.strip()] = int(value.strip(), 16)
        except ValueError:
            return None
    return {'enum': m.group('name'), 'encoding': m.group('encoding'), 'elements': elements,
            'names': {v: k for k, v in elements.items()}}


def enums(database: str) -> dict[str, dict]:
    """{wave signal name: enum info} for every enum-typed signal in the database."""
    from ..query.db import DesignDB, QueryError
    try:
        db = DesignDB(database)
    except QueryError as exc:
        raise WaveError(f'cannot open design database: {exc}') from exc
    try:
        out = {}
        for path, type_text in db.q("SELECT path, type FROM signals WHERE type LIKE '%@%{%' AND pruned=0"):
            info = parse_enum(type_text)
            if info:
                out[db.wave_path(path)] = info
        return out
    finally:
        db.close()


def label(info: dict | None, value: str | None) -> str | None:
    """Element name of a formatted value (`0x1`, `1`), or None when not an element / unknown."""
    if not info or value is None:
        return None
    try:
        n = int(value, 0)
    except ValueError:
        return None
    return info['names'].get(n)


def annotate_changes(page: dict, info: dict[str, dict]) -> dict:
    """Add `enum` element names to `changes` rows of enum-typed signals."""
    for row in page.get('changes', []):
        name = label(info.get(row['signal']), row['value'])
        if name is not None:
            row['enum'] = name
    return page


def annotate_sample(values: dict, info: dict[str, dict]) -> dict:
    """{signal: element name} for enum-typed signals in a `sample` result."""
    out = {}
    for k, v in values.items():
        name = label(info.get(k), v)
        if name is not None:
            out[k] = name
    return out
