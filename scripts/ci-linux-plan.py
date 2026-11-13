#!/usr/bin/env python3
"""Print the tier's inventory apt recipe. Linux CI remains untested."""
import argparse
import json
from pathlib import Path
import shlex
ROOT = Path(__file__).resolve().parents[1]


def packages(tier):
    tiers = json.loads((ROOT / 'scripts/ci-tiers.json').read_text())
    tools = json.loads((ROOT / 'rvw/src/rvw/doctor/tools.json').read_text())['tools']
    return sorted({p for tool in tools if tool['name'] in tiers[tier]['tools'] for p in shlex.split(tool['install']['apt'])})


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--tier', choices=['fast', 'native-light', 'examples', 'nightly'], required=True)
    parser.add_argument('--packages', action='store_true')
    args = parser.parse_args()
    print(' '.join(packages(args.tier)) if args.packages else 'Linux untested. Inventory apt packages: ' + ' '.join(packages(args.tier)))


if __name__ == '__main__':
    main()
