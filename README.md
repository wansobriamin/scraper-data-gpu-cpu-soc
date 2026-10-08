# Scraper Web Benchmark GPU CPU SoC

Scraper *polite*, *incremental*, dan *robust* untuk mengumpulkan data benchmark
device (SoC mobile, CPU & GPU PC) Outputnya menjadi bahan baku kalibrasi performa ShaderBench.

## 🌟 Apa itu ShaderBench?
ShaderBench adalah alat analisis performa dan rekomendasi setting Minecraft berbasis web. Alih-alih hanya memberikan tebakan, aplikasi ini menggunakan pendekatan provenance-first (jujur terhadap asal-usul data) dan model fisika satu-skalar yang dipadukan dengan Machine Learning (Random Forest).
> ## 🔗 Repo ini adalah bagian pertama dari pipeline 3 repo
>
> ```
>   [1] scraper  ──►  [2] convert  ──►  [3] build  ──►  backend ShaderBench
>   (ambil data)     (normalisasi)    (kalibrasi)     (serving /predict)
> ```
>
> | Repo | URL | Peran |
> |---|---|---|
> | **scraper** (ini) | [`Scraper`](https://github.com/wansobriamin/scraper-data-gpu-cpu-soc) | Scrape benchmark mentah |
> | **convert** | [`convert`](https://github.com/<USERNAME>/shaderbench-convert) | Skor mentah → `gpu_index`/`cpu_index` (CSV staging) |
> | **build** | [`build`](https://github.com/<USERNAME>/shaderbench-build) | Kalibrasi beban shader + QC 3 lapis → DB final |
>
> **Repo ini hanya berisi kode.** Folder `data/` dan file `paths.py` dibuat sendiri
> mengikuti tutorial Setup di bawah.

---

## 1. Pengertian Kode

| File | Tanggung jawab |
|---|---|
| `scraper/fetcher.py` | `PoliteFetcher`: HTTP client sopan (jeda antar-request, cek `robots.txt`, cache disk SHA-256, header browser standar). |
| `scraper/parsers/soc.py` | Parser halaman list SoC (`parse_list_page`) dan detail SoC (`parse_soc_page`): slug, AnTuTu v11, GeekBench 6, nama GPU, rating. |
| `scraper/parsers/pc.py` | Parser ranking CPU/GPU (`parse_ranking_page`) dengan dua tahap: **tabel-ber-header** (3DMark/GeekBench/Cinebench) lalu **link-walk** fallback bila tabel tidak dikenali. |
| `scraper/run_scrape.py` | **Orkestrator pipeline**: list SoC → detail SoC → ranking PC → merge → panggil repo `convert` untuk normalisasi → simpan CSV staging → pembersihan spasi liar di `DB_DIR`. |

> ⚠️ Sebelum produksi, ganti placeholder `"https://..."` dengan URL sumber aktual
> dan isi `r["source"] = "<nama_situs>"` di `run_scrape.py`.

### 2 CLI
```bash
python -m scraper.run_scrape --delay 3 --pages 3 --details 60 --pc-pages 3
python -m scraper.run_scrape --force              # abaikan cache
python -m scraper.run_scrape --skip-pc            # hanya SoC mobile
python -m scraper.run_scrape --skip-soc           # hanya PC
python -m scraper.run_scrape --no-clean           # lewati clean_spaces
```

## 3. Setup Workspace

### 3.1 Buat root workspace

```bash
mkdir dataDevice && cd dataDevice
git clone https://github.com/wansobriamin/scraper-data-gpu-cpu-soc.git scraper
git clone https://github.com/<USERNAME>/shaderbench-convert.git convert   # WAJIB
git clone https://github.com/<USERNAME>/shaderbench-build.git   build     # opsional untuk build database
```

### 3.2 Buat `paths.py` di ROOT workspace (sejajar dengan folder repo)

```python
# dataDevice/paths.py
from pathlib import Path

ROOT = Path(__file__).resolve().parent
DATA_DIR = ROOT / "data"
RAW_DIR      = DATA_DIR / "raw"
STAGING_DIR  = DATA_DIR / "staging"
DB_DIR       = DATA_DIR / "db"

for _d in (RAW_DIR, STAGING_DIR, DB_DIR):
    _d.mkdir(parents=True, exist_ok=True)
```

### 3.3 Struktur akhir workspace

```text
dataDevice/                      ← ROOT eksekusi (cwd saat menjalankan)
├── paths.py                     ← file yang baru kamu buat
├── scraper/                     ← repo #1
│   └── scraper/{fetcher,run_scrape,parsers/...}
├── convert/                     ← repo #2
│   └── convert/{normalize_soc,normalize_pc}.py
├── build/                       ← repo #3 (opsional)
│   └── build/{...}
└── data/                        ← dibuat otomatis saat import paths.py
    ├── raw/        
    ├── staging/    
    ├── db/         
```

## 4. Etika & Lisensi

- Data benchmark adalah milik sumber publik masing-masing; scraper ini hanya
  mengagregasi untuk riset pribadi dan pengembangan ShaderBench.
- Hormati `robots.txt`, ToS situs, dan jaga delay minimum 2–3 detik.
- Jangan gunakan untuk scraping massal di luar kebutuhan kalibrasi.
- Kode ini disediakan apa adanya (as-is) untuk tujuan edukasi.

Copyright (c) 2026 wansobriamin
