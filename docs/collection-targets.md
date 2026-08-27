# Where minutes can actually be collected

Written 2026-08-27, after re-opening the four leads left in yesterday's survey.
`docs/prefecture-survey.md` still maps all 47 assemblies; this document says what to
build, in what order, and what each thing costs.

**The headline:** two of the leads turned out to be better than the survey guessed,
and both are blocked by the *same* missing feature. One change to `GenericScraper` —
a second listing level — plus one small parsing addition, opens **four prefectures**
(和歌山・愛媛・三重・兵庫) with no permission question outstanding.

---

## Tier 1 — collectable now, nothing to ask anyone

### 1. 和歌山 — the best target found — **implemented 2026-08-27**

robots.txt 404, pages marked `index, follow`, UTF-8, no vendor system. One index
page lists ~150 sessions covering **平成2年 (1990) – 令和8年 (2026)**; each session
page lists its sittings; each sitting is a single HTML page with the full text.

Cost: 1 + ~150 + (number of sittings) requests for the entire 36-year archive.
Detail in `docs/wakayama.md`. `sites/wakayama.toml` now exists and is verified
against both the modern and the 平成-era generation; no full crawl has been run.

The one trap: members speak as bare `○濱口太史君` while office-holders use
`○知事（岸本周平君）`. 静岡's parenthesis-only split rule would silently discard the
majority of the corpus.

### 2. 愛媛・三重・兵庫 — one config shape, three prefectures

`kensakusystem.jp`, robots.txt 404, pages marked `follow,index`. The survey left two
open questions and both resolved in our favour:

- **The tree navigates by GET.** `See.exe?Code=…&treedepth=…` accepts as a query
  string what the page submits as a POST. No POST support needed.
- **A whole sitting comes back in one request.** The page's own ダウンロード button
  posts to `GetPerson.exe`; it accepts GET, takes a repeated `downloadPos`, and
  returns the sitting as plain text. Two requests per sitting including the speaker
  index.

Coverage: 兵庫 **昭和61年 (1986)**, 三重 平成元年, 愛媛 平成3年. 兵庫 is the deepest
archive in the whole survey. `fileName=R080225A` encodes the date, so unlike 静岡 a
date filter here saves requests instead of arriving too late.

Detail, including the exact URL forms and the cp932 percent-encoding of `treedepth`,
in `docs/kensakusystem.md`.

### What both need — done for 和歌山, still open for 愛媛

`GenericScraper` models a listing as one level: `list.meeting_link` plus
`next_page` pagination. Both targets are **year/index → session → sitting**. The
generic fix is an intermediate listing level — a selector for links that lead to
another list rather than to a transcript — which is a real shape in this domain,
not a per-site hack.

愛媛 needs two smaller things on top: applying `speech_split` to a body that is not
HTML, and a listing step that gathers `downloadPos` values into the next URL. The
second may be cheaper as a small `BaseScraper` subclass than as config.

---

## Tier 2 — SSP, 18 prefectures, still one fact short

Unchanged verdict, but the ground is better prepared.

**Done:** every tenant's numeric id, read from `/tenant/<tenant>/js/<…>.js`, which is
**not** under any `Disallow` rule (`Disallow: /tenant/js/` matches only the shared
directory, not `/tenant/prefosaka/js/`).

| | | | |
| --- | --- | --- | --- |
| 宮城 `prefmiyagi` 354 | 秋田 `prefakita` 408 | 山形 `prefyamagata` 466 | 福島 `fukushima` 69 |
| 埼玉 `prefsaitama` 350 | 神奈川 `prefkanagawa` 369 | 新潟 `prefniigata` 333 | 岐阜 `prefgifu` 352 |
| 大阪 `prefosaka` 315 | 奈良 `prefnara` 332 | 岡山 `prefokayama` 455 | 山口 `prefyamaguchi` 599 |
| 徳島 `tokushimapref` 266 | 高知 `prefkochi` 494 | 長崎 `prefnagasaki` 460 | 熊本 `prefkumamoto` 516 |
| 大分 `prefoita` 499 | 沖縄 `prefokinawa` 632 | | |

**Also established:** the permalink form is
`…/tenant/<t>/MinuteView.html?council_id=<n>&schedule_id=<m>`, and those pages are a
pure client-side shell — `<span id="council-title">` is empty in the served HTML.
So there is no server-rendered route; the API is genuinely required.

**Still blocked on:** the endpoint, which is defined in
`/tenant/js/release/config.js` — the shared path, and squarely under
`Disallow: /tenant/js/`. It has not been fetched. The vendor is NTT Advanced
Technology (the scripts carry an `ntt-at.co.jp` author header); the draft letter is
`docs/inquiries/ssp-vendor.md`.

**A second question, independent of robots.** 大阪's own page states:

> このデータの権利は、大阪府議会に帰属します。転用、その他の用途への利用については、
> 大阪府議会事務局までお問い合わせください。

That is a reuse condition, not an access rule, and it would apply even if the API
were known tomorrow. It belongs in the inquiry letters for these 18.

---

## Tier 3 — waiting on a person, not on code

- **静岡, full archive** — 平成11年 onwards, pending 議事課 on the `meta robots`
  question. 2025 is already collected. `docs/inquiries/shizuoka.md`.
- **千葉** — permitted by the letter of its robots.txt because its install sits at
  `/kaigiroku/` while the vendor boilerplate closes `/voices/cgi/`. Still an
  oversight rather than an invitation; ask first. `docs/inquiries/chiba.md`.
- **24 assemblies** on DB-Search and gijiroku VOICES — `Disallow: /`. Letters drafted
  in `docs/inquiries/`.

---

## Before collecting anything: check what already exists

The 地方議会会議録コーパスプロジェクト (<http://local-politics.jp/>) publishes a
都道府県議会 corpus covering **all 47 assemblies** for **2011–2014** and **2015–2019**
— reported as 423 bodies, ~134M sentences, ~80 GB. Its search systems are public;
the bulk data appears to be by arrangement with the project rather than a download.

If the research window falls inside 2011–2019, most of this crawl is redundant and
the right move is to ask them, not to re-collect. The genuine gap is **2020 onwards**,
which is also where our two Tier-1 targets are cheapest.

**This should be settled before any large crawl is started.**

---

## Recommended order

1. Ask local-politics.jp what they can share for the research window. Costs one
   email and may remove most of the work.
2. ~~Add the intermediate listing level to `GenericScraper`.~~ — done.
3. ~~`sites/wakayama.toml`~~ — done. Decide whether to run the full 36-year crawl.
4. `sites/ehime.toml` + the non-HTML detail path; then 三重 and 兵庫 for free,
   with 兵庫 reaching back to 1986.
5. Send the SSP letters (vendor and assemblies), covering both the API endpoint and
   the reuse condition.
