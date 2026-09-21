"""SSP (Discuss Net Premium) — the JSON API 18 assemblies publish through.

The fixtures below are trimmed from real 宮城 responses: one 本会議 sitting of
令和8年6月定例会, one 議会運営委員会 sitting, and the oldest material in the
archive (昭和22年5月臨時会), which prints its date without an era.
"""

from __future__ import annotations

import json
from datetime import date
from pathlib import Path

import pytest

from prefectural_transcripts.config import RobotsExemption
from prefectural_transcripts.http import FetchError
from prefectural_transcripts.scrapers.ssp import (
    Council,
    Sitting,
    SspConfig,
    SspScraper,
    parse_committee_record,
    read_roster,
    split_title,
    squash,
)

# --- the title, which is the whole speaker problem on this product ----------


def test_plenary_titles_split_on_the_final_bracket() -> None:
    assert split_title("知事（村井嘉浩君）") == ("村井嘉浩", "知事")
    assert split_title("二十三番（天下みゆき君）") == ("天下みゆき", "二十三番")
    assert split_title("会計管理者兼出納局長（大森秀和君）") == ("大森秀和", "会計管理者兼出納局長")


def test_an_office_carrying_its_own_brackets_does_not_steal_the_name() -> None:
    # 昭和22年: 「番外［知事］（千葉三郎君）」. The office holds ［...］ and the name
    # is in the last （...）; a rule anchored anywhere but the end gets this wrong.
    # NFKC folds ［］ to [], the same fold `normalize_speaker` relies on.
    assert split_title("番外［知事］（千葉三郎君）") == ("千葉三郎", "番外[知事]")


def test_committee_titles_have_no_brackets_at_all() -> None:
    # The documented trap: 委員会 are not 本会議 in a different room. The names
    # come from the sitting's own 名簿, so a title with no brackets still splits.
    roster = read_roster(MIYAGI_ROSTER)
    assert split_title("高橋宗也委員長", roster) == ("高橋宗也", "委員長")
    assert split_title("金田もとる委員", roster) == ("金田もとる", "委員")


def test_a_compound_office_is_not_split_on_a_guess() -> None:
    # 「仲慎一郎税務課長」 is 仲慎一郎 + 税務課長 or 仲慎一郎税務 + 課長, and nothing
    # in the string decides. An official is not on the 委員 roster, so neither
    # reading is taken: the title stays whole, which is countable, and a cut
    # would not be.
    assert split_title("仲慎一郎税務課長", read_roster(MIYAGI_ROSTER)) == (
        "仲慎一郎税務課長",
        None,
    )
    assert split_title("島田悠介市町村課長［選挙管理委員会事務局長］") == (
        "島田悠介市町村課長[選挙管理委員会事務局長]",
        None,
    )


MIYAGI_ROSTER = (
    "委員の出欠\n"
    "　　出席\n"
    "　　　委員長　　　高橋宗也君\n"
    "　　　副委員長　　わたなべ　拓君\n"
    "　　　　〃　　　　金田もとる君\n"
    "会議録署名委員　　石川光次郎君\n"
)

# 長崎: name first, office second, and no honorific anywhere.
NAGASAKI_ROSTER = (
    "２、出席委員の氏名\n"
    "　　　　冨岡孝介　　　　　　委員長\n"
    "　　　　山本由夫　　　　　　副委員長\n"
    "　　　　中山　功　　　　　　委員\n"
    "　　　　宅島寿一　　　　　　〃\n"
)

# 大分: office first, name second, no honorific, and most members on a line of
# their own with neither.
OITA_ROSTER = (
    "出席議員　４１名\n"
    "　　議長　　　　　　　　嶋　幸一\n"
    "　　副議長　　　　　　　森　誠一\n"
    "　　　　　　　　　　　　志村　学\n"
    "　　　　　　　　　　　　御手洗吉生\n"
)


