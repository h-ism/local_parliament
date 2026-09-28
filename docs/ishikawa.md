# 石川県議会 — permitted, inside hours, and mind the session

System: gijiroku VOICES, <https://pref-ishikawa.gijiroku.com/voices/>
Status as of 2026-09-18: **automated collection permitted, weekend evenings
only.** Nothing fetched yet; reconnaissance is scheduled for the first window.

---

## The answer

石川県議会事務局企画調査課 replied on 2026-09-18 to the letter in
`docs/inquiries/ishikawa.md`, addressed to 共同研究者A, who sent it. In substance:

> 角さまよりご提示のあった以下【サーバへの負荷について】の事項に留意いただき、かつ、
> その際の注意事項として、4項目目にあります取得の時間帯を**土日の夜間帯（20時以降など）
> に限定いただいた上での自動取得は可能**ですので、よろしくお願いいたします。
>
> ※特に現在は本県議会の**定例会の時期（9月30日まで）**でありますことから、くれぐれも
> 取得時間帯にご留意願います。

Two things, and the second is not the same as the first:

1. **Automated collection is permitted**, on our own five undertakings, with the
   fourth pinned to weekend evenings from 20:00. Word for word the condition
   滋賀 gave the same day — the same product, and now the same terms.
2. **The assembly is sitting until 2026-09-30**, and they went out of their way to
   say so. Nothing in the permission expires on that date, but it is the clearest
   possible statement of *why* the hours matter: during a session the people who
   need that server are the ones using it.

So the plan follows their emphasis rather than only their rule: **reconnaissance
this weekend, the bulk collection after 2026-09-30.** Forty pages on a Saturday
evening is not a load; a full archive walk during their 定例会 is a different
thing, and nothing about this corpus needs it to happen in September.

## What runs, and when

`scripts/recon_sites.py` — the same script 滋賀 uses, which now carries a table
of the VOICES installs that have answered. Scheduled by a `systemd --user` timer:

```
systemctl --user list-timers pt-voices-recon.timer
journalctl --user -u pt-voices-recon.service
tail -f data/logs/voices-recon.log
systemctl --user stop pt-voices-recon.timer     # call it off
```

**Sat 2026-09-19 20:00 JST**, both sites in one process, at most 40 pages each,
depth 2, 2 seconds apart, everything into the cache. `PoliteClient` carries the
window, so a timer that fires at the wrong hour fetches nothing and prints the
next opening — verified on a Friday, where it refused for both sites.

The User-Agent carries **共同研究者A**: the enquiry this
answers was theirs, and that is the address the secretariat can reply to.

## robots.txt

`Disallow: /voices/cgi/` — the vendor's boilerplate, identical across all nine
VOICES installs and not a statement by this assembly. The exemption rests on the
mail above, is scoped to `https://pref-ishikawa.gijiroku.com/voices/`, and quotes
the instruction as its reason. It is in `scripts/recon_sites.py` for now and
moves into `sites/ishikawa.toml` when that file exists.

## Still to do, in order

1. **Sat 2026-09-19 20:00** — reconnaissance (scheduled).
2. The second window starts at `g08v_viewh.asp?Sflg=10` (本会議会議録の閲覧),
   found in the first, so the 40-page cap is spent inside the archive; video
   listings and PDFs are skipped, which is where 23 of the first 40 went.
   Read `data/logs/ishikawa/recon-*.txt` and the cache afterwards, offline, and
   work out the selectors. VOICES markup has never been looked at here; 千葉 is
   the only other install this project has a reason to read, and it is a
   different question (`docs/inquiries/chiba.md`).
3. `sites/ishikawa.toml` once the selectors are checked against the real markup,
   carrying `[robots]`, `[fetch_window]` and `[contact]`.
4. **Collection from 2026-10-01**, in the weekend windows — **reserved
   2026-09-21**: `pt-voices-collect.timer` fires every Sat and Sun at 20:00, and
   `collect_voices.sh` refuses 石川 before October, so the first run that can do
   anything is **Sat 2026-10-03 20:00**. If it has to start sooner, ask them
   first — they told us what they are worried about.

   The reservation is real but conditional, and the condition is ours: **there is
   no `sites/ishikawa.toml` yet.** Until the selectors are written from the
   2026-09-26 reconnaissance, the timer will fire, find no config, write
   `ishikawa: NO CONFIG … Nothing fetched.` to `data/logs/voices/run.log`, and
   stop. A reservation that silently collects nothing would be worse than none.

   An archive does not fit in one four-hour window. It does not need to: the
   window closes at midnight, `PoliteClient` stops the run, and the next evening
   resumes from the corpus — every response already fetched is in the cache and
   costs nothing to pass again.

## What this makes two of

滋賀 and 石川 answered on the same day with the same condition, on the same
product. That is worth noticing before the next VOICES letter comes back: the
hours are not one assembly's quirk but what this vendor's operators consider
reasonable, and `[fetch_window]` was built for one site and immediately needed
for two. Seven more VOICES installs are still unanswered
(北海道・岩手・栃木・群馬・長野・宮崎, plus 千葉's separate question).

## The survey never reached a sitting (found 2026-09-28)

Same as 滋賀 (`docs/shiga.md`): the listings live in
`<iframe src="cgi/voiweb.exe?ACT=100…">`, the survey followed only `<a href>`,
and the cache holds 145 wrapper pages and no transcript. Fixed in
`recon_sites.py`; the next window is **Sat 2026-10-03 20:00**, which is also
the first collection slot. The collector will find no config that night and
say so — the config follows from that survey, and collection moves to the
following weekend at the earliest.
