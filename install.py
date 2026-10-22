#!/usr/bin/env python3
"""Install the lean Patricia-only Move Coach environment (no root needed)."""
import argparse
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parent


def environment_python():
    path = ROOT / '.venv' / ('Scripts/python.exe' if sys.platform == 'win32' else 'bin/python')
    if not path.exists():
        subprocess.run([sys.executable, '-m', 'venv', str(ROOT / '.venv')], check=True)
    return path


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--skip-patricia', action='store_false', dest='with_patricia',
                        help='Do not install the Patricia engine binary')
    parser.add_argument('--install-browser', action='store_true',
                        help='Install the Playwright Chromium fallback')
    args = parser.parse_args()

    python = environment_python()
    subprocess.run([str(python), '-m', 'pip', 'install', '--upgrade',
                    '-r', str(ROOT / 'requirements.txt')], check=True)
    if args.with_patricia:
        subprocess.run([str(python), str(ROOT / 'setup_patricia.py')], check=True)
    else:
        print('Patricia skipped; the panel level buttons will be unavailable.')
    if args.install_browser:
        subprocess.run([str(python), '-m', 'playwright', 'install', 'chromium'], check=True)
    print('\nEnvironment ready. Run the test suite, then: python3 run.py --status status.json')


if __name__ == '__main__':
    main()