def test_the_roster_reads_three_tenants_three_layouts() -> None:
    miyagi = read_roster(MIYAGI_ROSTER)
    assert {"高橋宗也", "わたなべ拓", "金田もとる", "石川光次郎"} <= miyagi.names
    assert "委員長" in miyagi.offices

    nagasaki = read_roster(NAGASAKI_ROSTER)
    assert {"冨岡孝介", "山本由夫", "中山功", "宅島寿一"} <= nagasaki.names
    assert {"委員長", "副委員長", "委員"} <= set(nagasaki.offices)

    oita = read_roster(OITA_ROSTER)
    assert {"嶋幸一", "森誠一", "志村学", "御手洗吉生"} <= oita.names
    assert "議長" in oita.offices
    # 「出席議員　４１名」 is a heading, not a member.
    assert not any("41" in n or n[-1:] == "名" for n in oita.names)


def test_a_name_from_the_roster_takes_the_rest_as_the_office() -> None:
    assert split_title("わたなべ　拓副委員長", read_roster(MIYAGI_ROSTER)) == (
        "わたなべ拓",
        "副委員長",
    )
    # 嶋 and 渡邊 come back as their 常用漢字 forms, as everywhere else here.
    assert split_title("嶋幸一議長", read_roster(OITA_ROSTER)) == ("島幸一", "議長")


def test_an_office_from_the_roster_needs_a_name_from_it_too() -> None:
    nagasaki = read_roster(NAGASAKI_ROSTER)
    # 長崎 titles its chair by surname where the 名簿 gives the full name, so no
    # name matches — but 委員長 does, and 「冨岡」 starts 「冨岡孝介」.
    assert split_title("冨岡委員長", nagasaki) == ("富岡", "委員長")
    # 分科会長 is not on this roster: the same person, a title this cannot read.
    assert split_title("冨岡分科会長", nagasaki) == ("富岡分科会長", None)


def test_an_office_the_sitting_never_lists_does_not_cut_a_name() -> None:
    # 大分 writes 「渡邊直二公安委員長」. Splitting on a plausible 委員長 gives the
    # speaker 「渡邊直二公安」 — an office glued to half a name, and the exact
    # failure 兵庫 took 124 speeches of. 公安委員長 is not on the roster and
    # 渡邊直二 is not a member, so the title is kept whole.
    assert split_title("渡邊直二公安委員長", read_roster(OITA_ROSTER)) == (
        "渡辺直二公安委員長",
        None,
    )


def test_an_unreadable_title_is_kept_whole_rather_than_cut() -> None:
    # Nothing is lost and it is countable: the alternative — cutting on a guess —
    # produces a speaker made of an office, which nothing warns about.
    speaker, role = split_title("某なにがし")
    assert (speaker, role) == ("某なにがし", None)


def test_honorifics_go_the_same_way_as_everywhere_else() -> None:
    assert split_title("議長（佐々木幸士君）")[0] == "佐々木幸士"
    assert split_title("参考人（山田花子さん）")[0] == "山田花子"
    assert split_title("参考人（山田花子氏）")[0] == "山田花子"


# --- metadata ---------------------------------------------------------------


def _council(name: str, names: tuple[str, ...], cid: int = 1, view_year: int = 2026) -> Council:
    return Council(council_id=cid, name=squash(name), view_year=view_year, type_names=names)


def test_plenary_has_no_committee() -> None:
    council = _council("令和　８年　　６月　定例会（第４００回）", ("全会議", "本会議", "定例会"))
    assert council.is_plenary
    assert council.committee is None
    assert (council.year, council.month) == (2026, 6)


def test_committee_comes_from_the_councils_own_name() -> None:
    # The listing types this node 「特別委員会」 and nothing else; the real name is
    # only in the 会議 name, and 1,063 of 宮城's 会議 are filed that way.
    council = _council("令和　８年　　３月　大震災復興調査特別委員会", ("全会議", "特別委員会"))
    assert council.committee == "大震災復興調査特別委員会"

    # And where the two disagree, the printed name wins: this node is typed
    # 環境生活委員会 but the sitting is of 環境生活農林水産委員会.
    council = _council(
        "平成３０年　　３月　環境生活農林水産委員会（第３６３回）",
        ("全会議", "委員会", "常任委員会", "環境生活委員会"),
    )
    assert council.committee == "環境生活農林水産委員会"


