#!/usr/bin/env python3
"""Create a portable distribution from an explicit public-file allowlist."""
from pathlib import Path
import zipfile
from lc0_config import WEIGHTS
ROOT = Path(__file__).resolve().parent
SOURCES = ['README.md', '.gitignore', 'requirements.txt', 'install.py', 'run.py',
           'arrows.py', 'adaptive_strength.py', 'app_paths.py', 'auto_moves.py', 'premove.py', 'session_audit.py', 'engine_runtime.py', 'panel.js', 'overlay.js',
           'presets.py', 'calibration-profiles.json', 'maia_config.py', 'setup_maia.py', 'lc0_config.py', 'lc0-checksums.json',
           'setup_lc0.py', 'check_engines.py', 'check_browser.py', 'check_lc0.py', 'check_auto_moves.py', 'check_premove.py',
           'check_premove_ui.py', 'check_premove_engine.py', 'check_native_board.py', 'check_time_management.py', 'check_engine_upgrade.py', 'check_adaptive_strength.py', 'check_windows_packaging.py', 'opening_book.py', 'package.py',
           'windows/MoveCoach.spec', 'windows/MoveCoach.iss', 'windows/build_windows.ps1', 'windows/build_windows.bat', 'windows/README.md', '.github/workflows/windows-installer.yml']

def main():
    files = [ROOT / name for name in SOURCES]
    files += [ROOT/'calibration-v6/REPORT.md',ROOT/'calibration-v6/public-results.json',ROOT/'calibration-v6/levels.png',
              ROOT/'calibration-v7-targeted/REPORT-low.md',ROOT/'calibration-v7-targeted/public-results-low.json']
    files += [ROOT / 'runtime/lc0-weights' / (value[1]+'.pb.gz') for value in WEIGHTS.values()]
    for filename in ['chess-arrows-v10.zip', 'chess-arrows.zip']:
        target = ROOT.parent / filename
        with zipfile.ZipFile(target, 'w', zipfile.ZIP_DEFLATED) as archive:
            for path in files:
                archive.write(path, Path('chess-arrows') / path.relative_to(ROOT))
        print(target, target.stat().st_size)

if __name__ == '__main__':main()
