# Windows V12 build

Build on a Windows 10/11 machine with Python 3.12, Git, and Inno Setup.

1. Place compatible CPU binaries at `runtime\lc0.exe` and (if not already present) let `build_windows.ps1` download `runtime\stockfish.exe`.
2. Run PowerShell:

```powershell
Set-ExecutionPolicy -Scope Process Bypass
.\windows\build_windows.ps1 -Clean
```

The final installer is `windows\Output\MoveCoach-Setup-v12.exe`. The app uses
Chrome/Edge already installed on the machine. Add `-InstallChromium` to cache a
Playwright Chromium fallback during the build.

The installer is per-user and writes its status/cache under the selected app
folder. Maia is intentionally omitted from the base package; it can be added in
a later Windows package after its CPU footprint is validated.

If the launcher closes before a browser appears, inspect `runtime\\launcher.log`
and `browser.log` inside the installed Move Coach folder. The launcher checks
the standard Chrome and Edge install locations before trying Playwright.