def test_session_is_normalised_so_one_session_is_one_string() -> None:
    # 和歌山's committees wrote one session three ways. NFKC plus one space means
    # 「令和　８年　　６月」 and 「令和8年6月」 do not sort apart here.
    a = _council("令和　８年　　６月　定例会（第４００回）", ("全会議", "本会議", "定例会"))
    b = _council("令和8年6月 定例会（第400回）", ("全会議", "本会議", "定例会"))
    assert a.name == b.name == "令和8年6月定例会(第400回)"


def test_listing_date_rolls_the_year_for_a_session_that_sits_in_january() -> None:
    scraper = SspScraper(_config())
    december = _council("令和　７年　１２月　定例会", ("全会議", "本会議", "定例会"))
    january = Sitting(council=december, schedule_id=9, label="01月15日-05号")
    assert scraper._listing_date(january) == date(2026, 1, 15)

    june = _council("令和　８年　　６月　定例会", ("全会議", "本会議", "定例会"))
    assert scraper._listing_date(
        Sitting(council=june, schedule_id=2, label="06月17日-01号")
    ) == date(2026, 6, 17)


# --- end to end, offline ----------------------------------------------------


def _config() -> SspConfig:
    return SspConfig(
        prefecture="宮城県",
        tenant="prefmiyagi",
        tenant_id=354,
        name="ssp_miyagi",
        robots_exempt=RobotsExemption(
            prefixes=("https://ssp.kaigiroku.net/dnp/search/",),
            reason="test",
            decided_on="2026-09-18",
        ),
    )


COUNCILS = json.dumps(
    {
        "councils": [
            {
                "view_years": [
                    {
                        "view_year": "2026",
                        "council_type": [
                            {
                                "council_type_path": "/0/1/3/6/",
                                "council_type_name1": "全会議",
                                "council_type_name2": "本会議",
                                "council_type_name3": "定例会",
                                "council_type_name4": None,
                                "council_type_name5": None,
                                "councils": [
                                    {
                                        "council_id": 4258,
                                        "name": "令和　８年　　６月　定例会（第４００回）",
                                    }
                                ],
                            },
                            {
                                "council_type_path": "/0/1/4/8/11/",
                                "council_type_name1": "全会議",
                                "council_type_name2": "委員会",
                                "council_type_name3": "常任委員会",
                                "council_type_name4": "総務企画委員会",
                                "council_type_name5": None,
                                "councils": [
                                    {
                                        "council_id": 4240,
                                        "name": "令和　８年　　１月　総務企画委員会",
                                    }
                                ],
                            },
                        ],
                    }
                ]
            }
        ]
    },
    ensure_ascii=False,
)

SCHEDULES_PLENARY = json.dumps(
    {
        "schedules_and_materials": [
            {"schedule_id": 1, "name": "06月17日－目次", "page_no": 0},
            {"schedule_id": 2, "name": "06月17日－01号", "page_no": 1},
        ]
    },
    ensure_ascii=False,
)

SCHEDULES_COMMITTEE = json.dumps(
    {"schedules_and_materials": [{"schedule_id": 1, "name": "01月21日－01号", "page_no": 0}]},
    ensure_ascii=False,
)

