# Move Coach App (PySide6)

Aplikasi desktop Windows: Chess.com berjalan di dalam jendela aplikasi
(Qt WebEngine), panel kontrolnya native Qt dan tinggal di system tray,
dan panah rekomendasi digambar oleh overlay Qt transparan — halaman
Chess.com tidak diinjeksi apa pun, skrip snapshot hanya membaca papan.

- **Mode Streaming**: overlay panah dan jendela kontrol memakai
  `SetWindowDisplayAffinity(WDA_EXCLUDEFROMCAPTURE)`, jadi keduanya
  terlihat di monitor tetapi tidak muncul di tangkapan layar TikTok
  Live Studio/OBS. Papan tetap terlihat di siaran.
- Patricia adalah satu-satunya engine, dengan lima gaya seperti versi
  browser. Level 1000–2300 memetakan ke Skill_Level Patricia.
- Auto move (opsional) mengklik di dalam WebEngine aplikasi.

Jalankan dari sumber (Windows, Python 3.12):

```powershell
python -m venv .venv
.venv\Scripts\python -m pip install -r requirements-app.txt
.venv\Scripts\python setup_patricia.py
.venv\Scripts\python run_app.py
```

Build Windows (`dist\MoveCoachApp\MoveCoach.exe`, termasuk smoke test
offscreen) berjalan di workflow `windows-app.yml` atau lokal lewat
`windows\build_app.ps1`. Pemeriksaan tanpa display:
`python check_desktop_app.py`.
