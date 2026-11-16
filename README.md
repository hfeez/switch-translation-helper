# Switch Translation Helper

Alat bantu translasi game Nintendo Switch: load folder **romfs** → scan target teks → extract ke JSON →
import terjemahan → patch **CRC32** otomatis. UI PySide6, bahasa Indonesia / English.

## Jalankan (development)
    pip install -r requirements.txt
    python main.py

## Build (tinggal jalan)
| OS | Perintah | Hasil |
|---|---|---|
| Windows | `build.bat` (atau `build.bat onefile`) | `dist\SwitchTranslationHelper\SwitchTranslationHelper.exe` |
| Linux / macOS | `./build.sh` (atau `./build.sh onefile`) | `dist/SwitchTranslationHelper` (macOS: `.app`) |
| Semua OS via GitHub | Actions → *build* → Run workflow | artifact per OS |

Script build otomatis membuat venv, memasang dependensi, menjalankan tes, lalu PyInstaller.
Butuh Python 3.9+. PyInstaller tidak bisa cross-compile: build di OS target.

## Alur kerja
1. **Scan**: pilih romfs + folder output (+ keyword, mis. satu kalimat yang kamu lihat di game). Simpan hasil scan kapan saja.
2. **Extract**: centang file → `output/extracted/<path>.json`. Isi `translation`.
3. **Import**: pilih folder JSON → hasil ke `output/romfs_patched/` (file asli tidak diubah; siap untuk LayeredFS).
4. **CRC**: CRC tertanam (awal/akhir file) otomatis dikenali. CRC di file indeks: isi glob di kolom *File indeks CRC*.

## Struktur
    main.py            titik masuk
    stlh/core.py       mesin (scan, MSBT, JSON, teks, string biner, CRC) — tanpa dependensi
    stlh/ui.py         antarmuka PySide6
    tests/test_core.py `python -m unittest discover -s tests`

## Batasan
- Terjemahan di file biner tidak boleh lebih panjang dari ruang aslinya (MSBT bebas panjang).
- File terkompresi (zstd/Yaz0/LZ4) hanya ditandai; dekompres dulu dengan tool lain.
- CRC memakai CRC32 standar (zlib); ubah `crc32()` di `core.py` untuk varian lain.
- MSBT hanya UTF-16; label (LBL1) tidak ditampilkan.
- Bahasa disimpan di `~/.switch_translation_helper.json`.