MINUTE_PLENARY = json.dumps(
    {
        "tenant_minutes": [
            {
                "minute_id": 1,
                "title": "（名簿）",
                "minute_type": "名簿",
                "minute_type_code": 2,
                "body": "<pre>令和　８年　　６月　定例会（第４００回）\n"
                "令和八年六月十七日（水曜日）\n出席議員（五十六名）\n</pre>",
            },
            {
                "minute_id": 2,
                "title": "開会（午後一時）",
                "minute_type": "△議題",
                "minute_type_code": 3,
                "body": "<pre>△開会（午後一時）</pre>",
            },
            {
                "minute_id": 3,
                "title": "議長（佐々木幸士君）",
                "minute_type": "○議長",
                "minute_type_code": 4,
                "body": "<pre>○議長（佐々木幸士君）　ただいまから本日の会議を開きます。</pre>",
            },
            {
                "minute_id": 4,
                "title": "二十三番（天下みゆき君）",
                "minute_type": "◆質問",
                "minute_type_code": 5,
                "body": "<pre>◆二十三番（天下みゆき君）　天下みゆきです。\n"
                "　大綱一、重油流出事故について伺います。</pre>",
            },
            {
                "minute_id": 5,
                "title": "知事（村井嘉浩君）",
                "minute_type": "◎答弁",
                "minute_type_code": 6,
                "body": "<pre>◎知事（村井嘉浩君）　お答えいたします。</pre>",
            },
        ]
    },
    ensure_ascii=False,
)

MINUTE_COMMITTEE = json.dumps(
    {
        "tenant_minutes": [
            {
                "minute_id": 1,
                "title": "（名簿）",
                "minute_type": "名簿",
                "minute_type_code": 2,
                "body": "<pre>令和　８年　　１月　総務企画委員会\n"
                "会議日時　　令和８年１月21日（水曜日）\n"
                "委員の出欠\n　　出席\n　　　委員長　　　高橋宗也君\n"
                "　　　副委員長　　わたなべ　拓君\n　　　　〃　　　　金田もとる君\n</pre>",
            },
            {
                "minute_id": 2,
                "title": "高橋宗也委員長",
                "minute_type": "○議長",
                "minute_type_code": 4,
                "body": "<pre>○高橋宗也委員長　ただいまから総務企画委員会を開会します。</pre>",
            },
            {
                "minute_id": 3,
                "title": "金田もとる委員",
                "minute_type": "◆質問",
                "minute_type_code": 5,
                "body": "<pre>◆金田もとる委員　県税収入について伺います。</pre>",
            },
        ]
    },
    ensure_ascii=False,
)

RESPONSES = {
    ("index",): COUNCILS,
    ("get_schedule_all", "4258"): SCHEDULES_PLENARY,
    ("get_schedule_all", "4240"): SCHEDULES_COMMITTEE,
    ("get_minute", "4258", "2"): MINUTE_PLENARY,
    ("get_minute", "4240", "1"): MINUTE_COMMITTEE,
}


def test_a_whole_tenant_walk_offline(fake_api_client: type) -> None:
    client = fake_api_client(RESPONSES)
    scraper = SspScraper(_config())

    meetings = list(scraper.scrape(client))

    assert [str(m.url) for m in meetings] == [
        "https://ssp.kaigiroku.net/tenant/prefmiyagi/MinuteView.html?council_id=4258&schedule_id=2",
        "https://ssp.kaigiroku.net/tenant/prefmiyagi/MinuteView.html?council_id=4240&schedule_id=1",
    ]

    plenary, committee = meetings
    assert plenary.date == date(2026, 6, 17)
    assert plenary.committee is None
    assert plenary.session == "令和8年6月定例会(第400回)"
    assert plenary.title == "06月17日-01号"
    # The 名簿 and the △議題 heading are not speeches; the three utterances are.
    assert [(s.speaker, s.role) for s in plenary.speeches] == [
        ("佐々木幸士", "議長"),
        ("天下みゆき", "二十三番"),
        ("村井嘉浩", "知事"),
    ]
    # The body repeats its own marker; the text is the words after it.
    assert plenary.speeches[1].text.startswith("天下みゆきです。")
    assert "◆二十三番" not in plenary.speeches[1].text

    assert committee.date == date(2026, 1, 21)
    assert committee.committee == "総務企画委員会"
    assert [(s.speaker, s.role) for s in committee.speeches] == [
        ("高橋宗也", "委員長"),
        ("金田もとる", "委員"),
    ]


