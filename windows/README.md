# Windows V14 build

Build on a Windows 10/11 machine with Python 3.12, Git, and Inno Setup.

1. Place compatible CPU binaries at `runtime\lc0.exe` and (if not already present) let `build_windows.ps1` download `runtime\stockfish.exe`. The build also downloads the small DirectML `lc0-gpu.exe` binary; it is selected when a compatible GPU is detected.
2. Run PowerShell:

```powershell
Set-ExecutionPolicy -Scope Process Bypass
.\windows\build_windows.ps1 -Clean
```

The final installer is `windows\Output\MoveCoach-Setup-v15.exe`. The app uses
Chrome/Edge already installed on the machine. Add `-InstallChromium` to cache a
Playwright Chromium fallback during the build.

The installer is per-user and writes its status/cache under the selected app
folder. Maia 3 5M is included as an offline CPU sidecar (`maia-worker.exe`), so
the Maia button is ready immediately after installation and does not need CUDA.
The extra PyTorch runtime makes the installer larger than the Lc0-only build.

On a machine without a compatible GPU, the CPU-DNNL path is selected
automatically. Set `LC0_FORCE_CPU=1` to force that path, or use
`LC0_BACKEND` for backend diagnosis. The GPU package uses DirectML and does
not require `cudart64_12.dll`.

If the launcher closes before a browser appears, inspect `runtime\\launcher.log`
and `browser.log` inside the installed Move Coach folder. The launcher checks
the standard Chrome and Edge install locations before trying Playwright.
