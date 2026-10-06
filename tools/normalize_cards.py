"""スキャン 78 枚の傾きを補正し、黒い内枠を検出して切り抜き、新しく作った均一なクリーム色の縁に当て込む。
縁の色は代表(愚者)のスキャンの縁から取る。

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

TEMPLATE = 0          # 縁の色と縦横比の基準にするカード(0 = 愚者)
MARGIN_PX = 22        # 出力での縁の幅(px)
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


def deskew(im):
    """黒枠の上下の線の傾きから回転角を求め、水平に補正する。"""
    l, t, r, b = frame_box(im)
    g = np.asarray(im.convert("L")).astype(np.float32)
    dark = 255 - g
    xs = (l + 40, l + 240, r - 240, r - 40)

    def line_y(y0, y1):
        ys = []
        for x0, x1 in ((xs[0], xs[1]), (xs[2], xs[3])):
            prof = dark[y0:y1, x0:x1].mean(axis=1)
            ys.append(y0 + float((prof * np.arange(len(prof))).sum() / prof.sum()))
        return ys

    top = line_y(max(0, t - 20), t + 30)
    bot = line_y(b - 30, min(im.height, b + 20))
    dx = (xs[2] + xs[3]) / 2 - (xs[0] + xs[1]) / 2
    ang = np.degrees(np.arctan2(((top[1] - top[0]) + (bot[1] - bot[0])) / 2, dx))
    if abs(ang) < 0.03:
        return im, 0.0
    cream = tuple(int(v) for v in np.median(np.asarray(im)[t + 100:t + 400, max(0, l - 25):max(1, l - 8)].reshape(-1, 3), axis=0))
    return im.rotate(ang, Image.BICUBIC, fillcolor=cream), float(ang)


def make_border(tpl, box, size):
    """代表のスキャンの縁の色を取り、わずかなムラを付けた均一な縁の画像を作る。"""
    l, t, r, b = box
    a = np.asarray(tpl).astype(np.int16)
    patch = a[t + 100:t + 400, max(0, l - 25):max(1, l - 8)].reshape(-1, 3)
    cream = np.median(patch, axis=0)
    rng = np.random.default_rng(0)
    w, h = size
    noise = rng.normal(0, 2.2, size=(h, w, 1))
    img = np.clip(cream + noise, 0, 255).astype(np.uint8)
    return Image.fromarray(img)


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
    scans, boxes = [], []
    for f in FILES:
        im, ang = deskew(Image.open(CACHE / f).convert("RGB"))
        scans.append(im)
        boxes.append(frame_box(im))
        if abs(ang) >= 0.03:
            print(f"  傾き補正: {f} {ang:+.2f}°")

    # 絵の枠の大きさは代表の縦横比から決め、縁は新しく作る
    l, t, r, b = boxes[TEMPLATE]
    bw = WIDTH - 2 * MARGIN_PX
    bh = round(bw * (b - t + 1) / (r - l + 1))
    size = (WIDTH, bh + 2 * MARGIN_PX)
    template = make_border(scans[TEMPLATE], boxes[TEMPLATE], size)
    box = (MARGIN_PX, MARGIN_PX)
    print(f"出力: {size}, 絵の枠: {bw}x{bh}, 縁 {MARGIN_PX}px")

    thumbs, total = [], 0
    for i, (im, (l, t, r, b)) in enumerate(zip(scans, boxes)):
        art = im.crop((l, t, r + 1, b + 1))
        ratio = (art.width / art.height) / (bw / bh)
        if abs(ratio - 1) > 0.04:
            print(f"  注意: {FILES[i]} の枠の縦横比が代表と {ratio:.3f} 倍ずれている")
        art = art.resize((bw, bh), Image.LANCZOS)
        card = template.copy()
        card.paste(art, box)
        q, size_ = save_webp(card, OUT / f"{i:02d}.webp")
        total += size_
        thumbs.append(card.resize((120, round(card.height * 120 / card.width))))
        print(f"{i:02d}.webp  {FILES[i]:32s} crop=({l},{t},{r},{b}) q={q} {size_ // 1024}KB")

    # 確認用の一覧画像
    cols, tw, th = 13, 120, thumbs[0].height
    sheet = Image.new("RGB", (cols * (tw + 6), 6 * (th + 6)), (60, 60, 60))
    for i, tm in enumerate(thumbs):
        sheet.paste(tm, ((i % cols) * (tw + 6) + 3, (i // cols) * (th + 6) + 3))
    sheet.save(Path(__file__).parent / "_contact.jpg", quality=85)
    print(f"合計 {total // 1024}KB / 78枚, 平均 {total // 78 // 1024}KB")


if __name__ == "__main__":
    main()
