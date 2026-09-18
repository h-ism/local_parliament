# 滋賀県議会 — permitted, on a condition about *when*

System: gijiroku VOICES, <https://www.shigaken-gikai.jp/voices/>
Status as of 2026-09-18: **permitted, restricted to weekend evenings.** Nothing
collected yet, and nothing fetched — including for selector work.

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
| User-Agent に研究用と連絡先 | **see the open question below** |
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
address = "…"
note = "照会は共同研究者が行い、2026-09-18に許可を得た"
```

which replaces `PT_CONTACT` in the User-Agent for that site alone, and prints
itself at the start of the run. **It is empty for now**: the address has not been
supplied, and inventing one would be worse than the default. Note that if one
address covers every enquiry, the honest fix is the project-level `PT_CONTACT`
instead — which is still marked 仮おき in `docs/collection-targets.md`, and is
what the SSP crawl is currently broadcasting.

## Still to do, in order

1. Decide what goes in the User-Agent (above), and set it before fetching.
2. First window: **2026-09-19 (Sat) 20:00 JST**. Inside it, work out the
   selectors with `pt inspect` — VOICES is a CGI search system and nothing about
   its markup has been checked yet.
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
next answer to need a third mechanism, and write it down rather than
remembering it.
