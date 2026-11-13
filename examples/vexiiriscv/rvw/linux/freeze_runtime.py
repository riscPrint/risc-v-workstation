"""Retain the compiled boot runtime so later source builds do not replace it."""
import argparse
import os
from pathlib import Path
import shutil
import zipfile


def freeze(classpath: str, out: Path) -> str:
    sources = [Path(p).resolve(strict=True) for p in classpath.split(os.pathsep) if p]
    if not sources:
        raise ValueError('empty runtime classpath')
    out = out.resolve()
    if any(p.is_dir() and out.is_relative_to(p) for p in sources):
        raise ValueError('runtime output must be outside the classpath directories')
    out.mkdir(parents=True, exist_ok=False)
    entries = []
    for index, source in enumerate(sources):
        target = out / f'entry-{index}.jar'
        if source.is_dir():
            with zipfile.ZipFile(target, 'w', compression=zipfile.ZIP_DEFLATED) as archive:
                for path in sorted(source.rglob('*')):
                    if path.is_file():
                        archive.write(path, path.relative_to(source))
        else:
            shutil.copyfile(source, target)
        entries.append(str(target))
    result = os.pathsep.join(entries)
    (out / 'classpath.txt').write_text(result + '\n')
    return result


if __name__ == '__main__':
    p = argparse.ArgumentParser(__doc__)
    p.add_argument('--classpath', required=True)
    p.add_argument('--out', type=Path, required=True)
    args = p.parse_args()
    print(freeze(args.classpath, args.out))
