# シンプルタロット

息を吹きかけるとタロットカードが1枚引ける、ブラウザで動くアプリです。
HTMLファイル1つとカード画像だけで動き、フレームワークもビルド工程もサーバー処理もありません。

## 構成

| パス | 内容 |
|---|---|
| `index.html` | アプリ本体(HTML、CSS、JavaScript、78枚分の意味の文章) |
| `cards/00.webp` 〜 `cards/77.webp` | カード画像。0〜21 が大アルカナ、22〜35 棒、36〜49 杯、50〜63 剣、64〜77 金貨 |
| `cards/back.webp` | カードの裏面 |
| `tools/fetch_cards.py` | Wikimedia Commons から1909年版のスキャンを取得するスクリプト |
| `tools/normalize_cards.py` | スキャンの黒い内枠を検出して切り抜き、愚者の白枠に当て込んで位置をそろえ、WebP に変換するスクリプト |

## 引き方

- スマホ: カードをタップしてマイクを許可し、息を吹きかけると引けます。「指で混ぜて引く」も選べます。
- PC: カードをクリックすると引けます。
- 1枚引いたあと「もう1枚引く」で最大3枚まで足せます。2枚目以降は「状況・課題・助言」の3枚引きとして読みます。同じカードは2度出ません。

息の波形(または指やマウスの動き)と時刻を SHA-256 にかけ、ブラウザ標準の乱数と混ぜてもう一度 SHA-256 にかけた結果から、0〜77 の番号と正位置・逆位置を決めます。
音は端末の中だけで使い、保存も送信もしません。

## カード画像を作り直す

```bash
python tools/fetch_cards.py
python tools/normalize_cards.py
```

Pillow と NumPy が必要です。`cards/back.webp` が無い場合は仮の裏面を生成するので、自作した裏面画像に差し替えてください。

## 出典

- 画像: Pamela Colman Smith (1909)。[Wikimedia Commons](https://commons.wikimedia.org/wiki/Category:Rider-Waite_tarot_deck) のパブリックドメインのスキャン(Pam-A 版)
- 意味: A. E. Waite, [The Pictorial Key to the Tarot](https://sacred-texts.com/tarot/pkt/) (1911) の占的意味を要約・訳出
