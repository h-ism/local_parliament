# 和歌山県議会 — 本会議会議録

Verified 2026-08-27. **Collectable, and the best target in the survey.**

## Verdict

Permitted and easy. UTF-8 throughout, one HTML page per sitting carrying the full
text, and a complete index of every session in a single page. No vendor system, no
session token, no encoding trap, no pagination.

## Access

- `https://www.pref.wakayama.lg.jp/robots.txt` → **404**. Nothing disallowed.
- Minutes pages carry `<meta name="robots" content="index, follow">` — the opposite
  of 静岡's `content="none"`, so none of the question raised in `docs/shizuoka.md`
  applies here.
- `https://www.pref.wakayama.lg.jp/gijiroku/` itself returns **403** — that is the
  directory index being switched off, not a block. Individual pages under it are
  200. The survey's earlier note that this path was the entry point was wrong; the
  entry point is the document below.

## Structure — three levels

1. **Index** — `/gijiroku/d00203238.html` (会議録の検索と閲覧).
   One page listing **every** session from 平成2年 to 令和8年 as `2月定例会` /
   `6月定例会` / `9月定例会` / `12月定例会`, roughly 150 links. Nothing to paginate.
   Two URL generations coexist and both resolve: older `p0NNNNN.html`, newer
   `d00NNNNN.html`.
2. **Session** — e.g. `/gijiroku/d00217972.html` (…会議録　目次).
   Links the sittings as `◎第１号全文` … `◎第８号全文`.
3. **Sitting** — e.g. `/gijiroku/d00217977.html`.
   ~186 KB, UTF-8, the whole sitting as one run of text. ~60,000 characters of
   transcript, 98 speech markers in the sample checked.

## Parsing notes

**Two speech-marker forms, not one.** 静岡's `speech_split` assumes every marker
carries parentheses. 和歌山 uses parentheses only for office-holders:

```
○議長（鈴木太雄君）　これより本日の会議を開きます。
○知事（岸本周平君）　お答え申し上げます。
○濱口太史君　皆さん、おはようございます。          ← bare member name
```

A pattern requiring 「（…君）」 would silently drop every member's own speech — the
majority of the corpus. The split rule needs an alternation, and the 「君」 suffix
still does the work of separating markers from the attendance roster (the lesson
from 静岡).

**Date** is in the header of the sitting, not the index:
`令和６年６月19日（水曜日）` — full-width digits, already handled by `dates.py`.
The session name is in the `<title>`: `令和6年6月　和歌山県議会定例会会議録　第3号`.

**Names are transliterated.** Every page carries a notice that text is rendered
within JIS 第1・2水準, so some personal names differ from the official record; the
site links a 人名等の正しい表記 page. Worth capturing as a corpus caveat — it is the
same class of problem as 静岡's cp932 characters, but here the *source* has already
lost the character, so no decoding fix can recover it.

## What the scraper still needs

`GenericScraper` has one listing level (`list.meeting_link` + `next_page`). This
site has two. See `docs/collection-targets.md` — the same gap blocks 愛媛.
