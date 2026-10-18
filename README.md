# Move Coach V13 — premove tunggal berulang, cabang 3/5/8

Tombol aktif saat ini: **1500, 1600, 1700, 1800, 1900, 2000**. Tombol
2100–2300 dinonaktifkan sampai ada kalibrasi terpisah. Pilih satu tombol;
konfigurasi level dipilih otomatis di backend. Level awal 1500. Panel tidak
menampilkan nama model, jumlah node, penggeser Elo atau input Elo bebas.
Pilihan level dan penampilan disimpan serta disinkronkan antartab.

## Paket Windows V13

Versi Windows dibangun sebagai installer per-user `MoveCoach-Setup-v13.exe`.
Build memakai PyInstaller dan Inno Setup; Lc0 CPU Windows DNNL dan binary GPU
DirectML opsional diambil dari rilis terpin, diverifikasi checksum, lalu dipasang
bersama Stockfish dan empat weight. Chrome atau Edge yang sudah ada dipakai oleh
launcher. Maia 3 5M sekarang ikut terpaket sebagai worker CPU offline, dengan
checkpoint dicache saat build. Instruksi build ada di
[windows/README.md](windows/README.md). Rencana migrasi ke shell native Windows
ada di [WINDOWS-DESKTOP-UI-PLAN.md](WINDOWS-DESKTOP-UI-PLAN.md).

## Arti label

Footer menandai target yang berada di luar interval sampel sebagai **tentatif**. Target yang berada di dalam interval juga belum membuktikan rating manusia secara pasti.

Angka tombol adalah **target level latihan**, bukan Elo Chess.com/FIDE yang
terverifikasi. V7 memakai 288 game kalibrasi dan 72 game holdout untuk enam
tombol rendah. Profil 2100–2300 dinonaktifkan dan belum diklaim terkalibrasi
setelah perubahan node. V6 memakai 624 game kalibrasi untuk tiga belas kandidat, kemudian
108 game tambahan pada bukaan berbeda untuk sembilan preset V6 yang dipilih.
Preset aktif V7 rendah mempunyai 48 game kalibrasi dan 12 game validasi.
Empat kandidat tambahan tidak dipakai tetapi datanya tetap disimpan. Dua belas game diagnostik dari kandidat 2100 yang diganti juga diarsipkan, sehingga total yang diverifikasi 744 game. Tiga kandidat perantara ditambahkan setelah hasil awal menunjukkan perlunya memperhalus level tinggi; pemilihannya tidak memakai hasil validasi.

Laporan estimasi, rentang sampel dan hasil pertandingan ada di
[laporan kalibrasi](calibration-v7-targeted/REPORT-low.md). Lawan benchmark memakai setelan
kekuatan lokal dengan waktu berpikir singkat. Interval antarpreset bisa tumpang
tindih; perbedaan 100 pada tombol tidak membuktikan perbedaan 100 Elo manusia.
Hasil game dan kekuatan pada posisi tertentu dapat bervariasi. Tidak ada jaminan
menang atau jaminan bebas kesalahan taktis. Validasi tidak mengubah preset
setelah dipilih dari data kalibrasi.

## Panel

- **Tombol Elo**: pilih satu level tetap; pilihan aktif disorot. Footer menampilkan estimasi lokal terukur, sedangkan tooltip tombol memuat rentang sampelnya.
- **Aktif**: nyalakan atau matikan panah segera.
- **Saya bermain**: deteksi otomatis, Putih, Hitam, atau kedua sisi untuk analisis.
- **Warna / Tebal**: atur penampilan panah.
- **Cek pembaruan**: periksa rilis Windows terbaru dari GitHub tanpa mencari link manual.
- **Kekuatan adaptif per fase**: sesuaikan budget secara konservatif untuk opening, middlegame, endgame, dan posisi taktis. Matikan toggle untuk memakai budget kalibrasi tetap.
- **Mode mesin**: pilih Lc0 terkalibrasi atau Maia 3 gaya manusia jika worker Maia tersedia. Level tetap membatasi rentang latihan; Maia berjalan offline di CPU.
- **Gelar profil game**: badge gelar visual ditempel di samping nama pemain pada kartu game Chess.com. Avatar dan kartu tetap milik halaman Chess.com; badge hanya dekorasi lokal.

