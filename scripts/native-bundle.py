#!/usr/bin/env python3
"""Pack and install private native tool artifacts. Python standard library only."""
import argparse
import hashlib
import json
import platform
import re
import shutil
import subprocess
import tarfile
import tempfile
from pathlib import Path

TOOLS = ('verilator', 'spike', 'sail', 'gem5', 'gcc')


def host():
    arch = {'aarch64': 'arm64', 'arm64': 'arm64', 'x86_64': 'x86_64'}.get(platform.machine())
    os_name = {'Darwin': 'macos', 'Linux': 'linux'}.get(platform.system())
    if (os_name, arch) not in (('macos', 'arm64'), ('linux', 'x86_64'), ('linux', 'arm64')):
        raise ValueError('No bundle for this host')
    return f'{os_name}-{arch}'


def digest(path):
    with path.open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def pin(home, tool):
    if tool == 'sail':
        return digest(home / 'scripts/install-sail.sh')
    text = (home / 'scripts/install.sh').read_text()
    return re.search(rf'^{tool}_revision=([a-f0-9]{{40}})$', text, re.M)[1]


def pack(home, tool, source, output):
    output.mkdir(parents=True, exist_ok=True)
    name = f'{tool}-{host()}'
    archive = output / f'{name}.tar.gz'
    with tempfile.TemporaryDirectory() as directory:
        stage = Path(directory)
        shutil.copytree(source, stage / tool, symlinks=False)
        metadata = {'schema': 'rvw.native-bundle/1', 'tool': tool, 'host': host(),
                    'pin': pin(home, tool),
                    'shim_source': digest(home / 'Cosim/spike_shim.cc') if tool == 'spike' else None}
        (stage / 'bundle.json').write_text(json.dumps(metadata) + '\n')
        with tarfile.open(archive, 'w:gz', dereference=True) as tar:
            tar.add(stage / tool, arcname=tool)
            tar.add(stage / 'bundle.json', arcname='bundle.json')
    archive.with_suffix(archive.suffix + '.sha256').write_text(digest(archive) + '\n')


def unpack(home, tool, directory, stage):
    archive = directory / f'{tool}-{host()}.tar.gz'
    checksum = archive.with_suffix(archive.suffix + '.sha256').read_text().strip()
    if not re.fullmatch('[a-f0-9]{64}', checksum) or digest(archive) != checksum:
        raise ValueError(f'{tool}: archive checksum mismatch')
    with tarfile.open(archive) as tar:
        # Our packer emits only directories and regular files, including dereferenced links.
        for member in tar.getmembers():
            path = Path(member.name)
            if (path.is_absolute() or '..' in path.parts or not path.parts
                    or path.parts[0] not in (tool, 'bundle.json')
                    or not (member.isfile() or member.isdir())):
                raise ValueError(f'{tool}: invalid archive member {member.name}')
        tar.extractall(stage, filter='data')
    metadata = json.loads((stage / 'bundle.json').read_text())
    if (metadata['schema'] != 'rvw.native-bundle/1' or metadata['tool'] != tool
            or metadata['host'] != host() or metadata['pin'] != pin(home, tool)):
        raise ValueError(f'{tool}: bundle identity does not match this checkout')
    if tool == 'spike' and metadata['shim_source'] != digest(home / 'Cosim/spike_shim.cc'):
        raise ValueError('Spike shim source does not match this checkout')


def install(home, selected, directory=None, run=None):
    if not selected:
        raise ValueError('Select at least one native tool flag')
    if directory and run:
        raise ValueError('Use --bundle-dir or --bundle-run, not both')
    if run and not run.isdecimal():
        raise ValueError('Actions run ID must be numeric')
    if not directory and not run:
        raise ValueError('Select an explicit Actions run or local directory')
    with tempfile.TemporaryDirectory(prefix='rvw-native-') as temporary:
        work = Path(temporary)
        prepared = []
        for tool in selected:
            download = Path(directory) if directory else work / f'download-{tool}'
            if not directory:
                subprocess.run(['gh', 'run', 'download', run, '--repo',
                                'riscPrint/risc-v-workstation', '--name', f'{tool}-{host()}',
                                '--dir', str(download)], check=True)
            stage = work / tool
            stage.mkdir()
            unpack(home, tool, download, stage)
            prepared.append((tool, stage / tool))
        # Validate all requested archives before replacing any installed tool.
        for tool, source in prepared:
            destination = home / '.tools' / ('riscv' if tool == 'gcc' else tool)
            destination.parent.mkdir(parents=True, exist_ok=True)
            if destination.is_symlink():
                destination.unlink()
            elif destination.exists():
                shutil.rmtree(destination)
            shutil.copytree(source, destination)
            if tool == 'spike':
                shim = destination / 'rvw-shim/librvw_spike.so'
                manifest = shim.with_name(shim.name + '.manifest.json')
                data = json.loads(manifest.read_text())
                # Static Spike bytes travel unchanged. Preserve the embedded build identity.
                data['spike_library'] = str(destination / 'lib/libriscv.a')
                data['spike_headers'] = str(destination / 'include/riscv')
                manifest.write_text(json.dumps(data, indent=2) + '\n')
                target = home / 'Cosim/build'
                target.mkdir(parents=True, exist_ok=True)
                shutil.copy2(shim, target / shim.name)
                shutil.copy2(manifest, target / manifest.name)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest='command', required=True)
    create = commands.add_parser('pack')
    create.add_argument('--home', type=Path, required=True)
    create.add_argument('--tool', choices=TOOLS, required=True)
    create.add_argument('--source', type=Path, required=True)
    create.add_argument('--output', type=Path, required=True)
    get = commands.add_parser('install')
    get.add_argument('--home', type=Path, required=True)
    get.add_argument('--tool', choices=TOOLS, action='append', default=[])
    location = get.add_mutually_exclusive_group(required=True)
    location.add_argument('--directory', type=Path)
    location.add_argument('--run')
    args = parser.parse_args()
    try:
        if args.command == 'pack':
            pack(args.home, args.tool, args.source, args.output)
        else:
            install(args.home, args.tool, args.directory, args.run)
    except (OSError, ValueError, KeyError, tarfile.TarError, subprocess.CalledProcessError) as exc:
        parser.exit(2, f'native-bundle: {exc}\n')


if __name__ == '__main__':
    main()
