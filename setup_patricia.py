#!/usr/bin/env python3
"""Install the pinned Patricia 5.1 engine into runtime/ (no root needed).

Official release binaries are used on Windows and Linux x86_64 (SHA-256
verified). Other platforms compile the pinned source commit, mirroring
the engine's own Makefile targets.
"""
import hashlib
import json
import os
from pathlib import Path
import platform
import shutil
import subprocess
import sys
import tarfile
import tempfile
import urllib.request

ROOT = Path(__file__).resolve().parent
RUNTIME = ROOT / 'runtime'
VERSION = '5.1'
COMMIT = '67d83d7056801cfab868872d27b99d192488a316'
RELEASE = f'https://github.com/Adam-Kulju/Patricia/releases/download/{VERSION}'
ASSETS = {
    ('Windows', 'x86_64'): ('patricia_v2.exe',
                            '5b3e90932771c218babf2c12ea55af8389f7bef1e5fc6c391d9415f86b4fff51'),
    ('Linux', 'x86_64'): ('patricia_v2',
                          '33f7800a7febe76ba31e2e7ae39e56c17d2f7eefa24e332c866c4c1d178a7889'),
}


def download(url, target, digest):
    target.parent.mkdir(parents=True, exist_ok=True)
    temp = target.with_suffix(target.suffix + '.part')
    with urllib.request.urlopen(url, timeout=120) as response, temp.open('wb') as out:
        shutil.copyfileobj(response, out)
    if hashlib.sha256(temp.read_bytes()).hexdigest() != digest:
        temp.unlink(missing_ok=True)
        raise ValueError(f'SHA-256 mismatch: {target.name}')
    temp.replace(target)


def build_from_source(target):
    url = f'https://github.com/Adam-Kulju/Patricia/archive/{COMMIT}.tar.gz'
    with tempfile.TemporaryDirectory() as folder:
        archive = Path(folder) / 'patricia.tar.gz'
        with urllib.request.urlopen(url, timeout=120) as response, archive.open('wb') as out:
            shutil.copyfileobj(response, out)
        with tarfile.open(archive) as package:
            package.extractall(folder, filter='data')
        engine = next(Path(folder).glob('Patricia-*/engine'))
        target_name = 'aarch64' if platform.machine() in ('aarch64', 'arm64') else 'build'
        subprocess.run(['make', target_name], cwd=engine, check=True)
        built = engine / ('patricia_aarch64' if target_name == 'aarch64' else 'patricia')
        shutil.copy2(built, target)


def main():
    system = platform.system()
    arch = {'AMD64': 'x86_64', 'x64': 'x86_64'}.get(platform.machine(), platform.machine())
    target = RUNTIME / ('patricia.exe' if system == 'Windows' else 'patricia')
    asset = ASSETS.get((system, arch))
    if asset and not target.exists():
        name, digest = asset
        print(f'Downloading Patricia {VERSION} ({name})', flush=True)
        download(f'{RELEASE}/{name}', target, digest)
    elif not target.exists():
        print(f'Building Patricia {VERSION} from pinned source ({COMMIT[:12]})', flush=True)
        build_from_source(target)
    target.chmod(target.stat().st_mode | 0o111)
    digest = hashlib.sha256(target.read_bytes()).hexdigest()
    (RUNTIME / 'patricia-install.json').write_text(json.dumps(
        {'version': VERSION, 'commit': COMMIT, 'sha256': digest}, indent=2))
    print(f'Patricia ready: {target}')


if __name__ == '__main__':
    main()
