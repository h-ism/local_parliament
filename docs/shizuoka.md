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

## Verified

The config was checked against the real pages, offline, from bytes already fetched
by hand:

- listing: 26 documents found in 令和7年6月定例会, titles like
  `赤堀　慎吾（自民改革会議）（代表質問）`
- one document parsed: `date=2025-06-23`,
  `session='令和７年６月静岡県議会定例会'`, **39 speeches, 25,875 characters**,
  roles and names split correctly (`議長/竹内良訓`, `六番/赤堀慎吾`, `知事/鈴木康友`)

The 「君」 that the minutes append to every name is stripped, so speakers join
across records.

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

**Recommendation.** Treat a one-off verification fetch as fine — it is what any
reader's browser does — and send a short note before collecting the full archive,
which is 平成11年 to the present and runs to thousands of documents. The
secretariat is on the page itself:

> 静岡県議会事務局議事課　〒420-8601 静岡市葵区追手町9-6
> 電話 054-221-3482 / ファクス 054-221-3179 / gikai_giji@pref.shizuoka.lg.jp

Draft: `docs/inquiries/shizuoka.md`. It asks whether the meta tags are meant to
cover research collection, and offers a bulk export as the easier alternative for
both sides.

## Running it, once that is settled

```bash
uv run pt scrape shizuoka --limit 1 -v     # one document, check the output
uv run pt scrape shizuoka --csv            # full run, JSONL + CSV
uv run pt stats data/静岡県.jsonl
```

`--limit` is worth using generously here: `&ExpandView` returns the entire tree,
so the listing page alone is large and the document count is in the thousands.

## Not done yet

- 委員会会議録 (`comgiji.nsf`) — same host and almost certainly the same shape, but
  not opened yet. Likely a second `start_urls` entry, or a sibling config.
- The exact size of the expanded view, and whether Domino caps it. Unmeasured,
  because measuring it means fetching it.
