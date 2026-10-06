"""スキャン 78 枚の黒い内枠を検出して切り抜き、1 枚の代表的な白枠(愚者)に当て込んで位置をそろえる。
代表の白枠は、カードの外にあるスキャン台の真っ白な帯を切り落とし、丸い角の白をクリーム色で埋める。

使い方:  python tools/fetch_cards.py   (先にスキャンをキャッシュしておく)
         python tools/normalize_cards.py
出力:    cards/00.webp ... cards/77.webp と、確認用の tools/_contact.jpg
"""
import io
import os
from pathlib import Path

import numpy as np
from PIL import Image

from fetch_cards import CACHE, FILES, OUT, TARGET_KB, WIDTH

TEMPLATE = 0          # 白枠の代表に使うカード(0 = 愚者)
WHITE = 232           # これより明るい画素は「スキャン台の白」とみなす
DARK = 90             # これより暗い画素を「黒」とみなす
LINE = 0.55           # 行・列のうち黒が占める割合がこれ以上なら枠線
MARGIN = 0.01         # 画像の外周(スキャンの縁)は無視する


def frame_box(im):
    """黒枠の外側の縁 (left, top, right, bottom) を返す。right/bottom は含む。"""
    g = np.asarray(im.convert("L"))
    h, w = g.shape
    dark = g < DARK
    mx, my = int(w * MARGIN), int(h * MARGIN)
    # まず左右の枠線(縦線)を見つけ、その内側だけで上下の枠線(横線)を測る。
    # 線がかすれている場合は、枠として妥当な大きさになるまで判定を緩める
    col = dark[my:h - my, :].mean(axis=0)
    for line in (LINE, 0.45, 0.35, 0.25):
        cols = np.where(col[mx:w - mx] >= line)[0] + mx
        if len(cols) < 2 or cols[-1] - cols[0] < 0.7 * w:
            continue
        l, r = int(cols[0]), int(cols[-1])
        row = dark[:, l:r + 1].mean(axis=1)
        rows = np.where(row[my:h - my] >= line)[0] + my
        if len(rows) < 2 or rows[-1] - rows[0] < 0.7 * h:
            continue
        return l, int(rows[0]), r, int(rows[-1])
    raise RuntimeError("枠線が見つからない")


def clean_template(im, box):
    """スキャン台の白い帯を切り落とし、丸い角の外の白をクリーム色で埋める。黒枠の座標も合わせて返す。"""
    a = np.asarray(im).astype(np.int16)
    white = a.min(axis=2) > WHITE
    cols = np.where(white.mean(axis=0) < 0.5)[0]
    rows = np.where(white.mean(axis=1) < 0.5)[0]
    x0, x1, y0, y1 = int(cols[0]), int(cols[-1]) + 1, int(rows[0]), int(rows[-1]) + 1
    a = a[y0:y1, x0:x1].copy()
    white = white[y0:y1, x0:x1]
    h, w = white.shape
    # 縁のクリーム色(黒枠の外側の帯)を取り、四隅の白い画素をそれで埋める
    l, t, r, b = box
    cream = np.median(a[t + 100:t + 400, max(0, l - x0 - 25):max(1, l - x0 - 8)].reshape(-1, 3), axis=0)
    rng = np.random.default_rng(0)
    corner = np.zeros((h, w), bool)
    c = 110
    corner[:c, :c] = corner[:c, w - c:] = corner[h - c:, :c] = corner[h - c:, w - c:] = True
    fill = white & corner
    noise = rng.integers(-4, 5, size=(int(fill.sum()), 3))
    a[fill] = np.clip(cream + noise, 0, 255)
    im2 = Image.fromarray(a.astype(np.uint8))
    return im2, (l - x0, t - y0, r - x0, b - y0)


def save_webp(im, dest):
    for q in (82, 76, 70, 64, 58, 52, 46, 40):
        buf = io.BytesIO()
        im.save(buf, "WEBP", quality=q, method=6)
        if buf.tell() <= TARGET_KB * 1024:
            break
    dest.write_bytes(buf.getvalue())
    return q, buf.tell()


def main():
    OUT.mkdir(exist_ok=True)
    scans = [Image.open(CACHE / f).convert("RGB") for f in FILES]
    boxes = [frame_box(im) for im in scans]

    # 代表の白枠: 外側の真っ白な帯を切り落とし、四隅の白をクリーム色で埋める
    tpl, (l, t, r, b) = clean_template(scans[TEMPLATE], boxes[TEMPLATE])
    s = WIDTH / tpl.width
    template = tpl.resize((WIDTH, round(tpl.height * s)), Image.LANCZOS)
    box = (round(l * s), round(t * s), round((r + 1) * s), round((b + 1) * s))
    bw, bh = box[2] - box[0], box[3] - box[1]
    print(f"白枠: {template.size}, 絵の枠: {box} ({bw}x{bh})")

    thumbs, total = [], 0
    for i, (im, (l, t, r, b)) in enumerate(zip(scans, boxes)):
        art = im.crop((l, t, r + 1, b + 1))
        ratio = (art.width / art.height) / (bw / bh)
        if abs(ratio - 1) > 0.04:
            print(f"  注意: {FILES[i]} の枠の縦横比が代表と {ratio:.3f} 倍ずれている")
        art = art.resize((bw, bh), Image.LANCZOS)
        card = template.copy()
        card.paste(art, (box[0], box[1]))
        q, size = save_webp(card, OUT / f"{i:02d}.webp")
        total += size
        thumbs.append(card.resize((120, round(card.height * 120 / card.width))))
        print(f"{i:02d}.webp  {FILES[i]:32s} crop=({l},{t},{r},{b}) q={q} {size // 1024}KB")

    # 確認用の一覧画像
    cols, tw, th = 13, 120, thumbs[0].height
    sheet = Image.new("RGB", (cols * (tw + 6), 6 * (th + 6)), (60, 60, 60))
    for i, tm in enumerate(thumbs):
        sheet.paste(tm, ((i % cols) * (tw + 6) + 3, (i // cols) * (th + 6) + 3))
    sheet.save(Path(__file__).parent / "_contact.jpg", quality=85)
    print(f"合計 {total // 1024}KB / 78枚, 平均 {total // 78 // 1024}KB")


if __name__ == "__main__":
    main()
