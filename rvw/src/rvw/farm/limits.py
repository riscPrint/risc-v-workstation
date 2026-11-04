"""Apply inherited native process limits before exec. No threaded preexec_fn."""
import json
import os
import resource
import sys


FIELDS = {'cpu_seconds': 'RLIMIT_CPU', 'file_bytes': 'RLIMIT_FSIZE',
          'open_files': 'RLIMIT_NOFILE', 'address_space_bytes': 'RLIMIT_AS'}


def validate(limits):
    if not isinstance(limits, dict) or set(limits) - FIELDS.keys():
        raise ValueError('unknown native process limit')
    for name, value in limits.items():
        if type(value) is not int or value <= 0:
            raise ValueError('native process limits must be positive integers')
        if not hasattr(resource, FIELDS[name]) or (name == 'address_space_bytes' and sys.platform != 'linux'):
            raise ValueError(f'unsupported native process limit: {name}')
    return limits


def command(argv, limits):
    validate(limits)
    return [sys.executable, '-m', 'rvw.farm.limits', json.dumps(limits), *argv] if limits else argv


def main():
    limits = validate(json.loads(sys.argv[1]))
    for name, value in limits.items():
        limit = getattr(resource, FIELDS[name])
        _, hard = resource.getrlimit(limit)
        bound = value if hard == resource.RLIM_INFINITY else min(value, hard)
        resource.setrlimit(limit, (bound, bound))
    os.execvp(sys.argv[2], sys.argv[2:])


if __name__ == '__main__':
    main()
