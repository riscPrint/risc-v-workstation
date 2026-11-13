#!/usr/bin/env python3
"""Select CI jobs from changed paths. Unknown code gets the Python checks."""
import argparse
import os
import subprocess


def select(paths):
    jobs = dict.fromkeys(('python', 'javascript', 'rust', 'scala'), False)
    for path in paths:
        if path.startswith(('.github/', 'scripts/ci', 'rvw/pyproject', 'rvw/uv.lock')):
            return dict.fromkeys(jobs, True)
        if path.startswith(('vscode/', 'SpinalBlocks/engine/', 'SpinalBlocks/hosts/')):
            jobs['javascript'] = True
        elif path.startswith('SpinalTrace/') and not path.endswith('.md'):
            jobs['rust'] = True
            jobs['scala'] |= path.endswith(('.scala', '.sbt'))
        elif path.endswith(('.scala', '.sbt')) or '/project/' in path:
            jobs['scala'] = True
        elif not path.endswith(('.md', '.png', '.svg', '.jpg')) and not path.startswith('docs/'):
            jobs['python'] = True
    return jobs


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--base')
    parser.add_argument('--head', default='HEAD')
    args = parser.parse_args()
    paths = subprocess.check_output(['git', 'diff', '--name-only', '-z', args.base, args.head]).decode().split('\0') if args.base else ['scripts/ci-local.sh']
    values = select([p for p in paths if p])
    text = ''.join(f'{key}={str(value).lower()}\n' for key, value in values.items())
    print(text, end='')
    if os.environ.get('GITHUB_OUTPUT'):
        with open(os.environ['GITHUB_OUTPUT'], 'a') as stream:
            stream.write(text)


if __name__ == '__main__':
    main()