Panel mengikuti papan, orientasi, reload dan game baru. Identitas pemain
menggunakan API atau profil Guest, bukan orientasi papan. Jika identitas belum
jelas, mode otomatis menunggu pemilihan warna. Panah disembunyikan saat
giliran lawan, riwayat game aktif, dan posisi akhir game. Riwayat sesudah game
mendukung analisis. Auto move dan antrean premove tersedia sebagai pilihan yang awalnya mati.

Preferensi penampilan lama dipertahankan. Elo lama yang tersedia tetap dipilih;
angka lain kembali ke level awal. Data konfigurasi level di browser lama tidak
dipakai. Level yang belum terpasang dinonaktifkan tanpa penggantian kekuatan
diam-diam.

## Instalasi

Gunakan Python 3.12+, git, kompiler C++20, dan Chromium/Chrome. Paket ZIP membawa
berkas model publik, checksum dan data kalibrasi. Installer menyiapkan runtime
CPU untuk mesin tujuan, tanpa memaketkan sesi browser atau kredensial.
Linux x86_64 CPU telah diuji. Platform lain memerlukan runtime CPU kompatibel.
Pembangunan pertama memerlukan beberapa menit.

```sh
python3 install.py
python3 run.py --elo 1500
```

Jika perlu memasang browser:

```sh
python3 install.py --install-browser
python3 run.py --headless --no-sandbox --elo 1500
```

Untuk memperbarui instalasi lama, ekstrak paket V10 di atas folder proyek dan
mulai ulang daemon. Browser di port 9222 dapat dipakai kembali. Preferensi
browser yang tersimpan mendahului nilai awal CLI. Jangan jalankan dua daemon
pada instalasi yang sama.

## Stabilitas dan sumber data

Preset ditentukan backend melalui data kalibrasi yang lengkap. Daemon menjalankan
langkah utama dengan single-PV dan node aktual preset (faktor default 1, dapat
diubah dengan `--node-multiplier`); Stockfish tidak memakai MultiPV. Setiap perubahan
pemetaan mempunyai identitas konfigurasi baru; panel diinstal ulang agar panah
lama tidak terbawa ke pemetaan baru. Hasil yang terlambat ditolak melalui token
posisi/konfigurasi. Penggantian level segera menghapus panah lama.

Model dimuat di background dan dilepas setelah 60 detik menganggur. Cache
hasil dibatasi menurut model, posisi, riwayat dan batas pencarian. Antrean
memakai permintaan terbaru tiap tab. Pencarian CPU menghindari prefetch yang
tidak diperlukan. Pengaturan runtime sama dengan pengaturan benchmark V6.
Model yang gagal dipulihkan otomatis; panah menghilang jika heartbeat hilang
lebih dari 4,5 detik. Tidak ada filter engine lain yang diam-diam mengganti langkah.

`check_browser.py` menguji seluruh tombol melalui backend nyata, langkah legal,
giliran, orientasi, toggle, reload dan penolakan hasil lama. Jalankan daemon dengan
`--status runtime/v6-status.json` sebelum menjalankannya. Tes memakai papan
terisolasi tanpa matchmaking. `check_engines.py` menguji worker dan pemulihan proses.

Skrip `calibrate_v6.py`, `analyze_v6.py`, `validate_v6.py`, dan `finalize_v6.py`
tersedia dalam arsip hasil terpisah untuk audit. Analisis grafik membutuhkan
matplotlib. Pilihan langkah lawan benchmark bersifat stokastik; pengulangan
baru tidak menjamin PGN identik. `python3 package.py` membuat ZIP melalui
allowlist, tanpa cache, log, sesi browser atau kredensial.


## Kontrol gerakan otomatis (V13)

