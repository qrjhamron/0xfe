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
    assert "name='MoveCoach'" in spec and "name='maia-worker'" in spec and "'stockfish.exe'" in spec and "'lc0-gpu.exe'" in spec and "'onnxruntime.dll'" in spec and "'lc0-gpu-backend.txt'" in spec
    assert "maia3-install.json" in spec and "collect_submodules('maia3')" in spec
    assert 'COLLECT(' in spec and "name='MoveCoach'" in spec
    iss = (ROOT / 'windows/MoveCoach.iss').read_text()
    assert 'MoveCoach-Setup-v15' in iss and 'PrivilegesRequired=lowest' in iss
    ps = (ROOT / 'windows/build_windows.ps1').read_text()
    assert 'pyinstaller' in ps.lower() and 'iscc.exe' in ps and 'runtime\\lc0.exe' in ps and 'lc0-gpu.exe' in ps and 'onnxruntime.dll' in ps and 'setup_maia.py' in ps
    workflow = (ROOT / '.github/workflows/windows-installer.yml').read_text()
    assert 'windows-latest' in workflow and 'MoveCoach-Setup-v15.exe' in workflow
    assert 'patricia.exe' in spec and 'patricia_v2.exe' in ps
    print('PASS: Windows V15 frozen build and per-user installer inputs are present')


if __name__ == '__main__':
    main()
