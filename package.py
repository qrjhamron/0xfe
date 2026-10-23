#!/usr/bin/env python3
"""Create a portable distribution from an explicit public-file allowlist."""
from pathlib import Path
import zipfile
ROOT = Path(__file__).resolve().parent
SOURCES = ['README.md', '.gitignore', 'requirements.txt', 'install.py', 'run.py',
           'arrows.py', 'adaptive_strength.py', 'app_paths.py', 'auto_moves.py', 'premove.py', 'session_audit.py', 'engine_runtime.py', 'panel.js', 'overlay.js',
           'presets.py', 'human_style.py',
           'setup_patricia.py', 'check_patricia.py', 'check_browser.py', 'check_auto_moves.py', 'check_premove.py',
           'check_premove_ui.py', 'check_premove_engine.py', 'check_native_board.py', 'check_time_management.py', 'check_engine_upgrade.py', 'check_adaptive_strength.py', 'check_windows_packaging.py', 'check_humanize.py', 'check_consistency.py', 'opening_book.py', 'package.py',
           'coach_app/__init__.py', 'coach_app/main.py', 'coach_app/windows.py', 'coach_app/overlay.py', 'coach_app/controller.py', 'coach_app/geometry.py', 'coach_app/snapshot.py', 'coach_app/streaming.py', 'coach_app/README.md', 'run_app.py', 'check_desktop_app.py', 'requirements-app.txt',
           'windows/MoveCoach.spec', 'windows/MoveCoach.iss', 'windows/build_windows.ps1', 'windows/build_windows.bat', 'windows/README.md', '.github/workflows/windows-installer.yml']

def main():
    files = [ROOT / name for name in SOURCES]
    files += [ROOT/'calibration-v6/REPORT.md',ROOT/'calibration-v6/public-results.json',ROOT/'calibration-v6/levels.png',
              ROOT/'calibration-v7-targeted/REPORT-low.md',ROOT/'calibration-v7-targeted/public-results-low.json']
    for filename in ['chess-arrows-v10.zip', 'chess-arrows.zip']:
        target = ROOT.parent / filename
        with zipfile.ZipFile(target, 'w', zipfile.ZIP_DEFLATED) as archive:
            for path in files:
                archive.write(path, Path('chess-arrows') / path.relative_to(ROOT))
        print(target, target.stat().st_size)

if __name__ == '__main__':main()