Engine memakai **incremental analysis**: worker mempertahankan identitas game dan hash UCI antar giliran serta menghitung cache hit incremental secara terpisah. Opening book kecil menangani beberapa posisi pembukaan umum dalam delapan ply pertama. Langkah utama memakai policy `play()` single-PV Lc0 pada node aktual preset; faktor dapat diatur melalui `--node-multiplier`. MultiPV tidak dipakai untuk memilih langkah utama. Planner premove masih memakai MultiPV terbatas untuk membaca beberapa cabang lawan, lalu memeriksa legalitas dan risiko sebelum mengantrekan satu langkah.

**Kekuatan adaptif per fase** aktif dari panel V13. Budget preset menjadi baseline middlegame; posisi opening yang tenang memakai sekitar 75%, endgame queenless bermaterial rendah sekitar 115%, dan posisi sedang check sekitar 125%. Budget selalu dibulatkan dan dibatasi 1–256 node. Model, tombol Elo, dan limiter tetap sama; toggle dapat dimatikan untuk kembali ke budget kalibrasi tetap. Estimasi Elo yang ditampilkan adalah acuan preset tengah, sehingga mode adaptif sebaiknya dibaca sebagai rentang latihan, bukan rating resmi.

**Auto move** menjalankan rekomendasi saat giliranmu. **Auto premove** mengantrekan langkah melalui API premove native pada papan saat giliran lawan. Antrean diverifikasi dari `game.premoves.getQueue()` dan FEN aktual harus tetap sama setelah antrean dipasang. Situs sendiri mengonsumsi antrean saat langkah lawan datang. Produk tidak memasang plugin tambahan atau memanggil API pengiriman langkah langsung untuk premove; papan pertandingan harus menyediakan plugin native-nya.

Antrean aplikasi selalu **satu langkah**, lalu diisi ulang pada setiap posisi baru saat giliran lawan. Pilihan lama 2/3 langkah dimigrasikan ke satu. **Cabang lawan** memilih 3, 5 (awal), atau 8 kandidat melalui MultiPV. Setiap kandidat mendapatkan respons dari preset yang sama. Respons untuk beberapa cabang disimpan agar saat lawan benar-benar melangkah, cabang yang cocok bisa langsung digunakan. Tampilan cabang menampilkan langkah lawan dan respons yang dihitung, bukan tiga premove berurutan. **Advanced premove** memberi prioritas tambahan pada respons forcing atau recapture yang tetap cocok di banyak cabang. **Endgame premove** aktif otomatis pada posisi minim material tanpa queen; planner memperlebar sampel hingga 8 cabang, tetap menolak pat/repetisi, dan memastikan ada kelanjutan legal setelah langkah.

Kandidat premove dipilih dari respons tersebut dengan prioritas dukungan beberapa cabang dan cakupan balasan legal. Langkah yang hanya cocok untuk satu tebakan sempit tidak langsung mengalahkan respons yang dapat digunakan setelah banyak pilihan lawan. Sebelum diantrekan, kandidat diperiksa terhadap **seluruh balasan legal satu langkah**: langkah ilegal, pat, pengulangan ketiga, ancaman mat satu langkah, dan pertukaran langsung di kotak tujuan. **Pola premove** Ketat/Seimbang/Aktif membatasi kerugian pertukaran yang diterima pada 0/100/220 centipawn. Angka ini batas pemeriksaan lokal, bukan evaluasi posisi lengkap atau probabilitas aman. Taktik panjang dan ancaman terhadap bidak lain dapat lolos. Jika semua kandidat gagal, premove ditahan dan Auto move tetap menggunakan preset normal.

Premove tetap spekulatif: balasan lawan yang berbeda dapat langsung mengonsumsi langkah bila masih legal. Pemeriksaan setelah kejadian tidak dapat menarik kembali langkah itu. Aplikasi tidak menjanjikan premove pada setiap giliran. Balasan lawan paksa tidak memerlukan pencarian prediksi. Anggaran prediksi 48–256 node terpisah dari preset respons; jumlah node respons dan tombol level tidak diubah. Satu pencarian MultiPV dan maksimal delapan respons dijalankan berurutan; pemeriksaan variasi dibagi dalam potongan sekitar 12 ms agar polling browser tetap responsif. Cache analisis dan cache langkah biasa dipisahkan.