def test_the_index_schedule_is_not_collected_as_a_sitting(fake_api_client: type) -> None:
    client = fake_api_client(RESPONSES)
    scraper = SspScraper(_config())

    list(scraper.scrape(client))

    assert ("get_minute", "4258", "1") not in client.requested
    assert scraper.outcome.skipped_labels == {"目次": 1}


def test_the_oldest_material_falls_back_to_the_listings_date(fake_api_client: type) -> None:
    # 昭和22年 prints 「五月二十八日第一日」 — month and day, no era, nothing
    # `parse_japanese_date` can anchor. The 会議 name carries the year and the
    # schedule label the month and day, so the record is still dated.
    councils = json.dumps(
        {
            "councils": [
                {
                    "view_years": [
                        {
                            "view_year": "1947",
                            "council_type": [
                                {
                                    "council_type_path": "/0/1/3/7/",
                                    "council_type_name1": "全会議",
                                    "council_type_name2": "本会議",
                                    "council_type_name3": "臨時会",
                                    "councils": [
                                        {
                                            "council_id": 2877,
                                            "name": "昭和２２年　　５月　臨時会（第１回）",
                                        }
                                    ],
                                }
                            ],
                        }
                    ]
                }
            ]
        },
        ensure_ascii=False,
    )
    minute = json.dumps(
        {
            "tenant_minutes": [
                {
                    "minute_id": 1,
                    "title": "（名簿）",
                    "minute_type": "名簿",
                    "minute_type_code": 2,
                    "body": "<pre>昭和２２年　　５月　臨時会（第１回）\n\n五月二十八日第一日\n"
                    "午後三時十七分開議\n　　出席議員　　全員\n</pre>",
                },
                {
                    "minute_id": 3,
                    "title": "仮議長（清野源助君）",
                    "minute_type": "○議長",
                    "minute_type_code": 4,
                    "body": "<pre>○仮議長（清野源助君）　開会いたします。</pre>",
                },
            ]
        },
        ensure_ascii=False,
    )
    client = fake_api_client(
        {
            ("index",): councils,
            ("get_schedule_all", "2877"): json.dumps(
                {"schedules_and_materials": [{"schedule_id": 1, "name": "05月28日－01号"}]},
                ensure_ascii=False,
            ),
            ("get_minute", "2877", "1"): minute,
        }
    )
    scraper = SspScraper(_config())

    (meeting,) = list(scraper.scrape(client))

    assert meeting.date == date(1947, 5, 28)
    assert scraper.outcome.dates_composed == 1
    assert scraper.outcome.dates_printed == 0


def test_an_empty_listing_is_an_error_not_an_empty_run(fake_api_client: type) -> None:
    # An index that yields nothing looks exactly like one that was never asked
    # for. A tenant with no 会議 is a wrong tenant_id, not a quiet archive.
    client = fake_api_client({("index",): json.dumps({"councils": []})})
    scraper = SspScraper(_config())

    with pytest.raises(FetchError, match="no 会議"):
        list(scraper.scrape(client))


def test_years_scopes_the_listing(fake_api_client: type) -> None:
    config = _config()
    config.years = [1900]
    client = fake_api_client({("index",): COUNCILS})

    with pytest.raises(FetchError, match="years"):
        list(SspScraper(config).scrape(client))


def test_config_requires_a_robots_table_to_be_complete(tmp_path: Path) -> None:
    path = tmp_path / "ssp_x.toml"
    path.write_text(
        'prefecture = "宮城県"\n[ssp]\ntenant = "prefmiyagi"\ntenant_id = 354\n'
        '[robots]\nexempt = ["https://ssp.kaigiroku.net/dnp/search/"]\n',
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="reason"):
        SspConfig.from_toml(path)


