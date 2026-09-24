# 岩手・茨城・栃木 — permitted by the method we offered

Answered 2026-09-24, through the collaborator's letters in `docs/inquiries/`.
Nothing collected yet, and nothing fetched.

| | system | host | answer |
| --- | --- | --- | --- |
| 岩手 | gijiroku VOICES | `iwatekengikai.gijiroku.com` | permitted, by the method described |
| 茨城 | **DB-Search** | `www.pref.ibaraki.dbsr.jp` | permitted, by the method described |
| 栃木 | gijiroku VOICES | `pref-tochigi.gijiroku.com` | permitted, **and tell us when you run** |

---

## What they agreed to is what we offered

All three answered the same way: scraping is acceptable **if it is done the way
the letter described**. The letter's five undertakings are therefore not a
courtesy any more — they are the terms:

1. 1件読み取るごとに2秒以上の間隔を空け、複数を同時には読み取りません
2. 一度読み取ったページは手元に保存し、同じページを繰り返し取得しません
3. 通信の際に、研究目的であることと当方の連絡先を明示します
4. **業務時間帯を避ける、実施日時を事前にお知らせするなど、ご指示に従います**
5. 何か支障が生じた場合は、ご連絡をいただき次第ただちに停止します

Four of the five the code already keeps on every site. The fourth is the one
that had to be built, twice.

### 「業務時間帯を避ける」 — a window that crosses midnight

We offered to avoid business hours, so we are held to it. The window is
**20:00–07:00, every day**, which is unambiguously outside them.

That shape did not exist: 滋賀 and 石川 are 20:00–24:00, and a window whose
`start` is later than its `end` read as an empty interval — it would have
refused every request and looked like a bug in the crawler rather than a misread
promise. `FetchWindow` now wraps, and **the small hours belong to the evening
that opened them**: a weekend window open at 20:00 on Sunday is still open at
01:00 on Monday, and Monday's own evening is not.

Weekend daytime would presumably be acceptable too, but nothing says so, and the
only cost of the narrower reading is wall-clock time.

### 栃木: 「実行のタイミングを事前に教えて欲しい」

An obligation the crawler cannot discharge — somebody has to send an email — but
it can be made impossible to forget. A site config may carry:

```toml
[notice]
who = "栃木県議会事務局 議事課"
last_sent = "2026-10-01"
covers_until = "2026-10-07"
what = "10月1日〜7日の20時〜翌7時に実施予定。1リクエスト2秒以上、直列。"
```

`pt scrape` refuses before fetching anything when today falls outside what the
notice covered, and prints what to send. The obligation lives in the config with
a date, next to the robots exemption and the window, for the same reason all
three do: an undertaking kept in somebody's memory is one that will be broken on
a Tuesday afternoon with nothing to show for it.

**No notice has been sent yet**, so 栃木 cannot run at all until one is. The
draft is `docs/inquiries/tochigi-notice.md`; three things it is careful about:

* the dates in the letter and the dates in `[notice]` must be **the same**, or we
  run in a period nobody was told about, or refuse in one they were;
* **the reconnaissance counts as a run** and is named in the letter. Forty pages
  is still their server, and deciding on our own that a survey does not need
  mentioning is the kind of reading that makes a promise worthless;
* the size of the archive is unknown until the survey, so the letter says so and
  promises a second notice rather than inventing a number.

`pt scrape tochigi` refuses until the `[notice]` table exists and covers today.

## The letters were not all sent by the same person

滋賀 and 石川 were 共同研究者A's; **栃木 is 共同研究者B's**. Which
matters for one thing, and it is the thing the operators see: the address in the
User-Agent has to be the one *that* assembly can reply to. `[contact]` is per
site for exactly this reason, and until today it looked like a mechanism with one
user.

栃木's is **共同研究者B** (given 2026-09-24).
**岩手 and 茨城's sender is not confirmed**, so neither is fetched: the recon
table now refuses a site whose contact is unknown, with the same shape as the
window and the notice. Running under the wrong colleague's name is not a smaller
mistake than running unannounced — a wrong address tells an operator who to
complain to and the complaint never arrives.

## 茨城 is DB-Search, and 山梨 said the opposite

This is worth stating plainly, because it is the second time the same evidence
has pointed both ways. 茨城 runs the same product as 山梨 — DB-Search, 大和速記
情報センター, `*.dbsr.jp`, the blanket `Disallow: /` — and:

* **山梨** telephoned on 2026-09-17: the system is built for one-at-a-time
  searching, so do not fetch it automatically; use the download button.
* **茨城** answered on 2026-09-24: scraping is fine, done the way we described.

Same vendor, same robots.txt, opposite instructions. The robots file is the
vendor's; the instruction is the assembly's, and only one of them is an
intention. 15 more DB-Search assemblies are unanswered, and this says their
answers cannot be guessed from each other — **ask each one**.

It also means `importers/dbsearch.py`, written for 山梨's downloads, describes a
format we will now also be able to fetch directly from 茨城. The parser should be
reusable; the transport is the only difference.

## Still to do, in order

1. **Reconnaissance**, in the window, for all three: nothing about any of these
   three sites' markup has been looked at. 岩手 is root-level `*.asp` rather than
   `/voices/`, so it is not the same shape as 石川 even within the same product.
2. Selectors from the reconnaissance cache, offline.
3. `sites/*.toml` once the selectors are checked against the real markup, each
   carrying `[robots]`, `[fetch_window]`, `[contact]` and — for 栃木 — `[notice]`.
4. **Send 栃木 the notice** before the first run, and record it.

## What the three answers make, counted

Every one of the three vendor products now has at least one assembly that has
permitted collection: SSP (17), VOICES (滋賀・石川・岩手・栃木), DB-Search (茨城).
The robots verdict recorded for all of them in August was the vendor's
boilerplate in each case. **24 assemblies were "blocked" a month ago; 18 are.**
