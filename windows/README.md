# Windows V15 build

Build on a Windows 10/11 machine with Python 3.12, Git, and Inno Setup.

1. Let `build_windows.ps1` download `runtime\stockfish.exe` and the pinned Patricia 5.1 binary (`runtime\patricia.exe`, checksum-verified). No Lc0 binaries/weights and no Maia checkpoint are downloaded or packaged in this Patricia-focused build.
2. Run PowerShell:

```powershell
Set-ExecutionPolicy -Scope Process Bypass
.\windows\build_windows.ps1 -Clean
```

The final installer is `windows\Output\MoveCoach-Setup-v15.exe`. The app uses
Chrome/Edge already installed on the machine. Add `-InstallChromium` to cache a
Playwright Chromium fallback during the build.

The installer is per-user and writes its status/cache under the selected app
folder. Patricia is the packaged engine; Lc0/Maia/Hybrid modes only light up
in source installs that provide those engines themselves.

If the launcher closes before a browser appears, inspect `runtime\\launcher.log`
and `browser.log` inside the installed Move Coach folder. The launcher checks
the standard Chrome and Edge install locations before trying Playwright.
