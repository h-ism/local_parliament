# 山梨県議会 — site survey (2026-09-17)

The first assembly to answer. 山梨's verdict was not decided by `robots.txt` or by
markup: the 議会事務局 telephoned and said what they wanted, and what they wanted
was neither "no" nor "yes, crawl it".

## What the secretariat said

**2026-09-17, by telephone, from 山梨県議会事務局** (the call came to us; the
officer's name and section were not recorded at the time — see the open question
below):

* 会議録検索システム **は個別での検索を想定しているため、自動取得は控えてほしい**.
* Use the page's **「ダウンロード」 button** and work from what it saves.

Read that carefully, because it is two statements and only the first is a refusal.
The system is not to be fetched by a program. The transcripts are ours to use —
they named the route themselves. So 山梨 is not blocked; it is **collected by
hand and parsed offline**, which is what `importers/dbsearch.py` exists for.

This also settles, from the operator's own mouth, what the `robots.txt` already
implied. <https://www.pref.yamanashi.dbsr.jp/> is a DB-Search tenant and carries
the vendor's blanket `Disallow: /` with a `$`-anchored `Allow` for the landing
page only — the same file as 青森's, and `docs/aomori.md` works through it.

## What the download button produces

One file per 号, which is one sitting. cp932, CRLF, plain text. The 2026-02-03
臨時会 第１号 is 43KB and 456 lines:

```
令和８年２月臨時会（第１号）　本文 : 2026-02-03
----------------------------------------------------------------
1:
◯議長（渡辺淳也君）ただいまから、令和八年二月山梨県議会臨時会を開会いたします。
　これより、本日の会議を開きます。
　　　　　　　───────────────────────────────
2:
◯議長（渡辺淳也君）次に、日程第二、諸般の報告をいたします。
```

Four things decide how it is parsed. The parser's docstring carries the detail;
this is what a reader of the corpus needs to know.

**The header is complete and the date is ISO.** 会議名, 号, 文書種別 and
`2026-02-03`, in one line. 静岡 lost 60 of 113 records to a date label that moved
between document types; nothing of that kind can happen here, because there is one
label and it is machine-readable. The 文書種別 matters: the button also downloads
the **目次**, which is a real document of the sitting and holds no speeches.

**The 発言番号 are the split.** `1:` … `39:`, contiguous. Every other site in this
project infers its speech boundaries from a marker, which is why a marker that
stops matching hands one member's words to whoever spoke before them, silently.
Here the vendor gives the boundaries, and the marker is asked only *who is
speaking*. **A marker this parser cannot read costs a name and not the words**,
and the importer counts those. That is the failure mode of this project's oldest
bug, disarmed by the format.

**The circle is ◯ U+25EF.** Not 和歌山's ○ (U+25CB), not 静岡's 〇 (U+3007) — a
third one. The same file uses U+3007 seven times as the numeral zero. A marker
rule lifted from either prefecture matches **zero** speeches here.

**Two marker shapes in one sitting**, as in 和歌山: 33 speeches write the office
with the name in the marker's brackets 「◯議長（渡辺淳也君）」, 6 are a bare name
「◯水岸富美男君　…」. One of the bare ones is 「◯飯島　修君」, a name split by an
ideographic space — `normalize_speaker` closes it.

And the one to remember for other tenants: **a 罫線 (─ U+2500) ends the speech.**
After it the clerk appends whatever document belongs to that agenda item —
説明員 lists, 付託表, 委員会日程表, 報告書, a box-drawn 議事予定表. 13 of the 39
blocks carry one. None of it is the preceding speaker talking, and attaching it
would be the swallowed-content failure in a new costume.

## The 目次 is the listing side

DB-Search publishes a 目次 beside every 本文, and it names each member who spoke:

```
　水岸富美男議員質疑　………………………………………………九
　　知　事　答　弁　………………………………………………一〇
```

A hand-downloaded corpus has no index to re-walk, so `CLAUDE.md`'s standing
requirement — count the listing against the corpus, per item, after every run —
had no way to be met. The 目次 meets it, offline and for free:
`scripts/audit_manual.py` reads the 目次 for member names and checks each against
the corpus record for that date. It also reports a 目次 with no 本文, which is how
a file nobody downloaded shows up. On a manual collection **that is the likeliest
loss of all**, and nothing else can see it.

Verified on 2026-09-17: 6 names matched from the 2026-02-03 目次, 0 missing from
the corpus; with a speaker deleted from the corpus on purpose, the check names
them. A check that matches nothing reports the same "0" as a clean run, so it was
confirmed to fire before it was believed.

## Where this stands

One sitting collected — 2026-02-03, 39 speeches, 17,189 characters — which is a
proof that the route works and nothing more. The work now is not scraping:

1. **Ask 地方議会会議録コーパス first.** It covers all 47 assemblies for 2011-04 ..
   2019-03, 山梨 included. That is eight years the researcher would otherwise
   download by hand, one 号 at a time. `docs/inquiries/local-politics.md`, drafted
   and still unsent.
2. **Write to the secretariat.** Two things: put the telephone answer in writing,
   and ask whether a bulk export or a programmatic interface exists. The vendor
   (大和速記情報センター) serves 150-odd assemblies, so a data-export feature may
   well be a product they already have. Asking for a route they provide is not
   what they declined. `docs/inquiries/yamanashi.md`.
3. **Then fill the rest by hand.** Estimate, unverified: 定例会 4/year at 5–6 号
   plus 臨時会 ≈ 25–30 files a year. 青森's DB-Search tenant goes back to 昭和58年度;
   **山梨's registered range has not been checked**, and it decides whether the
   remainder is hundreds of downloads or a thousand.

## Open questions

* **Who called.** Date and substance are recorded; the officer's name and section
  are not. The written follow-up should establish both — a verbal permission with
  no name attached is thin if the corpus is ever published on the strength of it.
* **山梨's registered range**, per 会議 type. Readable from the landing page, which
  is the one URL the `robots.txt` allows.
* **Committee minutes.** No committee document has been downloaded, so the
  importer's committee handling — it sets `committee` when the session name
  contains 委員会 — **is untested against real markup**. `CLAUDE.md` is explicit
  that 委員会 are not 本会議 in a different room, and that all three kensakusystem
  prefectures took zero speeches under the rule that collected 本会議. Sample one
  before trusting it.
* **Whether the button can save a whole 会期 at once.** Only two files have been
  seen, both from one sitting. If a session-level download exists, the manual
  effort drops by a factor of five.