def test_a_year_that_cannot_be_true_is_taken_from_the_listing_instead() -> None:
    # 熊本 names one 会議 「平成５７年　６月　定例会」 and files it under 1982. 平成
    # ended at 31; the sitting is 昭和57年. Read literally it lands in 2045.
    scraper = SspScraper(_config())
    impossible = Council(
        council_id=185,
        name=squash("平成５７年　６月　定例会"),
        view_year=1982,
        type_names=("全会議", "本会議", "定例会"),
    )
    sitting = Sitting(council=impossible, schedule_id=2, label="06月15日-02号")

    assert scraper._listing_date(sitting) == date(1982, 6, 15)
    assert scraper.outcome.impossible_years == 1

    # A one-year disagreement is normal and must not be "corrected": 宮城 files
    # 「平成　１年　１２月　決算特別委員会」 under 1990 and the sitting is 1989.
    real = Council(
        council_id=11,
        name=squash("平成　１年　１２月　決算特別委員会（２）"),
        view_year=1990,
        type_names=("全会議", "委員会", "特別委員会", "決算特別委員会"),
    )
    assert scraper._listing_date(
        Sitting(council=real, schedule_id=1, label="12月11日-01号")
    ) == date(1989, 12, 11)
    assert scraper.outcome.impossible_years == 1


def test_the_materials_branch_is_not_collected(fake_api_client: type) -> None:
    # 山形 files 「議第69号～議第93号」 — a list of bill titles — under a root called
    # 「資料」, beside the proceedings. It ends in 号 and has no date and no speaker.
    councils = json.dumps(
        {
            "councils": [
                {
                    "view_years": [
                        {
                            "view_year": "2026",
                            "council_type": [
                                {
                                    "council_type_path": "/0/9/",
                                    "council_type_name1": "資料",
                                    "council_type_name2": "定例会資料",
                                    "councils": [
                                        {"council_id": 519, "name": "定例会（第４２４号）"}
                                    ],
                                }
                            ],
                        }
                    ]
                }
            ]
        },
        ensure_ascii=False,
    )
    client = fake_api_client({("index",): councils})
    scraper = SspScraper(_config())

    with pytest.raises(FetchError, match="no 会議"):
        list(scraper.scrape(client))
    assert scraper.outcome.skipped_materials == 1


def test_a_bill_number_is_not_a_sitting(fake_api_client: type) -> None:
    schedules = json.dumps(
        {
            "schedules_and_materials": [
                {"schedule_id": 1, "name": "06月17日－目次"},
                {"schedule_id": 2, "name": "06月17日－01号"},
                {"schedule_id": 4, "name": "議第69号～議第93号"},
                {"schedule_id": 9, "name": "発議第12号"},
            ]
        },
        ensure_ascii=False,
    )
    client = fake_api_client(
        {
            ("index",): COUNCILS,
            ("get_schedule_all", "4258"): schedules,
            ("get_schedule_all", "4240"): SCHEDULES_COMMITTEE,
            ("get_minute", "4258", "2"): MINUTE_PLENARY,
            ("get_minute", "4240", "1"): MINUTE_COMMITTEE,
        }
    )
    scraper = SspScraper(_config())

    meetings = list(scraper.scrape(client))

    assert len(meetings) == 2
    assert scraper.outcome.skipped_labels == {"目次": 1, "議第69号~議第93号": 1, "発議第12号": 1}


