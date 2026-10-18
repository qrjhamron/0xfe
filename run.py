#!/usr/bin/env python3
"""Start or attach to Chromium, then run automatic engine arrows."""
import argparse
import os
from pathlib import Path
import shutil
import subprocess
import sys
import time
import urllib.request

from app_paths import ROOT
PYTHON = ROOT / '.venv' / ('Scripts/python.exe' if os.name == 'nt' else 'bin/python')


def write_launcher_log(message):
    try:
        log = ROOT / 'runtime' / 'launcher.log'
        log.parent.mkdir(parents=True, exist_ok=True)
        with log.open('a', encoding='utf-8') as stream:
            stream.write(time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime()) + ' ' + message + '\n')
    except OSError:
        pass


def browser_candidates():
    names = ['chromium', 'chromium-browser', 'google-chrome', 'chrome', 'msedge', 'microsoft-edge']
    found = [shutil.which(name) for name in names]
    if os.name == 'nt':
        local = os.environ.get('LOCALAPPDATA', '')
        program = os.environ.get('PROGRAMFILES', '')
        program_x86 = os.environ.get('PROGRAMFILES(X86)', '')
        found += [
            str(Path(local) / 'Google/Chrome/Application/chrome.exe'),
            str(Path(program) / 'Google/Chrome/Application/chrome.exe'),
            str(Path(program_x86) / 'Google/Chrome/Application/chrome.exe'),
            str(Path(local) / 'Microsoft/Edge/Application/msedge.exe'),
            str(Path(program) / 'Microsoft/Edge/Application/msedge.exe'),
            str(Path(program_x86) / 'Microsoft/Edge/Application/msedge.exe'),
        ]
    return [path for path in found if path and Path(path).exists()]


def main():
    if PYTHON.exists() and Path(sys.prefix).resolve() != PYTHON.parent.parent.resolve():
        return subprocess.call([str(PYTHON), str(Path(__file__)), *sys.argv[1:]])
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--port', type=int, default=9222)
    parser.add_argument('--browser', help='Path to a Chromium/Chrome executable')
    parser.add_argument('--headless', action='store_true', help='Run without a desktop display')
    parser.add_argument('--no-sandbox', action='store_true', help='Only for isolated environments requiring this option')
    args, extra = parser.parse_known_args()
    cdp = f'http://127.0.0.1:{args.port}'
    # Only the local browser management connection bypasses HTTP proxies.
    local = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    def ready():
        try:
            with local.open(cdp + '/json/version', timeout=1) as response:
                return response.status == 200
        except OSError:
            return False
    if not ready():
        executable = args.browser or next(iter(browser_candidates()), None)
        if not executable:
            try:
                from playwright.sync_api import sync_playwright
                with sync_playwright() as pw:
                    executable = pw.chromium.executable_path
            except Exception as exc:
                write_launcher_log(f'Playwright browser lookup failed: {type(exc).__name__}: {exc}')
                parser.error('Browser missing. Install Chrome/Edge or build with Chromium included.')
            if not Path(executable).exists():
                write_launcher_log(f'No browser executable found: {executable}')
                parser.error('Browser missing. Install Chrome/Edge or build with Chromium included.')
        command = [executable, '--remote-debugging-address=127.0.0.1', f'--remote-debugging-port={args.port}',
                   f'--user-data-dir={ROOT / "browser-profile"}', '--disable-dev-shm-usage', '--window-size=1440,1000']
        if args.headless:
            command.append('--headless=new')
        if args.no_sandbox:
            command.append('--no-sandbox')
        command.append('https://www.chess.com/play/computer')
        write_launcher_log(f'Starting browser: {executable}')
        with (ROOT / 'browser.log').open('ab') as log:
            browser = subprocess.Popen(command, stdout=log, stderr=log)
        for _ in range(50):
            if ready():
                break
            if browser.poll() is not None:
                write_launcher_log(f'Browser exited with code {browser.returncode}')
                parser.error('Browser exited. See browser.log.')
            time.sleep(.2)
        else:
            parser.error('Browser did not start. See browser.log.')
    if getattr(sys, 'frozen', False):
        # The frozen executable contains both the launcher and daemon.  Invoke
        # the daemon in-process so there is no missing ``arrows.py`` beside the
        # installed executable.
        from arrows import main as arrows_main
        original = sys.argv
        try:
            sys.argv = [sys.argv[0], '--cdp', cdp, *extra]
            try:
                return arrows_main()
            except Exception as exc:
                write_launcher_log(f'Daemon failed: {type(exc).__name__}: {exc}')
                raise
        finally:
            sys.argv = original
    return subprocess.call([sys.executable, str(ROOT / 'arrows.py'), '--cdp', cdp, *extra])


if __name__ == '__main__':
    raise SystemExit(main())
