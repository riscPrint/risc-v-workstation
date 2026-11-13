#!/usr/bin/env python3
"""Build the GHDL Yosys plugin against the selected Yosys and the libghdl beside `ghdl`.

Some OSS CAD Suite builds ship a ghdl.so made for another Yosys memory-cell API: VHDL
memories then fail Yosys' cell check. This rebuilds a pinned plugin revision with the GHDL
C headers of the exact libghdl commit (read from `ghdl --version`). Sources are fetched
outside the checkout. Prints `export RVW_GHDL_PLUGIN=...` on success."""
import argparse
import hashlib
from pathlib import Path
import re
import shlex
import shutil
import subprocess
import sys
import tarfile
import urllib.request

# Tested with OSS CAD Suite 2026-05-01 (Yosys 0.64+174, GHDL 4.1.0.r1379.gbababe6b1).
# Later plugin revisions need the libghdl Sname_Index API (GHDL from 2026-03) and Yosys 0.70.
PLUGIN_REV = '07a30ed39fb6a078f1bf7e9e88ce9ed712380ec2'


def fetch(url, target):
    if not target.exists():
        with urllib.request.urlopen(url, timeout=120) as response:
            target.write_bytes(response.read())
    return target


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--prefix', type=Path, default=Path.home() / '.cache/rvw')
    parser.add_argument('--yosys-config', default=shutil.which('yosys-config'))
    parser.add_argument('--ghdl', default=shutil.which('ghdl'))
    parser.add_argument('--plugin-rev', default=PLUGIN_REV)
    parser.add_argument('--cxx', default=shutil.which('c++') or 'clang++')
    args = parser.parse_args()
    if not args.yosys_config or not args.ghdl:
        parser.error('yosys-config and ghdl are required (source the OSS CAD Suite environment)')
    version = subprocess.run([args.ghdl, '--version'], capture_output=True, text=True, check=True).stdout
    match = re.search(r'\.g([0-9a-f]{7,40})\b', version)
    if not match:
        raise SystemExit(f'cannot read the GHDL commit from: {version.splitlines()[0]}')
    ghdl_rev = match[1]
    library = Path(subprocess.run([args.ghdl, '--libghdl-library-path'], capture_output=True, text=True,
                                  check=True).stdout.strip())
    if not library.is_file():
        # Relocated OSS CAD Suite trees report libexec/lib; the library is in lib/.
        candidates = sorted((Path(args.ghdl).resolve().parents[1] / 'lib').glob('libghdl-*.dylib')) + \
            sorted((Path(args.ghdl).resolve().parents[1] / 'lib').glob('libghdl-*.so'))
        if not candidates:
            raise SystemExit(f'libghdl not found: {library}')
        library = candidates[0]
    root = args.prefix.absolute() / 'src' / f'ghdl-yosys-plugin-{args.plugin_rev[:12]}-{ghdl_rev}'
    downloads = args.prefix.absolute() / 'downloads'
    downloads.mkdir(parents=True, exist_ok=True)
    archive = fetch(f'https://github.com/ghdl/ghdl-yosys-plugin/archive/{args.plugin_rev}.tar.gz',
                    downloads / f'ghdl-yosys-plugin-{args.plugin_rev}.tar.gz')
    if root.exists():
        shutil.rmtree(root)
    (root / 'include/ghdl').mkdir(parents=True)
    with tarfile.open(archive) as tar:
        for member in tar.getmembers():
            member.name = member.name.split('/', 1)[1] if '/' in member.name else ''
            if member.name:
                tar.extract(member, root, filter='data')
    for header in ('synth.h', 'synth_gates.h'):
        fetch(f'https://raw.githubusercontent.com/ghdl/ghdl/{ghdl_rev}/src/synth/include/{header}',
              root / 'include/ghdl' / header)
    flags = subprocess.run([args.yosys_config, '--cxxflags'], capture_output=True, text=True, check=True).stdout
    flags = [f for f in shlex.split(flags) if f not in ('-ggdb', '-MD', '-MP')]
    objects = []
    for source in sorted((root / 'src').glob('*.cc')):
        obj = root / (source.stem + '.o')
        subprocess.run(['nice', '-n', '10', args.cxx, '-c', *flags, '-w', '-fPIC', '-DYOSYS_ENABLE_GHDL',
                        f'-I{root / "include"}', f'-DGHDL_VER_HASH="{args.plugin_rev[:7]}"',
                        '-o', str(obj), str(source)], check=True)
        objects.append(str(obj))
    plugin = args.prefix.absolute() / 'lib' / 'ghdl.so'
    plugin.parent.mkdir(parents=True, exist_ok=True)
    # Yosys symbols resolve at load time from the yosys executable.
    lazy = ['-undefined', 'dynamic_lookup'] if sys.platform == 'darwin' else []
    subprocess.run([args.cxx, '-shared', *lazy, '-o', str(plugin), *objects,
                    str(library), f'-Wl,-rpath,{library.parent}'], check=True)
    yosys = str(Path(args.yosys_config).parent / 'yosys')
    subprocess.run([yosys, '-Q', '-T', '-m', str(plugin), '-p', 'help ghdl'], check=True,
                   stdout=subprocess.DEVNULL)
    digest = hashlib.sha256(plugin.read_bytes()).hexdigest()
    print(f'Built GHDL plugin {plugin} (sha256 {digest}, plugin {args.plugin_rev[:12]}, ghdl {ghdl_rev})')
    print(f'export RVW_GHDL_PLUGIN={shlex.quote(str(plugin))}')


if __name__ == '__main__':
    main()
