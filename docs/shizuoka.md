# 静岡県議会 — site notes (2026-08-26)

The first prefecture in this project with a working `sites/*.toml`. It is also the
first with a courtesy question attached, so read the second half before running a
full crawl.

## Where the minutes are

`www.pref.shizuoka.jp/kensei/kengikai/` links to two applications on a **different
host**:

| | URL | Contents |
| --- | --- | --- |
| 本会議会議録 | `https://www2.pref.shizuoka.jp/all/ggiji.nsf/` | plenary, 平成11年5月臨時会 onwards |
| 委員会会議録 | `https://www2.pref.shizuoka.jp/all/comgiji.nsf/index` | committees (not yet surveyed) |

Both are Lotus Domino applications serving Shift_JIS HTML over plain GET —
exactly the shape `GenericScraper` wants, and `sniff_encoding` already handles the
encoding.

### Structure

Five views over the same documents:

```
/all/ggiji.nsf/WebView1?OpenView   開催別   ← the one the config uses
/all/ggiji.nsf/WebView2?OpenView   知事提案
/all/ggiji.nsf/WebView3?OpenView   議員別
/all/ggiji.nsf/WebView4?OpenView   代表質問
/all/ggiji.nsf/WebView5?OpenView   一般質問
/all/ggiji.nsf/WebSearch           全文検索
```

`WebView1` is a collapsible tree of 議会 → documents. Appending `&ExpandView`
opens every 議会 at once, which is why the config needs no pagination. Individual
documents are `/all/ggiji.nsf/<view-id>/<doc-id>?OpenDocument`.

**One document is one 発言単位**, not one sitting: a member's question together
with every answer to it, or a 報告事項, 知事提案説明, or 委員長報告. A 令和7年6月
定例会 yields 26 documents. So a `Meeting` record here is finer-grained than the
name suggests — worth remembering when counting "meetings" downstream.

Document metadata is a Domino table with no classes or ids, labelled only by the
neighbouring cell's text (質問者：/ 質問分類 / 質問日：/ 会派名：), and the transcript
body is one run of text with 「○」 marking each speaker:

```
○議長（竹内良訓君）　質疑及び一般質問を行います。
○六番（赤堀慎吾君）　おはようございます。
○知事（鈴木康友君）　赤堀議員にお答えをいたします。
```

Neither shape can be expressed in CSS, which is why `detail.patterns` and
`detail.speech_split` were added to the scraper. Both are general: the 「○」
convention is near-universal in Japanese assembly minutes, and label-by-adjacent
-cell is how every Domino-era application is built.

Dates arrive as `06/23/2025` — Domino's month-first format, now handled in
`dates.py`. Day-first is deliberately *not* accepted, since the two are
indistinguishable for the first twelve days of a month.

## Collected: 2025 (令和7年)

The five 令和7年 sessions were collected on 2026-08-26, scoped with `--start-url`
rather than crawling the whole archive:

```
meetings : 113        # documents, i.e. 発言単位
speeches : 1,395
chars    : 886,315
range    : 2025-02-18 .. 2025-12-15
speakers : 88 distinct
```

| 会期 | documents |
| --- | ---: |
| 令和７年２月定例会 | 23 |
| 令和７年５月臨時会 | 12 |
| 令和７年６月定例会 | 25 |
| 令和７年９月定例会 | 26 |
| 令和７年12月定例会 | 27 |

Every record has a date and a session. One document (教育委員会意見) has no
speeches, correctly — it is a written opinion with no spoken content.

Output: `data/静岡県.jsonl` (2.8 MB) and `data/静岡県.csv` (10,112 speech rows).

### Three things the real data taught us

**1. The pages lie about their encoding.** The `<meta>` tag says `charset=utf-8`;
the HTTP header says `Shift_JIS`; the bytes are actually **cp932**. `sniff_encoding`
prefers the meta tag, and only survives here because utf-8 decoding fails outright
and it falls through to the header.

Then Shift_JIS itself is not enough: 「河原﨑」 and 「髙梨」 use NEC/IBM extension
characters that base Shift_JIS cannot decode, so a single member's name aborted the
decode of a whole sitting and the fallback silently produced garbage — 8 documents
came back with zero speeches. Shift_JIS now normalises to cp932, its Microsoft
superset, which is what browsers do with these pages. That recovered 1,263 → 1,395
speeches and 793,801 → 886,315 characters.

**2. Report documents label their date differently.** 質問文書 use 質問日：;
議会補足文書 (報告事項, 知事提案説明, 委員長報告) use 発言日：. Matching only the
first left 60 of 113 records undated.

