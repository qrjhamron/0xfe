"""Static checks for the reproducible Windows installer inputs."""
from pathlib import Path


ROOT = Path(__file__).resolve().parent


def main():
    required = [
        ROOT / 'app_paths.py', ROOT / 'windows/MoveCoach.spec',
        ROOT / 'windows/MoveCoach.iss', ROOT / 'windows/build_windows.ps1',
        ROOT / 'windows/build_windows.bat',
        ROOT / '.github/workflows/windows-installer.yml',
        ROOT / 'windows/README.md',
    ]
    assert all(path.is_file() for path in required)
    spec = (ROOT / 'windows/MoveCoach.spec').read_text()
    assert "name='MoveCoach'" in spec and "'stockfish.exe'" in spec
    assert 'COLLECT(' in spec and "name='MoveCoach'" in spec
    iss = (ROOT / 'windows/MoveCoach.iss').read_text()
    assert 'MoveCoach-Setup-v12' in iss and 'PrivilegesRequired=lowest' in iss
    ps = (ROOT / 'windows/build_windows.ps1').read_text()
    assert 'pyinstaller' in ps.lower() and 'iscc.exe' in ps and 'runtime\\lc0.exe' in ps
    workflow = (ROOT / '.github/workflows/windows-installer.yml').read_text()
    assert 'windows-latest' in workflow and 'MoveCoach-Setup-v12.exe' in workflow
    print('PASS: Windows V12 frozen build and per-user installer inputs are present')


if __name__ == '__main__':
    main()
