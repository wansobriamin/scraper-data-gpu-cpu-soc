import argparse
import json
from pathlib import Path

from paths import RAW_DIR, STAGING_DIR, DB_DIR
from .fetcher import PoliteFetcher
from .parsers.soc import (
    LIST_URL,
    DETAIL_URL,
    parse_list_page,
    parse_soc_page,
)
from .parsers.pc import RANKING_URLS, parse_ranking_page
from convert.normalize import normalize_all #File Convert Soc
from convert.normalize_pc import normalize_pc_all #File Convert GPU CPU


# Paths
RAW_JSON = RAW_DIR / "parsed.json"
DETAILS_CACHE = RAW_DIR / "details_cache.json"
PC_RAW_JSON = RAW_DIR / "parsed_pc.json"
OUT_SOC_CSV = STAGING_DIR / "benchmark_soc.csv"
OUT_PC_CPU_CSV = STAGING_DIR / "benchmark_pc_cpu.csv"
OUT_PC_GPU_CSV = STAGING_DIR / "benchmark_pc_gpu.csv"


# Konfigurasi sumber
SOC = {
    "enabled": True,
    "max_pages": 3,
    "detail_top_n": 60,
}

PC = {
    "enabled": True,
    "max_pages": 3,
}


# Helpers
def load_json(path: Path, default):
    if path.exists():
        try:
            text = path.read_text(encoding="utf-8").strip()
            if text:
                return json.loads(text)
            print(f"[warn] {path.name} kosong -> {type(default).__name__}")
        except json.JSONDecodeError:
            print(f"[warn] {path.name} rusak (bukan JSON) -> {type(default).__name__}")
        except Exception as e:
            print(f"[warn] {path.name} error: {e} -> {type(default).__name__}")
    return default