def test_the_listings_date_wins_over_the_notice_the_document_opens_with(
    fake_api_client: type,
) -> None:
    # 徳島's 名簿 prints the 告示 that convened the session before the sitting's own
    # date, so the first date in the document is a week early. The listing label
    # is the sitting.
    minute = json.dumps(
        {
            "tenant_minutes": [
                {
                    "minute_id": 18,
                    "title": "（名簿）",
                    "minute_type": "名簿",
                    "minute_type_code": 2,
                    "body": "<pre>令和　８年　６月定例会\n\n"
                    "　徳島県告示第三百三号\n"
                    "　令和八年六月徳島県議会定例会を次のとおり招集する。\n"
                    "　　令和八年六月八日\n"
                    "　　一　期日　令和八年六月十五日\n</pre>",
                },
                {
                    "minute_id": 20,
                    "title": "議長（井川龍二君）",
                    "minute_type": "○議長",
                    "minute_type_code": 4,
                    "body": "<pre>○議長（井川龍二君）　ただいまから開会いたします。</pre>",
                },
            ]
        },
        ensure_ascii=False,
    )
    councils = json.dumps(
        {
            "councils": [
                {
                    "view_years": [
                        {
                            "view_year": "2026",
                            "council_type": [
                                {
                                    "council_type_path": "/0/1/3/6/",
                                    "council_type_name1": "全会議",
                                    "council_type_name2": "本会議",
                                    "council_type_name3": "定例会",
                                    "councils": [
                                        {"council_id": 1338, "name": "令和　８年　６月定例会"}
                                    ],
                                }
                            ],
                        }
                    ]
                }
            ]
        },
        ensure_ascii=False,
    )
    client = fake_api_client(
        {
            ("index",): councils,
            ("get_schedule_all", "1338"): json.dumps(
                {"schedules_and_materials": [{"schedule_id": 2, "name": "06月15日－01号"}]},
                ensure_ascii=False,
            ),
            ("get_minute", "1338", "2"): minute,
        }
    )
    scraper = SspScraper(_config())

    (meeting,) = list(scraper.scrape(client))

    assert meeting.date == date(2026, 6, 15)
    assert scraper.outcome.date_disagreements == 1


# --- the transcript some tenants put in one block ---------------------------

KANAGAWA_RECORD = """△《委員会記録-令和５年第１回定-20230310-000005-建設・企業常任委員会》　

委員会名
建設・企業常任委員会

開催日
令和５年３月10日

出席者氏名（委員定数　13人のうち　13人出席）
永田(て)委員長、脇礼子副委員長、

５　同上質疑（両局所管事項も併せて）

永田(て)委員
　自民党の永田てるじです。企業庁関係で幾つか質問をいたします。
　まず、神奈川県営水道長期構想についてでありますけれども、
経営課長
　ただいま策定をしようとしております長期構想でございますが、
永田(て)委員
　策定の趣旨については承知をいたしました。

６　日程第１及び第２を採決
"""


def test_a_whole_transcript_in_one_agenda_block_is_read() -> None:
    # 神奈川 does not split its committee proceedings at all: 2,052 sittings
    # arrive as one 議題 block of up to 128,001 characters, which this file used
    # to throw away as a heading — 110 million characters of it.
    pairs = parse_committee_record(KANAGAWA_RECORD)

    assert [name for name, _ in pairs] == ["永田(て)委員", "経営課長", "永田(て)委員"]
    assert pairs[0][1].startswith("自民党の永田てるじです。")
    assert "まず、神奈川県営水道長期構想" in pairs[0][1]  # the speech runs over lines
    assert pairs[2][1] == "策定の趣旨については承知をいたしました。"


def test_the_front_matter_and_the_order_of_business_are_not_speakers() -> None:
    # 「委員会名」「開催日」「出席者氏名（…）」 are unindented lines in a run of
    # unindented lines, and 「５　同上質疑」 begins with a digit. Neither is
    # followed by an indented line, which is the whole test.
    names = [name for name, _ in parse_committee_record(KANAGAWA_RECORD)]
    assert "委員会名" not in names
    assert "開催日" not in names
    assert not any(n.startswith("５") or n.startswith("6") for n in names)


def test_a_record_of_a_sitting_where_nobody_spoke_yields_nothing() -> None:
    # 神奈川 has hundreds of these, and zero speeches is the right answer: a
    # 「１　開　　会」 and nothing else is a real record of a procedural sitting.
    procedural = "△《委員会記録-…-社会問題対策特別委員会》　\n\n１　開　　会\n\n２　閉　　会\n"
    assert parse_committee_record(procedural) == []
