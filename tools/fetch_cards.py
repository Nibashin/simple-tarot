"""Wikimedia Commons から 1909 年版(Pam-A)のスキャン 78 枚を取得し、幅 400px の WebP に変換する。

使い方:  python tools/fetch_cards.py
出力:    cards/00.webp ... cards/77.webp (大アルカナ 0-21、棒 22-35、杯 36-49、剣 50-63、金貨 64-77)
         cards/back.webp は別途用意する(無ければ仮の裏面を生成する)
"""
import io
import json
import os
import sys
import urllib.request
from pathlib import Path

from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "cards"
CACHE = Path(os.environ.get("TAROT_CACHE", ROOT / "tools" / "_cache"))
UA = "simple-tarot-build/1.0 (https://github.com/Nibashin/simple-tarot)"
WIDTH = 400
TARGET_KB = 40

MAJORS = [
    "00_Fool", "01_Magician", "02_High_Priestess", "03_Empress", "04_Emperor",
    "05_Hierophant", "06_Lovers", "07_Chariot", "08_Strength", "09_Hermit",
    "10_Wheel_of_Fortune", "11_Justice", "12_Hanged_Man", "13_Death", "14_Temperance",
    "15_Devil", "16_Tower", "17_Star", "18_Moon", "19_Sun", "20_Judgement", "21_World",
]
SUITS = ["Wands", "Cups", "Swords", "Pents"]

FILES = [f"RWS_Tarot_{m}.jpg" for m in MAJORS]
for suit in SUITS:
    FILES += [f"{suit}{n:02d}.jpg" for n in range(1, 15)]
assert len(FILES) == 78


def api(params):
    url = "https://commons.wikimedia.org/w/api.php?format=json&" + urllib.parse.urlencode(params)
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=60) as r:
        return json.load(r)


def fetch(url):
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=120) as r:
        return r.read()


def to_webp(data, dest):
    im = Image.open(io.BytesIO(data)).convert("RGB")
    h = round(im.height * WIDTH / im.width)
    im = im.resize((WIDTH, h), Image.LANCZOS)
    # 目標サイズに収まる最高画質を探す
    for q in (82, 76, 70, 64, 58, 52, 46, 40):
        buf = io.BytesIO()
        im.save(buf, "WEBP", quality=q, method=6)
        if buf.tell() <= TARGET_KB * 1024:
            break
    dest.write_bytes(buf.getvalue())
    return q, buf.tell()


def make_back(dest):
    """仮の裏面。上下対称の幾何学模様。ChatGPT で作った画像に差し替える前提。"""
    w, h = WIDTH, 665
    im = Image.new("RGB", (w, h), (24, 28, 64))
    d = ImageDraw.Draw(im)
    gold = (196, 160, 72)
    for i in range(4):
        m = 12 + i * 10
        d.rectangle([m, m, w - m, h - m], outline=gold, width=2)
    cx, cy = w // 2, h // 2
    for r in (120, 90, 60):
        d.ellipse([cx - r, cy - r, cx + r, cy + r], outline=gold, width=2)
    # 中央の八芒星
    import math
    pts = []
    for k in range(16):
        r = 60 if k % 2 == 0 else 26
        a = math.pi / 8 * k
        pts.append((cx + r * math.cos(a), cy + r * math.sin(a)))
    d.polygon(pts, fill=gold)
    im.save(dest, "WEBP", quality=80, method=6)


def main():
    import urllib.parse  # noqa: F401 (api() で使用)
    OUT.mkdir(exist_ok=True)
    CACHE.mkdir(parents=True, exist_ok=True)

    # 50 枚ずつ URL と説明文を取得
    info = {}
    for i in range(0, len(FILES), 50):
        chunk = FILES[i:i + 50]
        res = api({
            "action": "query",
            "titles": "|".join("File:" + f for f in chunk),
            "prop": "imageinfo",
            "iiprop": "url|extmetadata",
        })
        for page in res["query"]["pages"].values():
            if "imageinfo" not in page:
                sys.exit(f"見つからない: {page.get('title')}")
            ii = page["imageinfo"][0]
            desc = ii.get("extmetadata", {}).get("ImageDescription", {}).get("value", "")
            lic = ii.get("extmetadata", {}).get("LicenseShortName", {}).get("value", "")
            name = page["title"][5:].replace(" ", "_")
            info[name] = (ii["url"], desc, lic)

    total = 0
    for idx, name in enumerate(FILES):
        url, desc, lic = info[name]
        if "Pam-A" not in desc or lic != "Public domain":
            sys.exit(f"版かライセンスが想定と違う: {name}: {lic} / {desc[:80]}")
        cached = CACHE / name
        if not cached.exists():
            cached.write_bytes(fetch(url))
        dest = OUT / f"{idx:02d}.webp"
        q, size = to_webp(cached.read_bytes(), dest)
        total += size
        print(f"{dest.name}  {name:32s} q={q} {size // 1024}KB")

    back = OUT / "back.webp"
    if not back.exists():
        make_back(back)
        print("back.webp を仮生成しました(ChatGPT で作った画像に差し替えてください)")
    print(f"合計 {total // 1024}KB / 78枚, 平均 {total // 78 // 1024}KB")


if __name__ == "__main__":
    import urllib.parse
    main()
