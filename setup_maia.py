#!/usr/bin/env python3
"""Install upstream Maia-3 with CPU PyTorch and cache the 5M checkpoint."""
import argparse
import json
import os
from pathlib import Path
import subprocess
import sys
from maia_config import SOURCE_URL, SOURCE_REVISION, MODEL_NAME, MODEL_REVISION

ROOT = Path(__file__).resolve().parent


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--skip-torch', action='store_true', help='Keep an already installed PyTorch')
    args = parser.parse_args()
    python = ROOT / '.venv' / ('Scripts/python.exe' if os.name == 'nt' else 'bin/python')
    if not python.exists():
        parser.error('Run install.py first to create the project virtual environment.')
    runtime = ROOT / 'runtime'
    runtime.mkdir(exist_ok=True)
    env = dict(os.environ, PIP_CACHE_DIR=str(runtime / 'pip-cache'), HF_HOME=str(runtime / 'huggingface'))
    source = runtime / 'maia3-src'
    if not (source / 'pyproject.toml').exists():
        subprocess.run(['git', 'init', str(source)], check=True, env=env)
        subprocess.run(['git', '-C', str(source), 'remote', 'add', 'origin', SOURCE_URL], check=True, env=env)
    current = subprocess.run(['git', '-C', str(source), 'rev-parse', 'HEAD'], capture_output=True, text=True, env=env)
    if current.returncode or current.stdout.strip() != SOURCE_REVISION:
        subprocess.run(['git', '-C', str(source), 'fetch', '--depth', '1', 'origin', SOURCE_REVISION], check=True, env=env)
        subprocess.run(['git', '-C', str(source), 'checkout', '--detach', SOURCE_REVISION], check=True, env=env)
    revision = subprocess.check_output(['git', '-C', str(source), 'rev-parse', 'HEAD'], text=True, env=env).strip()
    if not args.skip_torch:
        command = [str(python), '-m', 'pip', 'install', 'torch>=2.6,<3']
        if sys.platform != 'darwin':
            command += ['--index-url', 'https://download.pytorch.org/whl/cpu']
        subprocess.run(command, check=True, env=env)
    subprocess.run([str(python), '-m', 'pip', 'install', str(source)], check=True, env=env)
    script = python.parent / ('maia3-cache.exe' if os.name == 'nt' else 'maia3-cache')
    subprocess.run([str(script), '--model', MODEL_NAME, '--revision', MODEL_REVISION,
                    '--cache-dir', str(runtime / 'maia3-cache')], check=True, env=env)
    (runtime / 'maia3-install.json').write_text(json.dumps({
        'source': 'https://github.com/CSSLab/maia3', 'revision': revision,
        'model': MODEL_NAME, 'model_revision': MODEL_REVISION,
        'device': 'cpu', 'cache_dir': str(runtime / 'maia3-cache')}, indent=2))
    print('Maia-3 5M installed and cached; ready for offline inference.', flush=True)


if __name__ == '__main__':
    main()
