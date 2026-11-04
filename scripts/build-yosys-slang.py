#!/usr/bin/env python3
"""Build pinned native slang sources against the selected yosys-config."""
import argparse
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import tarfile
import urllib.request


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--prefix', type=Path, required=True)
    parser.add_argument('--yosys-config', default=shutil.which('yosys-config'))
    args = parser.parse_args()
    if not args.yosys_config:
        parser.error('yosys-config is required')
    prefix = args.prefix.absolute()
    source = prefix / 'src/yosys-slang'
    downloads = prefix / 'downloads'
    downloads.mkdir(parents=True, exist_ok=True)
    sources = json.loads(Path(__file__).with_name('yosys-slang-sources.json').read_text())
    for item in sources:
        archive = downloads / (item['name'] + '-' + item['revision'] + '.tar.gz')
        if not archive.exists():
            with urllib.request.urlopen(item['url'], timeout=120) as response:
                archive.write_bytes(response.read())
        if hashlib.sha256(archive.read_bytes()).hexdigest() != item['sha256']:
            raise SystemExit(f'archive checksum mismatch: {archive}')
        target = source / item['path']
        # Always extract sealed bytes. Never compile a modified prior source tree.
        if target.exists():
            shutil.rmtree(target)
        target.mkdir(parents=True)
        with tarfile.open(archive) as tar:
            members = tar.getmembers()
            base = members[0].name.split('/')[0]
            for member in members:
                member.name = member.name.removeprefix(base + '/')
                if member.name == base:
                    continue
                tar.extract(member, target, filter='data')
    # Upstream accepts --all-deps but does not write it from the Yosys entry point.
    driver = source / 'src/yosys_plugin/driver.cc'
    text = driver.read_text()
    marker = '\t\t\tauto compilation = driver.createCompilation();'
    if text.count(marker) != 1:
        raise SystemExit('unexpected pinned slang driver layout')
    driver.write_text(text.replace(marker, '\t\t\tdriver.optionallyWriteDepFiles();\n' + marker))
    patch = Path(__file__).with_name('patches') / 'slang-overlap.patch'
    subprocess.run(['patch', '-p1', '--input', str(patch.resolve())], cwd=source, check=True)
    build = prefix / 'build/yosys-slang'
    if build.exists():
        shutil.rmtree(build)
    subprocess.run(['cmake', '-S', str(source), '-B', str(build),
                    '-DCMAKE_BUILD_TYPE=Release', f'-DYOSYS_CONFIG={args.yosys_config}',
                    '-DYOSYS_SLANG_REVISION=' + sources[0]['revision'],
                    '-DSLANG_REVISION=' + sources[1]['revision'],
                    '-DSLANG_INCLUDE_TESTS=OFF', '-DSLANG_INCLUDE_TOOLS=OFF',
                    '-DSLANG_INCLUDE_INSTALL=OFF',
                    '-DFETCHCONTENT_SOURCE_DIR_BOOST_REGEX=' + str(source / 'third_party/regex'),
                    '-DFETCHCONTENT_FULLY_DISCONNECTED=ON'], check=True)
    subprocess.run(['nice', '-n', '10', 'cmake', '--build', str(build), '-j2'], check=True)
    plugin = prefix / 'lib/slang.so'
    plugin.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(build / 'slang.so', plugin)
    yosys = str(Path(args.yosys_config).parent / 'yosys')
    subprocess.run([yosys, '-Q', '-T', '-m', str(plugin), '-p', 'help read_slang'],
                   check=True, stdout=subprocess.DEVNULL)
    print(f'Built native plugin: {plugin}')


if __name__ == '__main__':
    main()
