# 滋賀県議会 — permitted, on a condition about *when*

System: gijiroku VOICES, <https://www.shigaken-gikai.jp/voices/>
Status as of 2026-09-21: **permitted, restricted to weekend evenings — but the
system is not where the letter said it was.** Nothing collected.

---

## The answer

滋賀県議会事務局 replied on 2026-09-18 to the letter in
`docs/inquiries/shiga.md`. In substance:

> 取得に際しては、ご提示いただいた【サーバーへの負荷について】の事項にご留意いただき、
> 特に4項目目、**取得の時間帯を土日の夜間帯（20時以降）に限定する**ようお願い申し上げます。

The four items are ours — they are quoted back from our own letter — so the
answer is "yes, on the terms you offered, and pin down the fourth one":

| our undertaking | what it now means here |
| --- | --- |
| 1リクエストにつき2秒以上、並列アクセスなし | unchanged; the project default is 2 s |
| 取得済みは保存し再取得しない | unchanged; every response is cached |
| User-Agent に研究用と連絡先 | the address 滋賀 knows is the collaborator's — see below |
| 業務時間帯を避ける、指示に従う | **土日の20時以降のみ** |
| 支障が生じたら直ちに停止 | unchanged |

**This is a third kind of answer**, after 山梨's (don't crawl the system, use the
download button) and SSP's (no refusal). It is an unambiguous yes with a
condition attached, and the condition is about *when* rather than *how fast*.

## What it changed in the code

A promise about *when* fails the way a promise about *how fast* would: silently,
and only in the logs of the person inconvenienced by it. So the hours are not a
line in a runbook but a `[fetch_window]` table in the site config, checked before
every request:

```toml
[fetch_window]
days = ["sat", "sun"]
start = "20:00"
end = "24:00"
reason = "滋賀県議会事務局の指示 (2026-09-18): 取得の時間帯を土日の夜間帯（20時以降）に限定"
decided_on = "2026-09-18"
```

* `FetchWindow` will not load without a reason and a date, like `RobotsExemption`.
* Outside the hours, `PoliteClient` raises `OutsideFetchWindow` — deliberately
  **not** a `FetchError`, because `scrape()` carries on past a fetch error, and
  carrying on here would break the same promise once per document, thousands of
  times, and finish looking like a normal run. `BaseScraper.scrape` re-raises it.
* `pt scrape` says it in one line before fetching anything, with the next opening
  time: `next window opens 2026-09-19 20:00 JST`.
* **A cached page is still served at any hour.** Reading what we already hold is
  not fetching, and `reparse.py` and `audit.py` must not have to wait for
  Saturday night.
* The window is evaluated in `Asia/Tokyo`, not the machine's clock — a server on
  UTC would otherwise fetch at 05:00 滋賀 time.

## Who the enquiry came from (settled 2026-09-18)

The reply is addressed to **共同研究者A 様**, not to this project's
`PT_CONTACT`. That is because **the enquiry was made by a collaborator** — and, as
the researcher confirmed the same day, *every* letter in `docs/inquiries/` went out
that way. So the permission is ours to use.

What it leaves open is not permission but attribution: the third undertaking in
that letter is 「User-Agent に研究用である旨と当方の連絡先を明記します」, and the
address 滋賀 has on file is the collaborator's. A site config can therefore carry

```toml
[contact]
address = "(共同研究者Aの連絡先)"
note = "照会は共同研究者Aが行い、2026-09-18 に許可を得た"
```

which replaces `PT_CONTACT` in the User-Agent for that site alone and prints
itself at the start of the run. **共同研究者A, given
2026-09-18**, is the address 滋賀 has on file, and it is what
`scripts/recon_sites.py` already sends; it goes into `sites/shiga.toml` the
moment that file exists.

Note that the project-level `PT_CONTACT` (a 京都大学 address) is still marked
仮おき in `docs/collection-targets.md`, and is what the SSP crawl is currently
broadcasting. If one address covers every enquiry, that is the thing to fix.

## The first window: reconnaissance, scheduled

**Sat 2026-09-19 20:00 JST**, by a `systemd --user` timer created 2026-09-18:

```
systemctl --user list-timers pt-voices-recon.timer    # NEXT / LEFT
journalctl --user -u pt-voices-recon.service          # what it did
tail -f data/logs/voices-recon.log                    # the same, as it runs
systemctl --user stop pt-voices-recon.timer           # call it off
```

It runs `scripts/recon_sites.py` — shared with 石川, which answered the same day
on the same terms (`docs/ishikawa.md`) — and what it does is **look, not
collect**:
at most 40 pages under `/voices/`, depth 2, 2 seconds apart, all of it into the
cache. It cannot run at the wrong time — `PoliteClient` carries the window, so a
timer that fires on a Tuesday fetches nothing and says why.

Collecting cannot be scheduled yet, and should not be: there is no
`sites/shiga.toml`, because nobody has seen this site's markup. **Fetch inside
the window; think outside it.** The selectors get worked out afterwards from the
cache, at no cost to their server, and the first real run goes in a later window.

