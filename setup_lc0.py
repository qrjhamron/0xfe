#!/usr/bin/env python3
"""Install pinned CPU Lc0 and four Gyal weights. No root privileges required."""
import argparse
import gzip
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import urllib.request
import urllib.parse

from lc0_config import LC0_VERSION, LC0_COMMIT, WEIGHTS, weight_url
ROOT = Path(__file__).resolve().parent
RUNTIME = ROOT / 'runtime'


class CanonicalRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        # Normalize signed attachment query escaping consistently across Python/proxies.
        parts = urllib.parse.urlsplit(newurl)
        if parts.hostname == 'objects.githubusercontent.com':
            query = urllib.parse.urlencode(urllib.parse.parse_qsl(parts.query, keep_blank_values=True))
            newurl = urllib.parse.urlunsplit((parts.scheme, parts.netloc, parts.path, query, parts.fragment))
        return super().redirect_request(req, fp, code, msg, headers, newurl)


def download(url, target, digest=None):
    """Never expose partial downloads as installed models."""
    target.parent.mkdir(parents=True, exist_ok=True)
    temp = target.with_suffix(target.suffix + '.part')
    last = None
    opener = urllib.request.build_opener(CanonicalRedirect)
    for suffix in ['?download=1', '', '?raw=1', '?download']:
        try:
            with opener.open(url + suffix, timeout=60) as response, temp.open('wb') as out:
                shutil.copyfileobj(response, out)
            if digest and hashlib.sha256(temp.read_bytes()).hexdigest() != digest:
                raise ValueError('SHA-256 mismatch: ' + target.name)
            if target.name.endswith('.pb.gz'):
                with gzip.open(temp, 'rb') as model:
                    while model.read(1024 * 1024):
                        pass  # Validate gzip CRC before committing.
            temp.replace(target)
            return
        except (OSError, ValueError) as exc:
            last = exc
            temp.unlink(missing_ok=True)
    raise RuntimeError(f'Download failed: {target.name}: {last}')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--lc0', type=Path, help='Use an existing compatible Lc0 CPU binary')
    parser.add_argument('--jobs', type=int, default=2, choices=range(1, 9))
    args = parser.parse_args()
    RUNTIME.mkdir(exist_ok=True)
    binary = RUNTIME / ('lc0.exe' if os.name == 'nt' else 'lc0')
    if args.lc0:
        if args.lc0.resolve() != binary.resolve():
            shutil.copy2(args.lc0, binary)
    elif not binary.exists():
        if os.name == 'nt' or not shutil.which('g++') or not shutil.which('git'):
            parser.error('Install C++20 compiler and git, or supply --lc0 PATH to a compatible CPU binary.')
        subprocess.run([sys.executable, '-m', 'pip', 'install', 'meson>=1.3,<2', 'ninja>=1.11,<2'], check=True)
        source, build = RUNTIME / 'lc0-src', RUNTIME / 'lc0-build'
        if not source.exists():
            subprocess.run(['git', 'clone', '--depth', '1', '--branch', LC0_VERSION,
                            'https://github.com/LeelaChessZero/lc0.git', str(source)], check=True)
        revision = subprocess.check_output(['git', '-C', str(source), 'rev-parse', 'HEAD'], text=True).strip()
        if revision != LC0_COMMIT:
            raise RuntimeError('Unexpected Lc0 source revision')
        # CPU build only needs this pinned common-submodule protobuf definition.
        proto = source / 'libs/lczero-common/proto/net.proto'
        if not proto.exists():
            download('https://raw.githubusercontent.com/LeelaChessZero/lczero-common/'
                     'b326b154221a6eb91977bdccf11d6f89e8547875/proto/net.proto', proto)
        env = dict(os.environ)
        env['PATH'] = str(Path(sys.executable).parent) + os.pathsep + env.get('PATH', '')
        if not (build / 'build.ninja').exists():
            subprocess.run([sys.executable, '-m', 'mesonbuild.mesonmain', 'setup', str(build), str(source),
                            '--buildtype=release', '-Db_lto=false', '-Dnative_arch=false',
                            '-Dplain_cuda=false', '-Donnx=false', '-Dopenblas=false',
                            '-Dispc=false', '-Dgtest=false', '-Dmetal=disabled'], check=True, env=env)
        subprocess.run(['ninja', '-C', str(build), '-j' + str(args.jobs)], check=True, env=env)
        shutil.copy2(build / 'lc0', binary)
        shutil.copy2(source / 'COPYING', RUNTIME / 'Lc0-COPYING.txt')
    binary.chmod(binary.stat().st_mode | 0o111)
    manifest = {'version': LC0_VERSION, 'source_commit': LC0_COMMIT, 'backend': 'eigen', 'weights': {}}
    for key, (label, name, attachment, size) in WEIGHTS.items():
        target = RUNTIME / 'lc0-weights' / (name + '.pb.gz')
        expected = None
        if (ROOT / 'lc0-checksums.json').exists():
            expected = json.loads((ROOT / 'lc0-checksums.json').read_text()).get(key)
        if not target.exists() or (expected and hashlib.sha256(target.read_bytes()).hexdigest() != expected):
            print('Downloading', label, flush=True)
            download(weight_url(name, attachment), target, expected)
        manifest['weights'][key] = {'label': label, 'architecture': size,
            'sha256': hashlib.sha256(target.read_bytes()).hexdigest(), 'url': weight_url(name, attachment)}
    # Test every model with the actual binary/backend, then advertise installation.
    import chess
    import chess.engine
    for key, (_, name, _, _) in WEIGHTS.items():
        backend = 'blas' if os.name == 'nt' else 'eigen'
        engine = chess.engine.SimpleEngine.popen_uci([str(binary), '--backend=' + backend,
                    '--weights=' + str(RUNTIME / 'lc0-weights' / (name + '.pb.gz')),
                    '--threads=1', '--minibatch-size=1', '--nncache=20000'], timeout=30)
        try:
            move = engine.play(chess.Board(), chess.engine.Limit(nodes=1, time=2)).move
            if move not in chess.Board().legal_moves:
                raise RuntimeError('Invalid model output: ' + key)
        finally:
            engine.quit()
        print('Verified', key, flush=True)
    target = RUNTIME / 'lc0-install.json'
    temp = target.with_suffix('.tmp'); temp.write_text(json.dumps(manifest, indent=2)); temp.replace(target)
    print('Ready: python run.py --elo 1500')


if __name__ == '__main__':
    main()
