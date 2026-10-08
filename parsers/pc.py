import re
from bs4 import BeautifulSoup

RANKING_URLS = {
    ("cpu", "desktop"): "https://...", #Sumber scraping data cpu desktop
    ("cpu", "laptop"):  "https://...", #Sumber scraping data cpu laptop
    ("gpu", "desktop"): "https://...", #Sumber scraping data gpu desktop
    ("gpu", "laptop"):  "https://...", #Sumber scraping data gpu laptop
}

GPU_FILLER = ("geforce_", "radeon_", "graphics_", "gpu_")


def clean_slug(slug: str, kind: str) -> str:
    s = str(slug).replace("-", "_").strip("_").lower()
    if kind == "gpu":
        for f in GPU_FILLER:
            s = s.replace(f, "_")
        s = re.sub(r"_+", "_", s).strip("_")
    return s


def _num(text):
    if text is None:
        return None
    m = re.search(r"\d[\d,\.]*", str(text))
    if not m:
        return None
    try:
        return int(float(m.group(0).replace(",", "")))
    except ValueError:
        return None


def _header_indexes(headers, kind):
    idx = {}
    for i, h in enumerate(headers):
        hl = h.lower()
        if kind == "gpu":
            if ("3dmark" in hl) or ("time spy" in hl):
                idx.setdefault("score_3dmark", i)
            elif ("opencl" in hl) or ("geekbench" in hl):
                idx.setdefault("score_geekbench", i)
            elif "flops" in hl:
                idx.setdefault("tflops", i)
            elif "rating" in hl:
                idx.setdefault("rating", i)
        else:  
            if "cinebench" in hl and "multi" in hl:
                idx.setdefault("cb_multi", i)
            elif "cinebench" in hl and "single" in hl:
                idx.setdefault("cb_single", i)
            elif "cinebench" in hl:
                idx.setdefault("cb_single", i)  
            elif "rating" in hl or "score" in hl:
                idx.setdefault("rating", i)
    return idx


def _primary(rec, kind):
    if kind == "gpu":
        return rec.get("score_3dmark") or rec.get("score_geekbench") or rec.get("rating")
    return rec.get("cb_multi") or rec.get("cb_single") or rec.get("rating")


def parse_ranking_page(html: str, kind: str, form_factor: str) -> list:
    soup = BeautifulSoup(html, "lxml")
    records, seen = [], set()
    prefix = f"/en/{kind}/"

    # Stage 1 : Tabel dengan Header
    for table in soup.find_all("table"):
        headers = [th.get_text(" ", strip=True) for th in table.find_all("th")]
        if not headers:
            first_row = table.find("tr")
            if first_row:
                headers = [c.get_text(" ", strip=True) for c in first_row.find_all(["th", "td"])]
        if not headers:
            continue
            
        if not any(h.lower().strip() in ("gpu", "cpu", "name", "model", "processor", "graphics card") for h in headers):
            continue

        idx = _header_indexes(headers, kind)

        for tr in table.find_all("tr"):
            a = tr.find("a", href=re.compile("^" + prefix))
            if not a:
                continue
            cells = tr.find_all("td")
            if not cells:
                continue
                
            slug_raw = a["href"].replace(prefix, "").strip("/")
            if not slug_raw or slug_raw in seen:
                continue
            seen.add(slug_raw)

            texts = [c.get_text(" ", strip=True) for c in cells]
            rec = {
                "name_raw": a.get_text(" ", strip=True),
                "slug_raw": clean_slug(slug_raw, kind),
                "kind": kind,
                "form_factor": form_factor,
            }
            for key, i in idx.items():
                rec[key] = _num(texts[i]) if i < len(texts) else None
                
            rec["primary_score"] = _primary(rec, kind)
            if rec["primary_score"]:
                records.append(rec)

    if records:
        return records

    # Stage 2: Link-walk
    for a in soup.select(f'a[href^="{prefix}"]'):
        name = a.get_text(" ", strip=True)
        slug_raw = a["href"].replace(prefix, "").strip("/")
        if not name or not slug_raw or slug_raw in seen:
            continue
        seen.add(slug_raw)

        box, nums = a, []
        for _ in range(5):
            box = box.parent
            if box is None:
                break
            nums = re.findall(r"\b\d{3,7}\b", box.get_text(" ", strip=True))
            if len(nums) >= 2:
                break

        rec = {
            "name_raw": name,
            "slug_raw": clean_slug(slug_raw, kind),
            "kind": kind,
            "form_factor": form_factor,
            "primary_score": _num(nums[0]) if nums else None,
            "score_geekbench": _num(nums[1]) if len(nums) > 1 else None,
        }
        if rec["primary_score"]:
            records.append(rec)

    if not records:
        for table in soup.find_all("table")[:3]:
            hs = [th.get_text(" ", strip=True) for th in table.find_all("th")]
            print(f"  [debug] header tabel {kind} {form_factor}: {hs[:8]}")

    return records