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
    assert "name='MoveCoach'" in spec and "'patricia.exe'" in spec and 'stockfish' not in spec
    assert 'COLLECT(' in spec and "name='MoveCoach'" in spec
    # Patricia-focused installer: no Lc0 binaries/weights, no Maia sidecar.
    for gone in ('lc0.exe', 'lc0-gpu.exe', 'onnxruntime.dll', 'maia-worker',
                 'maia3-install.json', 'lc0-weights'):
        assert gone not in spec, f'heavy engine input still packaged: {gone}'
    iss = (ROOT / 'windows/MoveCoach.iss').read_text()
    assert 'MoveCoach-Setup-v16' in iss and 'PrivilegesRequired=lowest' in iss
    ps = (ROOT / 'windows/build_windows.ps1').read_text()
    assert 'pyinstaller' in ps.lower() and 'iscc.exe' in ps and 'patricia_v2.exe' in ps
    for gone in ('lc0-v0.32.1', 'setup_lc0.py', 'setup_maia.py'):
        assert gone not in ps, f'heavy engine download still in build: {gone}'
    workflow = (ROOT / '.github/workflows/windows-installer.yml').read_text()
    assert 'windows-latest' in workflow and 'MoveCoach-Setup-v16.exe' in workflow
    assert 'refs/tags/move-coach-v' in workflow and 'action-gh-release' in workflow
    print('PASS: Windows V16 Patricia-only installer inputs are present and lean')


if __name__ == '__main__':
    main()