Antrean milik aplikasi dibatalkan ketika posisi tidak sesuai cabang yang diperiksa, game/pengaturan berubah, mode riwayat/analisis dipilih, atau **Stop · Esc** ditekan. Antrean manual tidak ditimpa. Auto move menunggu selama ada antrean native. Penolakan situs dicoba maksimal dua kali per posisi dengan jeda satu detik; API yang kembali tersedia membuka percobaan baru. Prediksi cabang tetap berjalan ketika API native belum tersedia, tetapi tidak dihitung sebagai premove terpasang.

**Enable Premoves pada Chess.com harus ON.** Pengaturan situs yang OFF dapat membuat API premove hanya muncul saat pregame, lalu hilang ketika game berjalan. Panel mendeteksi kondisi tersebut dan menyediakan tombol pembuka pengaturan situs. Aplikasi tidak mengedit cache pengaturan akun, tidak menambahkan plugin palsu, dan tidak menganggap plugin pregame sebagai bukti premove selama game.

**Delay (ms)** 0–10000 ms (awal 1200) dan **Gerak kursor (ms)** 60–600 ms (awal 400) berlaku pada Auto move. **Time management** membaca jam pemain dan memendekkan delay ketika waktu tersisa kritis; **Adaptive delay** menambah waktu pada posisi bercabang atau taktis dan mengunci input Delay (ms) agar tidak bentrok. Matikan Adaptive delay untuk mengatur jeda manual. Preferensi lama tetap dipertahankan. Antrean premove dipasang melalui API situs; konsumsi dan waktu jam mengikuti aturan situs. Jika pengaturan menggulir papan ke luar layar, Auto move menampilkan papan kembali sebelum input mouse. Browser baru dibuka pada ukuran 1440×1000. Promosi Auto move memilih bidak rekomendasi otomatis, termasuk underpromotion; pemilih dideteksi lewat class, data attribute, atau label bidak. Jika pemilih tidak dikenali dalam 1,5 detik, otomatisasi dihentikan.

Pada Windows, paket menyertakan build Lc0 GPU DirectML sebagai jalur opsional. Saat GPU terdeteksi dan backend didukung binary, engine memilih GPU secara otomatis; jika tidak, engine memakai CPU DNNL/BLAS. Status backend dan alasan fallback tampil di panel. `LC0_FORCE_CPU=1` memaksa CPU, sedangkan `LC0_BACKEND` dapat memilih backend tertentu untuk diagnosis.

Panel menghitung **terpasang**, **terpakai**, **teramati**, **batal**, dan penolakan per game. Terpakai memerlukan event native dengan flag boolean `consumedPremove === true`, langkah yang cocok, dan FEN sesudah premove. Teramati berarti queue kosong dan FEN cocok tanpa event konsumsi yang terverifikasi; kedua jenis bukti tidak disamakan. Event ganda, fungsi yang kebetulan truthy, dan hasil dari game lain ditolak. Daemon menyimpan audit per game di `runtime/games/*.json`; gunakan `--audit-dir` untuk folder lain. Arsip distribusi tidak memuat audit atau sesi pengguna. Reload selalu mematikan otomatisasi.

Pemeriksaan: `python check_adaptive_strength.py` untuk policy fase dan batas node, `python check_premove.py` untuk cabang, advanced ranking, endgame, dan pembatalan, `python check_premove_engine.py` untuk MultiPV engine nyata dan pemisahan cache, `python check_engine_upgrade.py` untuk opening book dan batas MultiPV per Elo, `python check_premove_ui.py` untuk enam siklus queue/konsumsi/isi ulang dalam kontrak native terisolasi, `python check_time_management.py` untuk jalur jam normal/kritis/taktis, dan `python check_auto_moves.py` untuk mouse, promosi pintar, dan papan di luar layar. `python check_browser.py` memerlukan daemon di CDP 9222 dengan `--status runtime/v6-status.json`. Diagnosis opsional `python check_native_board.py` memerlukan papan situs yang disiapkan lokal, bukan match aktif. Uji terisolasi tidak membuktikan pertandingan online; V13 belum diuji ulang melawan manusia. Game online V9 sebelumnya hanya membuktikan Auto move.
