"""Regression entry points for native component tests."""
import json

from rvw.sim.backends import BACKENDS, require


def capabilities(a):
    names = [a.backend] if a.backend else BACKENDS
    obj = {name: require(name).to_dict() for name in names}
    print(json.dumps(obj, indent=2))
    return 0


def register(sub):
    p = sub.add_parser('backends', help='show native backend semantic capabilities')
    p.add_argument('--backend', choices=BACKENDS)
    p.add_argument('--json', action='store_true')
    p.set_defaults(func=capabilities)
