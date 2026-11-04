#!/usr/bin/env python3
"""Package the pinned viewer as a macOS application."""
import argparse
import plistlib
import re
import shutil
import subprocess
from pathlib import Path


def package(binary, notices, app, manifest):
    version = re.search(r'^version\s*=\s*"([^"]+)"', manifest.read_text(), re.M)[1]
    contents = app / "Contents"
    (contents / "MacOS").mkdir(parents=True, exist_ok=True)
    resources = contents / "Resources"
    resources.mkdir(exist_ok=True)
    executable = contents / "MacOS/surfer-tywaves"
    shutil.copy2(binary, executable)
    executable.chmod(0o755)
    for name in ("LICENSE-EUPL-1.2.txt", "vendor-lock.json", "source.tar.gz"):
        shutil.copy2(notices / name, resources / name)
    with (contents / "Info.plist").open("wb") as stream:
        plistlib.dump({
            "CFBundleIdentifier": "org.riscprint.spinalwaves",
            "CFBundleName": "SpinalWaves",
            "CFBundleDisplayName": "SpinalWaves",
            "CFBundleExecutable": "surfer-tywaves",
            "CFBundlePackageType": "APPL",
            "CFBundleInfoDictionaryVersion": "6.0",
            "CFBundleShortVersionString": version.split("-")[0],
            "CFBundleVersion": version.split("-")[0],
            "SpinalWavesForkVersion": version,
            "NSHighResolutionCapable": True,
        }, stream)
    subprocess.run(["codesign", "--force", "--sign", "-", str(app)], check=True)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("binary", type=Path)
    parser.add_argument("notices", type=Path)
    parser.add_argument("app", type=Path)
    args = parser.parse_args()
    package(args.binary, args.notices, args.app,
            Path(__file__).resolve().parents[1] / "surfer-tywaves/Cargo.toml")
