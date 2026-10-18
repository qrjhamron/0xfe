# V6 — kalibrasi level latihan 1500–2300

**624 game kalibrasi + 108 game validasi preset terpilih + 12 game diagnostik yang diarsipkan = 744 game yang diverifikasi.**

Angka tombol adalah target latihan tetap. Estimasi di bawah relatif terhadap setelan UCI_Elo Stockfish 19, bukan Elo Chess.com/FIDE yang terverifikasi. Interval 95% hanya mencerminkan variasi sampel; bias setelan lawan, waktu berpikir, perangkat, pemilihan kandidat dan bukaan tidak seluruhnya tercakup.

| Tombol | Estimasi lokal gabungan | Interval sampel 95% | Kalibrasi W–D–L (48) | Validasi W–D–L (12) |
|---|---:|---:|---:|---:|
| 1500 | 1438 | 1321–1548 | 5–10–33 | 4–3–5 |
| 1600 | 1560 | 1438–1679 | 12–9–27 | 2–4–6 |
| 1700 | 1794 | 1699–1889 | 18–5–25 | 4–2–6 |
| 1800 | 1889 | 1771–2008 | 17–12–19 | 6–1–5 |
| 1900 | 1913 | 1830–1996 | 16–18–14 | 3–5–4 |
| 2000 | 1901 | 1818–1984 | 19–13–16 | 2–5–5 |
| 2100 | 2224 | 2114–2335 | 27–11–10 | 4–4–4 |
| 2200 | 2273 | 2163–2373 | 25–16–7 | 5–5–2 |
| 2300 | 2273 | 2139–2412 | 30–7–11 | 5–4–3 |

## Metode

Tiga belas kandidat masing-masing memainkan 48 game pada 24 bukaan dengan warna ditukar. Lawan acuan: 1320, 1700, 2100 dan 2500; masing-masing 12 game per kandidat. Dua kandidat dipertimbangkan untuk level 1500, lalu satu dipilih melalui aturan yang dicatat di konfigurasi. Dua kandidat untuk 1900/2000 diurutkan menurut estimasi hasil kalibrasi, bukan semata jumlah pencarian. Kandidat menengah lain ditentukan sebelumnya; dua kandidat perantara level tinggi dipilih dari hasil kalibrasi awal. Pilihan tiap preset dikunci sebelum validasi preset itu dijalankan. Refinemen level tinggi tidak memakai hasil validasi.

Sembilan preset terpilih menjalani 12 game tambahan pada enam bukaan berbeda, warna ditukar, melawan dua setelan acuan di sekitar targetnya. Tidak ada perubahan preset berdasarkan hasil validasi. Estimasi gabungan menggunakan 60 game per preset. Empat kandidat yang tidak terpilih serta 12 game validasi dari kandidat 2100 yang diganti tetap tersimpan sehingga total 744 game dapat diaudit. Ini validasi kecil, bukan pembuktian rating manusia.

Satu thread per engine, hash lawan 16 MiB, 50 ms per langkah untuk lawan, backend CPU lokal. Batas pencarian kandidat dicatat per game, dengan plafon waktu 2 detik. Prefetch dimatikan agar tidak memboroskan evaluasi di luar kebutuhan pencarian kecil. Pilihan langkah lawan acuan bersifat stokastik; pengulangan baru dapat memberi hasil berbeda. Jumlah node aktual dan latensi setiap langkah kandidat disimpan. Tidak ada injeksi kesalahan acak atau filter lawan yang menggantikan langkah model.

Skor menang=1, seri=0,5. Estimasi memakai rumus ekspektasi Elo logistik. Interval memakai 5.000 bootstrap pasangan bukaan/warna, dikelompokkan menurut setelan lawan. Untuk estimasi gabungan, ID bukaan validasi dipisahkan dari bukaan kalibrasi. Tidak ada adjudikasi berdasarkan evaluasi. Klaim seri tiga kali posisi/50 langkah diterapkan; batas 300 ply menghasilkan seri administratif yang dilaporkan terpisah.

Interval antarlevel bisa tumpang tindih. Nilai yang berbeda 100 pada tombol tidak berarti perbedaan kekuatan 100 Elo telah terbukti. Label yang berada di luar interval hasilnya ditandai di bawah dan harus diperlakukan sebagai target nominal, bukan rating terukur.

## Pemeriksaan label

- 1500: selisih estimasi terhadap target -62; target di dalam interval sampel: ya; seri administratif: 0.
- 1600: selisih estimasi terhadap target -40; target di dalam interval sampel: ya; seri administratif: 0.
- 1700: selisih estimasi terhadap target +94; target di dalam interval sampel: ya; seri administratif: 0.
- 1800: selisih estimasi terhadap target +89; target di dalam interval sampel: ya; seri administratif: 0.
- 1900: selisih estimasi terhadap target +13; target di dalam interval sampel: ya; seri administratif: 0.
- 2000: selisih estimasi terhadap target -99; target di dalam interval sampel: tidak; seri administratif: 0.
- 2100: selisih estimasi terhadap target +124; target di dalam interval sampel: tidak; seri administratif: 0.
- 2200: selisih estimasi terhadap target +73; target di dalam interval sampel: ya; seri administratif: 0.
- 2300: selisih estimasi terhadap target -27; target di dalam interval sampel: ya; seri administratif: 0.
