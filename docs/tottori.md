# 鳥取県議会 — 本会議は提供、委員会はとりネットから

**Answered 2026-10-01** (to 共同研究者A's enquiry). The reply is drafted in
`docs/inquiries/tottori-reply.md`, unsent.

| | where | route | status |
| --- | --- | --- | --- |
| 本会議 平成15年〜 | DB-Search (`pref.tottori.dbsr.jp`) | **files from the secretariat**, can be sent at once | waiting for our reply |
| 本会議 平成7〜14年 | same | files, once the old media (DVD/USB) are found — or via the vendor, which we will not ask for | waiting |
| 委員会 平成18年度〜 | **とりネット** (`www.pref.tottori.lg.jp/88112.htm`), not DB-Search | **fetch it ourselves**, once 広報課情報センター has approved the method we describe | **permitted 2026-10-05**, weekends; verbatim |

Provision expected **by early November** if both are agreed.

- **本会議 is the third category again** — hand-delivered data, parsed offline, as
  山梨 — but given rather than downloaded. The format is unknown until it arrives;
  the importer is written then, against the files, not before.
- **委員会 is a different operator.** とりネット is maintained by the prefecture's
  広報課, not by DB-Search's vendor, and that 広報課 asked to know the tool and
  method **before** any automated access. So the crawler has fetched nothing
  there — not even robots.txt — and will not until their answer is recorded.
  When it comes, it belongs in `sites/tottori_committee.toml` as conditions, the
  way 北海道's did.
- **Verbatim, HTML — checked 2026-10-01** by viewing four pages one at a time at
  the researcher's request (the index, 令和7年度 `323536.htm`, 総務教育常任委員会
  `323537.htm`, and the minute of 令和8年2月25日 `item/1432711.htm`), not by the
  crawler, and nothing followed beyond them. First-person speech in the page
  itself, ~100,000 characters for that day. Three levels: 年度 → 委員会 →
  「令和8年2月25日会議録（確定版）」.
- **Three markers**: ◎ the chair (◎東田委員長), ● the executive (●松本政策統轄総局長),
  ○ a member (○山川委員). In 和歌山 ● marked a 要点筆記; here it is a speaker. A
  rule must take all three — and count what each catches.
- **Scale, estimated**: 平成18年度〜令和8年度 (21 years); 令和7年度 has 8
  committees and 総務教育 alone 12 minutes — so roughly 2,000 minutes, ~2,200
  requests with the indexes, ~3 hours at 5 s. An extrapolation from one year.

## 委員会 permitted (2026-10-05), on two conditions

The secretariat relayed 広報課情報センター's answer to the method we described
(serial, 5 s, cache, User-Agent): 「基本的には問題ない」, provided that

1. **these are excluded even though the index links to them** — ホーム
   `/gikai/`, 議会の動き `/87615.htm`, 議会・議員 `/87659.htm`, 開かれた議会
   `/87660.htm`, 議会その他 `/87662.htm`;
2. **not on weekdays 06:00–20:00, not Wednesday night (Thursday 01:00–04:00), and
   if possible on 土日.**

How the code keeps them (`scripts/recon_sites.py`, then `sites/tottori_committee.toml`):

- **土日のみ、終日** (`WEEKEND_ALL_DAY`). Weekday nights are allowed by the letter
  of it, but 「可能であれば」 is followed, as with 栃木's vendor — and Thursday
  01:00–04:00 then never comes up.
- **The five URLs are excluded verbatim** (`TOTTORI_EXCLUDED`), and the walk only
  follows link text 「…年度委員会会議録…」 → a committee → 「…会議録…」 (`follow`),
  because とりネット is the whole prefectural website and its URL prefix bounds
  nothing.
- **5 s**, which is what we told them. robots.txt obeyed as it stands.
- The survey is capped at 40 requests. First window **Saturday 2026-10-10**; the
  recon timer fires at 20:00. The config is written from that cache, then the
  collector (`collect_voices.sh`, `tottori_committee::5`) takes it.

本会議 files: from 10/14, after the 9月定例会.
