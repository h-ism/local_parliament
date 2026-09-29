# 岩手・茨城・栃木 — permitted by the method we offered

Answered 2026-09-24, through the collaborator's letters in `docs/inquiries/`.
Nothing collected yet, and nothing fetched.

| | system | host | answer |
| --- | --- | --- | --- |
| 岩手 | gijiroku VOICES | `iwatekengikai.gijiroku.com` | permitted, by the method described |
| 茨城 | **DB-Search** | `www.pref.ibaraki.dbsr.jp` | permitted, by the method described |
| 栃木 | gijiroku VOICES | `pref-tochigi.gijiroku.com` | permitted, **tell us when you run**, and **土日夜間** while it sits |

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

### 栃木, hours later: 「土日夜間での実施推奨」

The same day, the secretariat wrote again, relaying their system vendor:

> 1点、本日システムベンダーから連絡があり、可能であれば、ただいま会期中（9/17-10/13）
> と言うこともあり、土日夜間での実施推奨とのことでした。可能でしたらご検討お願い致します。

**A second condition from the same operator does not replace the first — it is
ANDed with it.** 「業務時間帯を避ける」 gave the hours and this gives the days, so
栃木's window is 土日 20:00–07:00: 滋賀's days with 岩手's hours, and the first
window here that is both. Reading it as "weekends" alone would have re-opened
Saturday *daytime*, which is a promise we made and they did not withdraw.

It is phrased as a recommendation (「可能でしたら」), not an instruction. It is
followed anyway: the only thing it costs is wall-clock time, and the assembly is
sitting — which is exactly when a slow page is somebody's afternoon.

**It does not lapse on 2026-10-13 by itself.** The 会期 is the vendor's stated
reason, so the restriction plausibly ends with it — but "plausibly" is us
answering a question they were asked and we were not. `WEEKEND_NIGHTS` stays
until someone says otherwise, and the notice that has to go out before the first
run is the natural place to ask.

**And it is 栃木's, not the product's.** 岩手 runs the same VOICES install family
and answered the same day in the same words; its vendor said nothing to anybody.
Widening or narrowing 岩手 on 栃木's vendor's advice would be the DB-Search
mistake below, in the other direction.

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
   栃木's `[fetch_window]` is `days = ["sat", "sun"]`, not every day.
4. **Send 栃木 the notice** before the first run, and record it — and ask in it
   whether 土日夜間 still applies after the 会期 ends on 2026-10-13.

## What the three answers make, counted

Every one of the three vendor products now has at least one assembly that has
permitted collection: SSP (17), VOICES (滋賀・石川・岩手・栃木), DB-Search (茨城).
The robots verdict recorded for all of them in August was the vendor's
boilerplate in each case. **24 assemblies were "blocked" a month ago; 18 are.**

## 岩手's minutes are not on the host the letter named (2026-09-28)

150 pages of `iwatekengikai.gijiroku.com` are cached — 93 calendar months, the
assembly news, member lists — and no minutes, because that host has none. Its
「本会議会議録」 link leaves for the prefecture's server:

```
http://www3.pref.iwate.jp/gikai/user/www/index.php
```

(the survey of August had noted it: `…/gikai/user/www/Kensaku/`, robots.txt 404).

**Decided by the researcher, 2026-09-28: survey www3.** The permission was for
岩手県議会's 会議録 by the method described, and this is where the assembly's
own site says they are. Same terms — 2 s, serial, 20:00–07:00, 共同研究者B in the
User-Agent. **robots.txt is obeyed as it stands there**: nobody has answered
about that host's rules file, so there is no exemption to write, and if it now
disallows the path the walk stops and says so. First window: tonight, 20:00.

Worth saying in the next letter to 岩手 anyway: that we are reading
`www3.pref.iwate.jp`, which the first letter did not name.

`recon_sites.py` also now counts requests rather than pages walked, so 茨城's
nightly survey — which fetched nothing on 9/25–27 because its first 150 pages
were cached — goes further from tonight. Kept running at the researcher's
choice (2026-09-28).

