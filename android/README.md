# Move Coach Android — Patricia

Aplikasi Android membuka Chess.com dalam WebView dan menampilkan panah
rekomendasi dari engine [Patricia](https://github.com/Adam-Kulju/Patricia)
yang berjalan lokal di HP sebagai proses UCI arm64.

Beda dari versi desktop:

- **Tanpa auto move dan tanpa premove.** Aplikasi tidak pernah mengklik,
  menggeser, atau mengantrekan langkah. Panah hanya rekomendasi.
- **Satu engine: Patricia.** Tidak ada Lc0, Maia, Stockfish, mode hybrid,
  atau kalibrasi Elo lokal.
- **Skill Level 1–18.** Tombol panel memakai `Skill_Level` bawaan Patricia;
  label Elo (500–2650) adalah tabel estimasi dari proyek Patricia, bukan
  rating manusia terverifikasi. Level awal Skill 7 (≈1500).

Panel menyediakan tombol Skill 1–18, pilihan sisi (Otomatis/Putih/Hitam/
Kedua sisi), warna dan ketebalan panah, serta tombol Aktif. Preferensi
disimpan di localStorage WebView.

## Build

Build dilakukan oleh GitHub Actions (`.github/workflows/android.yml`):
cross-compile Patricia statis arm64 dari commit terpin, lalu Gradle
membangun APK debug dan menjalankan unit test. APK tersedia sebagai
artifact `movecoach-android-apk` pada run workflow tersebut.

Build lokal (Linux dengan JDK 17 dan Gradle 8.9):

```sh
sudo apt-get install g++-aarch64-linux-gnu
./android/build-patricia.sh
cd android && gradle :app:testDebugUnitTest :app:assembleDebug
```

Hasil: `android/app/build/outputs/apk/debug/app-debug.apk` (debug-signed,
untuk sideload pengujian).

## Catatan

- Target situs adalah Chess.com versi web di dalam WebView, bukan aplikasi
  Chess.com.
- Langkah yang ditampilkan di panel adalah notasi UCI dari Patricia
  (mis. `G1F3`); panah di papan adalah petunjuk utamanya.
- `python3 check_android.py` di root repo memeriksa kontrak Android ini
  tanpa JDK: tabel skill, ketiadaan jalur input papan, dan wiring build.
