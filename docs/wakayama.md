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

## Implemented

`sites/wakayama.toml`, on the intermediate listing level added to `GenericScraper`
(`list.index_link` / `index_include` / `max_depth`, plus a symmetric `list.include`).

Verified against live pages, three ways:

| Run | Result |
| --- | --- |
| 令和6年6月定例会 (`d00217972`) | 8 sittings, 520 speeches, 222,065 chars, 2024-06-11 .. 06-28 |
| 平成12年12月定例会 (`p040100`) | 7 sittings, 326 speeches, 250,469 chars, 2000-12-01 .. 12-19 |
| Full index, `--limit 3` | walks index → session → sitting unaided |

37 distinct speakers in the first run, no empty speaker, roles correctly separated
from names.

## Two more found by collecting 2020–2025

**4. The whole-sitting link is labelled two different ways.** Most sessions call it
「◎第３号全文」, but 令和2年2月, 令和2年4月 and 令和2年5月 call it 「◎第１号本文」.
Filtering on 全文 dropped **12 of the 199 sittings in 2020–2025 — three entire
sessions — with no warning**, because a session page that yields no links is
indistinguishable from a session that was never asked for. There is no
"zero speeches" smoke test at the listing level.

The fix is to match the leading 「◎」 rather than the word. 「◎」 prefixes the
whole-sitting link in every generation checked (199/199 across the 30 sessions of
2020–2025) and never prefixes a member slice.

**5. One index link is simply broken.** The 令和7年6月 session page (`d00220752`)
links its 第6号 as a truncated 「◎第」 whose href points at `d00217979` — a 令和6年
document — so 令和7年6月第6号 is unreachable from the site's own index. The document
exists: `d00220760.html` returns 「令和7年6月　和歌山県議会定例会会議録　第6号（全文）」,
verified 2026-08-27. It is listed in `list.extra_meeting_urls` so the corpus stays
complete and still reproducible from the config.

Following the broken link is harmless — it resolves to a document already collected
from its own session page, and the record dates and titles itself correctly from
its own content — but it is worth raising with 議事課.

## Collected

| Range | Meetings | Speeches | Note |
| --- | ---: | ---: | --- |
| 1989-02-27 .. 2011-02 | 673 | — | not in the 地方議会会議録コーパス (starts 2011-04) |
| 2011-04 .. 2019-03 | — | — | **skipped** — covered by that corpus |
| 2019-05 .. 2019-12 | 25 | — | not in it either (that corpus ends 2019-03) |
| 2020-02-20 .. 2025-12-19 | 199 | 14,366 | |
| **total on disk** | **907** | **46,839** | 27,358,983 chars, 410 speakers |

The 2019 gap is easy to miss: the corpus runs on fiscal years (2011-04 .. 2019-03),
so 2019年5月臨時会 onwards falls between it and any collection that starts at 2020.

**Known gap: one undated record.** 平成8年6月第6号 (`p042602`) prints its date as
「平成八年**七年**十日（水曜日）」 — a typo for 七**月** in the source. The date filter
is deliberately anchored on 「（…曜日）」 to avoid picking up a date mentioned in
passing, and loosening it to rescue this one record would risk mis-dating others.
The true date is **1996-07-10**, which the same page gives correctly elsewhere as
「平成８年７月10日」.

## Two more found by parsing 907 documents

**6. The name must be matched lazily.** Greedy `{1,24}` runs past the real name to
a later 「君」 in the speech itself — 「○林　隆一君　知事、大変失礼いたしました。林君」
became a single 21-character speaker. Lazy matching fixed 3 records and changed the
speech count by **zero**, so it is strictly better.

**7. 〇 is a numeral and 「君」 is an ordinary word.** The 「君」 suffix rejects
「二〇〇三年度」 but not 「例えば二〇年後、三〇年後、君が四〇歳を過ぎ」 or
「子供一一〇番の家であるきしゅう君の家」 — 4 false speakers over 907 documents. A real
marker never follows a digit, so a negative lookbehind on
`[0-9０-９一二三四五六七八九十百千〇]` settles it: 46,843 → 46,839, and all four
removed matches are false positives.

Two alternatives were measured over the whole corpus and **rejected**:

| Rule | False positives killed | Real speeches lost |
| --- | ---: | ---: |
| Anchor marker to line start | 4 | **7** — 「〔「異議なし」と呼ぶ者あり〕 ○議長（濱口太史君）…」 |
| Require whitespace after marker | 4 | **15** — 「○浜本　収君（続）」, and older sittings with no space |
| **Lookbehind on numerals** | **4** | **0** |

The lesson is the measurement, not the regex: each candidate looked reasonable, and
only counting what it caught *and what it lost* across the whole corpus separated
them.

## Three traps this site set, all of the same kind

Each is a case of "one form is not all forms", and each fails *silently*.

1. **Bare member names.** Handled by making the office prefix optional — see above.
   静岡's rule scored 72 of 98 on 令和6年6月第3号.

2. **The circle is two different characters.** Most documents mark speeches with
   ○ (U+25CB), but 令和6年6月第1号 uses 〇 (U+3007, IDEOGRAPHIC NUMBER ZERO) for all
   21 of its speeches. The first live run parsed that sitting to zero speeches and
   said so; nothing else would have shown it. Accepting both recovered 21 speeches
   and changed no other document's count over a six-document sample.

3. **〇 is also a numeral.** 平成12年12月第2号 contains 53 of them inside body text
   (「二〇〇三年度」). Requiring the name to end in 「君」 rejects every one — the same
   requirement that keeps the attendance roster out, doing double duty.

**Checked and not a problem here:** the 議長 addresses women as さん in speech
(「６番森礼子さん」), which would break a 「君」-only rule. But the *markers* use 君 for
every member regardless of gender. Verified across nine documents: zero markers
ending in さん or 氏. Do not assume this carries to another prefecture.

## Dates

The archive changes numeral form partway through — 「令和６年６月19日（水曜日）」 in
recent years, 「平成十二年十二月八日（金曜日）」 before that. `dates.py` gained a
漢数字 reader for this (`kanji_to_int`), which also covers 「昭和六十一年」 and so will
be needed again for 兵庫.