**3. The attendance roster looks exactly like a speech.** 議会補足文書 open with
「○出　席　議　員（六十七名）」, which has the same shape as 「○知事（鈴木康友君）」 and
landed in the corpus as a speech by 「六十七名」. Requiring the name to end in 「君」
separates them: across a 40-document sample, 632 markers matched and the only four
without 「君」 were rosters. The 「君」 is then stripped, so speakers join across
records.

## The courtesy question — read before crawling

`https://www2.pref.shizuoka.jp/robots.txt` returns **404**: there is no robots.txt,
and nothing is disallowed. But every page of the application — the views and the
documents alike — carries:

```html
<meta name="robots" content="none">
<meta name="robots" content="noindex,nofollow">
<meta name="robots" content="noarchive">
```

The main CMS at `www.pref.shizuoka.jp` carries no such tag, so this is specific to
the minutes application.

What it does and does not mean:

- These are **indexing** directives, not access rules. `noindex` asks that pages
  stay out of public search indexes; `noarchive` asks that cached copies not be
  served publicly; `nofollow` asks crawlers not to follow the page's links.
  None of them says "do not fetch" — that is what a robots.txt `Disallow` says,
  and there isn't one.
- A research corpus is not a public index and publishes no cached copy, so the
  directives' actual purpose is not obviously engaged.
- But `nofollow` on the view pages does describe the exact pattern this scraper
  uses — walk the list, follow the document links — and `PoliteClient` does not
  read meta robots, so nothing in the toolkit will stop it.
- Three mutually redundant tags (`none` already implies `noindex,nofollow`) reads
  like template accumulation rather than a considered policy, much like 千葉's
  robots.txt gap. That is a guess, though, not a finding.

**Recommendation.** A scoped run is proportionate — 2025 took 119 requests at
2s apart, and is what a diligent reader could do by hand. Send a short note before
collecting the full archive, which is 平成11年 to the present and runs to thousands
of documents. The secretariat is on the page itself:

> 静岡県議会事務局議事課　〒420-8601 静岡市葵区追手町9-6
> 電話 054-221-3482 / ファクス 054-221-3179 / gikai_giji@pref.shizuoka.lg.jp

Draft: `docs/inquiries/shizuoka.md`. It asks whether the meta tags are meant to
cover research collection, and offers a bulk export as the easier alternative for
both sides.

## Running it

The configured `start_urls` uses `&ExpandView`, which opens the entire archive —
fine once the question above is settled, but not what you want for a single year.
To scope a run, pass the per-session view URLs instead. `Expand=N` is the Nth
category in the 開催別 view, newest first, so the indices shift as sessions are
added; read them off `WebView1?OpenView` before using them.

```bash
# 2025 = 令和7年 = the five sessions at Expand=2..6 as of 2026-08-26
B='https://www2.pref.shizuoka.jp/all/ggiji.nsf/WebView1?OpenView&Start=1&Count=30&Expand='
uv run pt scrape shizuoka --csv --since 2025-01-01 --until 2025-12-31 \
  --start-url "${B}2" --start-url "${B}3" --start-url "${B}4" \
  --start-url "${B}5" --start-url "${B}6"

uv run pt stats data/静岡県.jsonl
```

`--since/--until` alone is not enough to scope a crawl here: the index carries no
dates, so every document has to be fetched before its date is known. Narrowing the
start URLs is what actually saves the requests.

## Not done yet

- 委員会会議録 (`comgiji.nsf`) — **opened 2026-09-04, not collected.** It is the
  same Domino application under a different `.nsf`: `WebView1` 開催別, `WebView2`
  委員会別, `WebView3` 議員別, the same `Expand=N` / `ExpandView` controls, the same
  three `robots` meta tags, cp932. One document is again one 発言単位 — 【委員会概要】,
  then 「議案説明及び所管事項等の報告（当局側説明）」, then one per member as
  「鈴木　澄美（自民改革会議）（質疑・質問）」.

  **What stops it is not the shape, it is the size and the open question.** The
  view paginates at 30 rows: `?OpenView` returns 30 collapsed nodes and
  `?OpenView&ExpandView` returns the documents of only that first page (28 of
  them, 22 KB). Collecting the archive means walking `Start=1,31,61,…`, which is
  the "thousands of documents" case this document already says to write about
  first — and that letter is the one waiting on 議事課. Building the config before
  the answer would be verifying it by doing the thing the answer governs.
- The exact size of the expanded view, and whether Domino caps it. Unmeasured,
  because measuring it means fetching it.
