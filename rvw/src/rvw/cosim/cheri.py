"""Configuration hook for optional CHERI reference assessment, not a checker."""
import re

REFERENCE = 'https://github.com/CTSRD-CHERI/sail-cheri-riscv'
REVISION = 'cf36cfd4fca0bd10a5906651bf48b9674ccd0a2b'
CAPABILITY_FIELDS = ('tag', 'base', 'top', 'permissions', 'sealed', 'otype', 'offset')
FAULT_FIELDS = ('cause', 'tval', 'cap_cause', 'cap_index')


def validate(config):
    if config is None:
        return None
    if not isinstance(config, dict) or set(config) != {'repository', 'revision', 'capability_bits'}:
        raise ValueError('cheri requires repository, revision and capability_bits')
    if not isinstance(config['repository'], str) or not config['repository']:
        raise ValueError('CHERI reference repository is required')
    if not isinstance(config['revision'], str) or not re.fullmatch('[0-9a-f]{40}', config['revision']):
        raise ValueError('CHERI reference requires a pinned commit')
    if type(config['capability_bits']) is not int or config['capability_bits'] not in (64, 128, 256):
        raise ValueError('unsupported CHERI capability width')
    return dict(config)