def save_json(path: Path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(data, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )


def clean_spaces(obj):
    if isinstance(obj, dict):
        return {str(k).strip(): clean_spaces(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [clean_spaces(x) for x in obj]
    if isinstance(obj, str):
        return obj.strip()
    return obj


def clean_all_db_json():
    print("\n[CLEAN] Membersihkan spasi liar di file database...")
    cleaned = 0
    for p in sorted(DB_DIR.glob("*.json")):
        try:
            text = p.read_text(encoding="utf-8").strip()
            if not text:
                continue
            data = json.loads(text)
            cleaned_data = clean_spaces(data)
            p.write_text(
                json.dumps(cleaned_data, indent=2, ensure_ascii=False),
                encoding="utf-8",
            )
            cleaned += 1
            print(f"  ✓ {p.name}")
        except json.JSONDecodeError as e:
            print(f"  ✗ {p.name}: JSON rusak ({e})")
        except Exception as e:
            print(f"  ✗ {p.name}: {e}")
    print(f"[CLEAN] {cleaned} file dibersihkan.\n")


# Main Pipeline
def main():
    ap = argparse.ArgumentParser(description="Polite incremental scraper")
    ap.add_argument("--delay", type=float, default=3.0,
                    help="Jeda antar request (detik, default 3)")
    ap.add_argument("--pages", type=int, default=None,
                    help="Jumlah halaman SoC list (default dari config)")
    ap.add_argument("--details", type=int, default=None,
                    help="Jumlah detail SoC yang diambil (default dari config)")
    ap.add_argument("--pc-pages", type=int, default=None,
                    help="Jumlah halaman PC (default dari config)")
    ap.add_argument("--force", action="store_true",
                    help="Paksa refresh, abaikan cache")
    ap.add_argument("--ignore-robots", action="store_true",
                    help="Bypass robots.txt check (untuk bypass Cloudflare)")
    ap.add_argument("--skip-soc", action="store_true",
                    help="Lewati scraping SoC mobile")
    ap.add_argument("--skip-pc", action="store_true",
                    help="Lewati scraping PC")
    ap.add_argument("--no-clean", action="store_true",
                    help="Jangan bersihkan spasi di database JSON")
    args = ap.parse_args()

    max_pages = args.pages or SOC["max_pages"]
    detail_top_n = args.details or SOC["detail_top_n"]
    pc_max_pages = args.pc_pages or PC["max_pages"]

    print("=" * 60)
    print("  Detail Device Scraper")
    print("=" * 60)
    print(f"  Delay: {args.delay}s | Pages: {max_pages} | Details: {detail_top_n}")
    print(f"  PC Pages: {pc_max_pages} | Ignore robots: {args.ignore_robots}")
    print(f"  Force: {args.force}")
    print("=" * 60)

    fetcher = PoliteFetcher(
        delay=args.delay,
        ignore_robots=args.ignore_robots,
    )

    # 1) SoC
    if not args.skip_soc and SOC["enabled"]:
        print("\n[1/2] SCRAPING SOC MOBILE")
        print("-" * 40)

        list_recs, seen = [], set()
        for page in range(1, max_pages + 1):
            html = fetcher.get(LIST_URL.format(page=page), force=args.force)
            if not html:
                print(f"  [stop] halaman {page} gagal/empty")
                break

            added = 0
            for r in parse_list_page(html):
                if r["soc_slug_raw"] in seen:
                    continue
                seen.add(r["soc_slug_raw"])
                r["source"] = "..." #Isi Source sumber scrapping
                r["source_url"] = LIST_URL.format(page=page)
                list_recs.append(r)
                added += 1

            print(f"  halaman {page}: +{added} SoC baru (total: {len(list_recs)})")
            if added == 0:
                print(f"  [stop] tidak ada SoC baru di halaman {page}")
                break

        details = load_json(DETAILS_CACHE, {})
        pending = [r for r in list_recs if r["soc_slug_raw"] not in details]
        batch = pending[:detail_top_n]

        print(f"\n  [INFO] Total SoC: {len(list_recs)}")
        print(f"  [INFO] Detail tersimpan: {len(details)}")
        print(f"  [INFO] Pending: {len(pending)}")
        print(f"  [INFO] Batch ini: {len(batch)}")

        if batch:
            print(f"\n  [FETCHING {len(batch)} detail pages...]")
            for i, r in enumerate(batch, 1):
                slug = r["soc_slug_raw"]
                url = DETAIL_URL.format(slug=slug.replace("_", "-"))
                print(f"  [{i}/{len(batch)}] {slug}", end=" ")

                html = fetcher.get(url, force=args.force)
                if not html:
                    print("✗")
                    continue

                info = parse_soc_page(html)
                info["detail_url"] = url
                details[slug] = info

                gpu = info.get("gpu_name") or "—"
                print(f"✓ GPU: {gpu}")

            save_json(DETAILS_CACHE, details)
        else:
            print("  [skip] tidak ada SoC baru yang butuh detail")

        raw = []
        for r in list_recs:
            d = details.get(r["soc_slug_raw"], {})
            merged = {**r, **{k: v for k, v in d.items() if v is not None}}
            raw.append(merged)

        save_json(RAW_JSON, raw)
        normalize_all(raw, OUT_SOC_CSV)

        with_gpu = sum(1 for r in list_recs if details.get(r["soc_slug_raw"], {}).get("gpu_name"))
        print(f"\n  [COVERAGE SoC] dengan GPU: {with_gpu}/{len(list_recs)}")
    else:
        print("\n[1/2] SKIPPED: SoC mobile (--skip-soc atau disabled)")

    # 2) PC
    if not args.skip_pc and PC["enabled"]:
        print("\n[2/2] SCRAPING PC (Desktop + Laptop)")
        print("-" * 40)

        pc_raw = []
        for (kind, form), base_url in RANKING_URLS.items():
            print(f"\n  [{kind.upper()} {form.upper()}]")
            seen_slugs = set()
            kind_total = 0

            for page in range(1, pc_max_pages + 1):
                url = base_url if page == 1 else f"{base_url}?page={page}"
                html = fetcher.get(url, force=args.force)
                if not html:
                    print(f"    [stop] halaman {page} gagal/empty")
                    break

                recs = parse_ranking_page(html, kind, form)
                new = [r for r in recs if r["slug_raw"] not in seen_slugs]

                for r in new:
                    seen_slugs.add(r["slug_raw"])
                    r["source"] = "..." #Isi Source sumber scrapping
                    r["source_url"] = url

                pc_raw.extend(new)
                kind_total += len(new)
                print(f"    halaman {page}: +{len(new)} entri (total: {kind_total})")

                if not new:
                    print(f"    [stop] tidak ada entri baru di halaman {page}")
                    break

        save_json(PC_RAW_JSON, pc_raw)
        normalize_pc_all(pc_raw, OUT_PC_CPU_CSV, OUT_PC_GPU_CSV)

        cpu_count = sum(1 for r in pc_raw if r.get("kind") == "cpu")
        gpu_count = sum(1 for r in pc_raw if r.get("kind") == "gpu")
        desktop_count = sum(1 for r in pc_raw if r.get("form_factor") == "desktop")
        laptop_count = sum(1 for r in pc_raw if r.get("form_factor") == "laptop")

        print(f"\n  [SUMMARY PC]")
        print(f"    Total entri: {len(pc_raw)}")
        print(f"    CPU: {cpu_count} (desktop: {sum(1 for r in pc_raw if r.get('kind')=='cpu' and r.get('form_factor')=='desktop')}, laptop: {sum(1 for r in pc_raw if r.get('kind')=='cpu' and r.get('form_factor')=='laptop')})")
        print(f"    GPU: {gpu_count} (desktop: {sum(1 for r in pc_raw if r.get('kind')=='gpu' and r.get('form_factor')=='desktop')}, laptop: {sum(1 for r in pc_raw if r.get('kind')=='gpu' and r.get('form_factor')=='laptop')})")
    else:
        print("\n[2/2] SKIPPED: PC (--skip-pc atau disabled)")

    # 3) CLEAN SPACES
    if not args.no_clean:
        clean_all_db_json()

    print("\n" + "=" * 60)
    print("  SCRAPER SELESAI")
    print("=" * 60)


if __name__ == "__main__":
    main()