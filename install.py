#!/usr/bin/env python3
"""Install dependencies and an official Stockfish binary without root access."""
import argparse
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
import venv
import zipfile

ROOT = Path(__file__).resolve().parent


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--stockfish', type=Path, help='Use an existing local Stockfish binary')
    parser.add_argument('--install-browser', action='store_true', help='Also download Chromium with Playwright')
    parser.add_argument('--with-maia3', action='store_true', help='Also install Maia-3 5M and its CPU runtime')
    parser.add_argument('--with-lc0', action='store_true', default=True, help='Install the CPU runtime for fixed Elo levels (default)')
    parser.add_argument('--skip-lc0', action='store_false', dest='with_lc0', help='Dependencies only; fixed levels will be unavailable')
    args = parser.parse_args()
    env_dir = ROOT / '.venv'
    python = env_dir / ('Scripts/python.exe' if os.name == 'nt' else 'bin/python')
    if not python.exists():
        venv.EnvBuilder(with_pip=True, system_site_packages=True).create(env_dir)
    runtime = ROOT / 'runtime'
    runtime.mkdir(exist_ok=True)
    install_env = dict(os.environ, PIP_CACHE_DIR=str(runtime / 'pip-cache'))
    subprocess.run([str(python), '-m', 'pip', 'install', '-r', str(ROOT / 'requirements.txt')], check=True, env=install_env)
    target = runtime / ('stockfish.exe' if os.name == 'nt' else 'stockfish')
    if args.stockfish:
        shutil.copy2(args.stockfish.resolve(), target)
    elif not target.exists():
        system = {'Linux': 'linux', 'Darwin': 'macos', 'Windows': 'windows'}.get(platform.system())
        arch = {'x86_64': 'x86-64', 'AMD64': 'x86-64', 'aarch64': 'arm64', 'arm64': 'arm64'}.get(platform.machine())
        if not system or not arch:
            parser.error('Unsupported platform. Supply a compatible binary with --stockfish.')
        request = urllib.request.Request('https://api.github.com/repos/official-stockfish/Stockfish/releases/latest', headers={'User-Agent': 'chess-arrows-installer'})
        release = json.load(urllib.request.urlopen(request, timeout=30))
        prefix = f'stockfish-{system}-' + ('' if system == 'macos' else arch + '-') + 'universal'
        asset = next((a for a in release['assets'] if a['name'].startswith(prefix + '.')), None)
        if not asset:
            parser.error(f'No official release for {system}/{arch}; use --stockfish.')
        print('Downloading', release['tag_name'], asset['name'], flush=True)
        with tempfile.TemporaryDirectory() as temp:
            folder = Path(temp)
            archive = folder / asset['name']
            urllib.request.urlretrieve(asset['browser_download_url'], archive)
            unpacked = folder / 'unpacked'
            if archive.suffix == '.zip':
                with zipfile.ZipFile(archive) as package:
                    for name in package.namelist():
                        if not (unpacked / name).resolve().is_relative_to(unpacked.resolve()):
                            raise ValueError('Unsafe archive path')
                    package.extractall(unpacked)
            else:
                with tarfile.open(archive) as package:
                    package.extractall(unpacked, filter='data')
            candidates = [p for p in unpacked.rglob('*') if p.is_file() and p.name.startswith('stockfish-') and p.suffix in ('', '.exe')]
            if len(candidates) != 1:
                raise RuntimeError(f'Expected one Stockfish executable; found {candidates}')
            shutil.copy2(candidates[0], target)
            for license_file in unpacked.rglob('Copying.txt'):
                shutil.copy2(license_file, runtime / 'Stockfish-Copying.txt')
    target.chmod(target.stat().st_mode | 0o111)
    if args.install_browser:
        subprocess.run([str(python), '-m', 'playwright', 'install', 'chromium'], check=True)
    if args.with_maia3:
        subprocess.run([str(python), str(ROOT / 'setup_maia.py')], check=True)
    if args.with_lc0:
        subprocess.run([str(python), str(ROOT / 'setup_lc0.py')], check=True)
    print('Ready. Start with: python3 run.py --elo 1500')


if __name__ == '__main__':
    main()
