import re
from bs4 import BeautifulSoup

LIST_URL = "https://...{page}" #Sumber daftar SoC
DETAIL_URL = "https://...{slug}" #Sumber detail SoC

ANTUTU_VERSION = 11

VENDOR_PREFIXES = (
    "qualcomm_", "mediatek_", "samsung_", "apple_",
    "hisilicon_", "unisoc_", "google_", "xiaomi_",
)


def strip_vendor(slug: str) -> str:
    for p in VENDOR_PREFIXES:
        if slug.startswith(p):
            return slug[len(p):]
    return slug


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


def _split_pair(text):
    parts = str(text).split("/")
    a = _num(parts[0]) if len(parts) > 0 else None
    b = _num(parts[1]) if len(parts) > 1 else None
    return a, b


def parse_list_page(html: str) -> list:
    soup = BeautifulSoup(html, "lxml")
    records, seen = [], set()

    for table in soup.find_all("table"):
        headers = [th.get_text(" ", strip=True).lower() for th in table.find_all("th")]
        if not headers:
            first = table.find("tr")
            if first:
                headers = [c.get_text(" ", strip=True).lower() for c in first.find_all(["th", "td"])]
        if not any(h in ("processor", "cpu", "soc", "name") for h in headers):
            continue

        idx = {}
        for i, h in enumerate(headers):
            if "antutu" in h:
                idx.setdefault("antutu", i)
            elif "geekbench" in h:
                idx.setdefault("geekbench", i)
            elif "gpu" in h:
                idx.setdefault("gpu", i)
            elif "rating" in h:
                idx.setdefault("rating", i)

        for tr in table.find_all("tr"):
            a = tr.find("a", href=re.compile(r"^/en/soc/"))
            if not a:
                continue
            cells = tr.find_all("td")
            if not cells:
                continue
            slug = a["href"].replace("/en/soc/", "").strip("/")
            if not slug or slug in seen:
                continue
            seen.add(slug)

            texts = [c.get_text(" ", strip=True) for c in cells]

            def cell(key):
                i = idx.get(key)
                return texts[i] if i is not None and i < len(texts) else None

            gb_single, gb_multi = _split_pair(cell("geekbench"))

            records.append({
                "soc_raw": a.get_text(" ", strip=True),
                "soc_slug_raw": slug.replace("-", "_"),
                "antutu_total": _num(cell("antutu")),  
                "geekbench6_single": gb_single,
                "geekbench6_multi": gb_multi,
                "gpu_name": cell("gpu"),                      
                "rating": _num(cell("rating")),
            })

    if records:
        return records

    for a in soup.select('a[href^="/en/soc/"]'):
        name = a.get_text(" ", strip=True)
        slug = a["href"].replace("/en/soc/", "").strip("/")
        if not name or not slug or slug in seen:
            continue
        seen.add(slug)
        box, nums = a, []
        for _ in range(4):
            box = box.parent
            if box is None:
                break
            nums = re.findall(r"\b\d{4,7}\b", box.get_text(" ", strip=True))
            if len(nums) >= 2:
                break
        records.append({
            "soc_raw": name,
            "soc_slug_raw": slug.replace("-", "_"),
            "antutu_total": _num(nums[0]) if nums else None,
            "geekbench6_single": _num(nums[1]) if len(nums) > 1 else None,
            "geekbench6_multi": None,
            "gpu_name": None,
            "rating": None,
        })
    return records


def parse_soc_page(html: str) -> dict:
    import pandas as pd
    out = {"antutu_gpu": None}
    try:
        tables = pd.read_html(html)
    except Exception:
        tables = []
    for df in tables:
        flat = df.astype(str).apply(lambda r: " ".join(r).lower(), axis=1)
        for line in flat:
            if "gpu" in line:
                nums = re.findall(r"\b\d{5,7}\b", line)
                if nums:
                    out["antutu_gpu"] = int(nums[0])
                    break
        if out["antutu_gpu"]:
            break
    return out