## 岩手: configured (2026-09-29), from the cache alone

`sites/iwate.toml`, `scraper = "iwate"` (`scrapers/iwate.py`). Worked out
entirely offline from the 9/28 survey — 88 requests, 0 more today.

- **Coverage**: 234 目次 on `Zenbun/` — 161 本会議, 73 予算・決算特別委員会
  (incl. 決算特別委員会（企業会計）), 平成7年 to 令和8年. Both committee kinds
  are verbatim 会議録, so both are in scope. No 常任委員会 on this server.
- **A sitting is several pages.** `Zenbun/page/<目次>/<first>/<last>` is a range
  of paragraph ids; the 目次 lists 「第２号（10月４日）」 and then each member's
  question as its own range, and the first page stops at
  「〔32番佐々木博君登壇〕」. Those are the *rest* of the sitting, not slices of it
  (和歌山's member links are slices), so one record per page would leave most
  一般質問 undated fragments. The scraper joins every page from one 第N号 to the
  next. The ranges are contiguous inside a sitting, so a page the 目次 does not
  link shows up as a gap — counted in `report()`, not trusted.
- **Marker**: 〇 **U+3007**, two shapes — 本会議 「〇議長（渡辺幸貫君）」,
  committees 「〇佐々木朋和委員長」 (name and office together, up to 36 chars
  seen) — and always a full-width space after. On all 56 cached pages
  (1995–2026): 7,493 speeches, **0** 〇-lines unmatched, **0** swallowed.
- **Date**: the first page's own 「平成19年10月４日（木曜日）」, checked against
  the 目次's month and day; a disagreement is reported. 26 whole sittings parse
  from cache, all dated, all agreeing.
- **Not yet seen**: a multi-page 本会議 sitting end to end (no such sitting is
  fully cached) and any 本会議 目次 before 平成19年. Read `report()` after the
  first night.
- **Size**: ≈1,000 sittings, ≈5,000 pages — about three hours at 2 s, inside one
  20:00–07:00 window. `collect_voices.sh` picks it up from the timer;
  `recon_sites.py` now leaves a site with a config alone, so the two never run
  on one host at once.

## 茨城: the route is known, the listing is not verified (2026-09-29)

From the 9/28 survey (150 requests). No config yet, for a reason that needs one
live request to settle.

- **The transcript is easy.** `?Template=document&Id=N` holds every speech of
  the sitting as `li.voice-block` → `p.voice__text`, numbered `1:` … by the
  vendor, ◯ **U+25EF** markers, ─ rules after — the same shape as 山梨's
  downloads, and the `h1` is the download's header line verbatim
  (「令和８年土木企業立地推進常任委員会　 本文 2026-06-10」). So
  `importers/dbsearch.py` parses it as it stands; only the transport differs,
  as expected on 9/24.
- **`Id` is global; the number before `?` is a session.** `Id=10978` under
  `/669261` and `/100000` is byte-identical text; `Id=0` is "whatever this
  session last showed" and differs per session. Records must point at
  `/100000?Template=document&Id=N`, never at a session URL.
- **Each sitting is 3–4 documents**: 議事日程, 名簿, 本文, 質疑通告一覧表 —
  only 本文 is a transcript.
- **The listing is the problem.** 年別の会議録閲覧 gives 483 GET links (本会議
  per 定例会, committees per year, 1989–2026), but each result list shows 10
  documents, and page 2 is a **POST to the session URL with a CSRF `_token`**
  (Laravel). The search form has `Part[]` = 3 (本文), which would cut the
  listing to a quarter — **but whether the GET links accept `Part=3` is
  unverified**, and verifying it is a request, so it waits for 20:00.
- **429 at 2 s**: 7 of 150 requests on 9/28, all recovered on retry. DB-Search
  429'd this project in August too. Proposed: 茨城 at 5 s, as SSP — slower only.
- The 質問一覧 (`Template=mokuji.*-tuu`) are 発言通告 lists, not transcripts.