Two caveats about the timer itself: it is transient, so it does not survive a
reboot, and `Linger=no` for this user, so it needs a login session to be alive at
20:00. `loginctl enable-linger` fixes the second if that is a problem.

## The install has moved (2026-09-19)

The first window fetched exactly one page and stopped, which is the walk working
as intended. `https://www.shigaken-gikai.jp/voices/` is 271 bytes:

```html
<meta Http-Equiv="Refresh" Content="3;url=../index.asp">
<title>滋賀県議会公式サイト</title>
3秒後に滋賀県議会ホームページに移動します。
移動しないときは<a href="../index.asp">ここ</a>をクリックしてください。
```

A signpost, not a system. The URL in `docs/inquiries/shiga.md` was verified
2026-08-26 and is stale: the 会議録検索システム has been moved or retired since.
The exemption is scoped to `/voices/`, so the crawl stopped at the edge of what
the operator answered about rather than wandering the site — which is the
behaviour to keep.

**What this does and does not change.** The permission is not in doubt: they
answered a letter about collecting 滋賀県議会's 会議録, and that is still what we
want. What is unknown is the URL, and with it two things that only a URL can
settle — **whether the new location is a different product** (in which case its
own robots.txt and its own shape apply) and whether it is even on this host.
CLAUDE.md's rule covers exactly this: *a robots.txt verdict is not final until
you know the URL that actually carries the data.*

**Finding it, next window (Sat 2026-09-26 20:00).** `scripts/recon_sites.py`
now walks a `discover` list when the start page turns out to be a signpost:
`robots.txt`, `index.asp` and the host root, at most a dozen pages, following
only links whose text or URL says 会議録・議事録・検索・voices・gijiroku, and
writing what it finds to `data/logs/shiga/candidates.txt`. **robots is enforced
normally outside `/voices/`** — the exemption covers the path the secretariat
answered about, not the whole host — so if their file closes the rest of the
site the walk stops and says so.

`robots.txt` itself is named in a one-line exemption of its own: the rules file
is always fetchable (RFC 9309 §2.3), and `urllib.robotparser` would otherwise
apply a blanket `Disallow: /` to the very file that says it.

**Found, 2026-09-21, by the researcher in a browser** — faster than any crawl,
and how SSP's `config.js` was read too:

```
https://www.shigaken-gikai.jp/voices/g07v_search.asp
```

Still under `/voices/`, so the existing exemption covers it and the vendor's
naming matches 石川's (`g07…`, `g08v…`). Saturday now starts there.

Fixing the start exposed a bug worth recording: `walk()` filtered on the *start*
URL, which is the same string as the permitted area only when the start is a
directory. Beginning at a page would have followed nothing at all and looked
like a site with no links. `start` and `prefix` are now separate fields — the
first is where to begin, the second is what the operator answered about.

## Still to do, in order

1. ~~Decide what goes in the User-Agent~~ — 共同研究者A.
2. **Find where the system went** — next window, or a browser (above).
3. `robots.txt` still disallows the CGI directory. The answer above is the
   operator's own instruction and overrides that reading, but the exemption has
   to be written down the same way SSP's is: prefixes, reason, date, in the
   config. Quote the mail in the reason.
4. Only then a config in `sites/`, once the selectors have been checked against
   the real markup — the standing rule.

## What generalises to the other blocked assemblies

The count of assemblies that "forbid crawling" has now been wrong twice in one
month, in both directions and for the same reason: **`robots.txt` is one
statement an operator makes, and not the last one.** 山梨 moved to hand
collection, SSP to collection under a recorded decision, 滋賀 to collection
inside agreed hours. Each letter that comes back can move an assembly between
categories, and the code has had to grow a mechanism for each one. Expect the
next answer to need a mechanism of its own, and write it down rather than
remembering it.

## The survey never reached a sitting (found 2026-09-28)

Two weekend windows, 150 pages each, and **not one listing or transcript is in
the cache.** Every `g08v_viewh.asp` / `g08v_views.asp` page is a wrapper; the
sittings are inside `<iframe src="cgi/voiweb.exe?ACT=100&…">`, and the survey
followed `<a href>` only. The report looked complete — 81 committee pages, 43
本会議 pages — and was 124 frames with nothing in them. On the second weekend
every page came from cache, so the 150 cap (which counted cached pages) was
spent before a single request went out.

`recon_sites.py` now follows frames at the same depth and first in line, puts
`voiweb.exe` links ahead of everything else, counts **requests** against the
cap, skips the schedule pages, and samples evenly across each list of
same-shaped links so 昭和62年 is in the sample as well as 令和8年. The walk starts
at `g08v_viewh.asp`, because from the search form a transcript is at depth 5.

**Next window: Sat 2026-10-03 20:00.** No config until then — the rule is not
to write selectors against markup nobody has seen.

**The committee side is 委員会*要録*.** The site's own label, and the word
usually means a summary. If a sample reads like 和歌山's committees — third
person, 「［主な発言］」 — it is not collected (verbatim only, decided
2026-09-24), and 滋賀 is 本会議 only. Check it on the first sample.
