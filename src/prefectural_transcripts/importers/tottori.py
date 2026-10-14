"""Import the 本会議 files 鳥取県議会事務局 sent (received 2026-10-14).

Nothing here makes a request. `scripts/tottori_receive.py` files the delivery
under ``manual/鳥取県`` first; this reads that tree. Two shapes, two parsers,
one rule for speeches:

**``export/`` — 平成19年2月〜, one sitting per file.** The search system's own
export, not the ダウンロード text 山梨 sent: the first line is
「2007年02月19日：平成19年２月定例会（第２号）　本文」, the circle is ◯ U+25EF,
and there is **no 発言番号** — so unlike `dbsearch.py` the boundaries are the
markers, and a marker that cannot be read is counted rather than merged.
Three files of the 2026-10-14 delivery hold only 「発言が指定されていません。」:
an export that failed, not a sitting with nothing said. They are reported and
**not written**, so a re-sent file with the same name is not skipped as seen.

**``H15-H18/`` — 平成15年5月〜平成18年12月, files the secretariat kept.** One
folder per session (「H15.06定例会議事録」), named by hand, in four shapes:

- the usual one: a header, the printed date 「平成１５年６月９日（月曜日）」, the
  attendance lists, then ○ U+25CB markers;
- 平成15年5月臨時会: every line indented with eight ASCII spaces and wrapped
  mid-word (「ござい」/「ます。」) — the wraps are joined back;
- 平成17年6月定例会: body only — no header, no printed date; the date is the
  file name's 「_170621」, and 号 is unknown;
- 平成18年11月定例会: 「第1～4号」 and 「第5～7号」 hold several sittings each,
  split at the printed date, and 第1号 also arrives on its own.

Front matter, 目次 and 付録 are not speech. A file whose name says it is one of
those is skipped by name and counted.

**The rule line.** A short ─ rule (the 16-character separator) ends a section:
what follows it up to the next marker is a 再開 time stamp, 〔参照〕 tables or
〔事務局長朗読〕 — not the speaker before it — and is dropped and counted.
A long rule (33 characters or more) is something else, and is kept: inside a
委員長報告 it frames the 報告書 being read, and inside a member's speech it
stands where words were struck out (平成26年11月定例会 第10号), with the
speech carrying on after it. Cutting there lost real speech in testing.
"""

from __future__ import annotations

import datetime as dt
import logging
import re
import unicodedata
from collections import defaultdict
from dataclasses import dataclass, field
from pathlib import Path

from prefectural_transcripts.models import Meeting, Speech
from prefectural_transcripts.scrapers.generic import _clean_speaker

log = logging.getLogger(__name__)

PREFECTURE = "鳥取県"

_EXPORT_HEADER = re.compile(
    r"^(?P<y>\d{4})年(?P<m>\d\d)月(?P<d>\d\d)日：(?P<session>.+?)（(?P<number>第.+?号)）"
    r"[\s　]*(?P<kind>\S+)\s*$"
)
_EXPORT_EMPTY = "発言が指定されていません。"

# Both circles: ○ U+25CB in the secretariat's files, ◯ U+25EF in the export
# (and 35 times in the H18 files). 「○３６番　（小谷茂君）」 puts a space before
# the bracket once, so one is allowed there.
_MARKER = re.compile(
    "^[○◯](?:"
    r"(?P<role>[^（）　\s]{1,40}?)　?（(?P<name>[^（）]{1,40})）"
    r"|(?P<name2>[^（）　\s、。，「」]{1,20}?(?:君|さん|氏))(?=[　\s]|$)"
    ")"
)
_CIRCLE = re.compile("^[○◯]")
_RULE = re.compile(r"^[\s　]*[─━]{5,}")
_SEPARATOR_MAX = 30

_PRINTED_DATE = re.compile(
    r"^[\s　]*平成[\s　]*(?P<y>[0-9０-９]{1,2})年[\s　]*(?P<m>[0-9０-９]{1,2})月"
    r"[\s　]*(?P<d>[0-9０-９]{1,2})日[\s　]*（.曜日）[\s　]*$"
)
_NUMBER = re.compile(r"第[\s　]*(?P<n>[0-9０-９]{1,2})[\s　]*号")
_FILE_NUMBER = re.compile(r"(?:第|本文)(?P<n>[0-9０-９]{1,2})(?:号|[.（]|$)")
_FILE_DATE_COMPACT = re.compile(r"_(?P<y>\d\d)(?P<m>\d\d)(?P<d>\d\d)$")
_FILE_DATE_DOTS = re.compile(
    r"^(?P<y>[0-9０-９]{1,2})・(?P<m>[0-9０-９]{1,2})・(?P<d>[0-9０-９]{1,2})"
)
_CLOSE = re.compile(r"^[\s　]*午[前後].{1,8}(?:散会|閉会)[\s　]*$")
_FOLDER = re.compile(r"^H(?P<y>\d\d)\.(?P<m>\d\d)(?P<kind>定例会|臨時会)")

#: Files that are part of a session's record but hold no transcript.
NOT_TRANSCRIPT = re.compile(
    r"目次|もくじ|付録|日程|報告事項|議決結果|議会結果|請願|陳情|議員提出|表紙"
)

HEISEI = 1988


def _int(s: str) -> int:
    return int(unicodedata.normalize("NFKC", s))


def _session(name: str) -> str:
    """One spelling: 「平成19年２月定例会」 and 「平成19年2月定例会」 are one session."""
    return re.sub(r"[\s　]", "", unicodedata.normalize("NFKC", name))


def speaker_of(line: str) -> tuple[str, str | None, str]:
    """(speaker, role, rest of the line); an empty speaker if the marker is unreadable."""
    m = _MARKER.match(line)
    if not m:
        return "", None, line[1:]
    speaker = _clean_speaker(m["name"] or m["name2"] or "")
    role = unicodedata.normalize("NFKC", m["role"]).strip() if m["role"] else None
    return speaker, role or None, line[m.end() :]


@dataclass
class Split:
    speeches: list[Speech] = field(default_factory=list)
    unattributed: list[str] = field(default_factory=list)
    cut_sections: int = 0
    cut_chars: int = 0
    #: A marker followed by no words: 「◯議長（野田修君）」 alone, 平成26年12月9日.
    silent: int = 0
    #: Speech that went on after an inserted table, joined to the speech before it.
    resumed: int = 0


_STAMP = re.compile(r"^午[前後][0-9０-９]{1,2}時[0-9０-９]{1,2}分(?:\S{2})?$")
# What follows a separator and is not speech: a 再開 stamp, then a 〔参照〕 or
# 〔事務局長朗読〕 section, or a roll of names under 「白票を投じた議員の氏名」.
_NOT_SPEECH = re.compile(r"^[〔［]|氏名$")


def split_speeches(lines: list[str]) -> Split:
    """Speeches from a sitting's lines: a circle at line start begins one.

    After a separator rule, text up to the next marker belongs to no one in
    particular. Stamps, 〔参照〕 tables and name rolls are dropped and counted;
    anything else is speech, in one of two places:

    - **after an inserted table, it is the speaker before the table going on.**
      「…議席表のとおり指定いたします。」 ─ 〔参照〕 the table ─ 「次に、会議録署名
      議員の指名をいたします。」 — the export prints no marker for the chair's
      next sentence. Ten sittings do this; an earlier rule dropped all ten.
    - **otherwise it belongs to no one the record names**, and is kept with an
      empty speaker and counted: 令和6年・7年3月11日 print the 黙祷 announcement
      there, during a 休憩, and attributing it to the chair would be a guess.
    """
    out = Split()
    current: tuple[str, str | None, list[str]] | None = None
    section: list[str] | None = None
    after_insert = False

    def emit(speaker: str, role: str | None, body: list[str]) -> bool:
        text = "\n".join(s for s in (b.strip(" \u3000\t\x1a") for b in body) if s).strip()
        if text:
            out.speeches.append(
                Speech(order=len(out.speeches), speaker=speaker, role=role, text=text)
            )
        return bool(text)

    def close() -> None:
        nonlocal current, section, after_insert
        if current is not None:
            if not emit(*current):
                out.silent += 1
            after_insert = False
        current = None
        if section is None:
            return
        kept = [x.strip(" \u3000\x1a") for x in section]
        kept = [x for x in kept if x and not _STAMP.match(x)]
        if not kept:
            after_insert = False
        elif _NOT_SPEECH.search(kept[0]):
            out.cut_chars += sum(len(x) for x in kept)
            after_insert = True
        elif after_insert and out.speeches:
            last = out.speeches[-1]
            out.speeches[-1] = last.model_copy(update={"text": last.text + "\n" + "\n".join(kept)})
            out.resumed += 1
            after_insert = False
        else:
            emit("", None, kept)
            out.unattributed.append(f"(after a rule) {kept[0][:30]}")
        section = None

    started = False
    for raw in lines:
        line = raw.rstrip()
        if _CIRCLE.match(line):
            close()
            started = True
            speaker, role, rest = speaker_of(line)
            if not speaker:
                out.unattributed.append(line[:40])
            current = (speaker, role, [rest])
            continue
        if not started:
            continue  # front matter before the first speech
        if _RULE.match(line) and len(line.strip(" \u3000")) < _SEPARATOR_MAX:
            close()
            out.cut_sections += 1
            section = []
            continue
        if section is not None:
            section.append(line)
        elif current is not None:
            current[2].append(line)
    close()
    return out


@dataclass(frozen=True)
class Sitting:
    """One sitting located in one file, before its speeches are split."""

    source_file: str
    session: str
    date: dt.date | None
    number: int | None
    lines: list[str]

    @property
    def title(self) -> str:
        return f"{self.session}（第{self.number}号）" if self.number else self.session


def _decode(path: Path) -> list[str]:
    return path.read_bytes().decode("cp932").replace("\r\n", "\n").split("\n")


def read_export(path: Path, source_file: str) -> Sitting | str:
    """A sitting, or a reason the file is not one."""
    lines = _decode(path)
    m = _EXPORT_HEADER.match(lines[0].lstrip("﻿"))
    if not m:
        return f"not an export header: {lines[0][:40]!r}"
    if m["kind"] != "本文":
        return f"kind {m['kind']}"
    if [line.strip() for line in lines[1:] if line.strip()] == [_EXPORT_EMPTY]:
        return "empty export (発言が指定されていません。)"
    return Sitting(
        source_file=source_file,
        session=_session(m["session"]),
        date=dt.date(int(m["y"]), int(m["m"]), int(m["d"])),
        number=_int(m["number"][1:-1]),
        lines=lines[1:],
    )


def _wrapped(lines: list[str]) -> bool:
    body = [line for line in lines if line.strip()]
    return bool(body) and sum(line.startswith(" " * 8) for line in body) > len(body) / 2


def _unwrap(lines: list[str]) -> list[str]:
    """Join 平成15年5月臨時会's mid-word wraps; strip its eight-space indent."""
    out: list[str] = []
    for raw in lines:
        line = raw[8:] if raw.startswith(" " * 8) else raw
        continues = (
            out
            and line
            and line[0] not in "　○◯〔─ "
            and out[-1].strip()
            and not out[-1].rstrip().endswith(("。", "」", "）", "〕"))
            and not _RULE.match(out[-1])
        )
        if continues:
            out[-1] = out[-1].rstrip() + line
        else:
            out.append(line)
    return out


def _width(line: str) -> int:
    return sum(2 if unicodedata.east_asian_width(c) in "WFA" else 1 for c in line)


def _wrap_width(lines: list[str]) -> int | None:
    """The column a file was hard-wrapped at, if it was.

    「第1～4号」 and 「第5～7号」 of 平成18年11月定例会 break every line at 150
    columns (75 full-width characters) — 2,967 lines of exactly that width in the
    first. No other file has more than a handful of lines that long.
    """
    widths = [_width(line) for line in lines if line.strip()]
    long = [w for w in widths if w >= 100]
    if len(long) < 50:
        return None
    return max(set(long), key=long.count)


def _rejoin(lines: list[str], width: int) -> list[str]:
    """Join a line that fills the wrap width to the line after it.

    Two columns of slack: a line ending in a half-width character, or one whose
    next character was full-width and would not fit, stops short of the edge.
    """
    out: list[str] = []
    joining = False
    for line in lines:
        if joining and line and line[0] not in "　○◯〔─" and not _RULE.match(line):
            out[-1] = out[-1] + line
        else:
            out.append(line)
        joining = _width(out[-1]) >= width - 2 and _width(line) >= width - 2
    return out


def _file_date(stem: str) -> dt.date | None:
    m = _FILE_DATE_COMPACT.search(stem) or _FILE_DATE_DOTS.match(stem)
    if not m:
        return None
    return dt.date(HEISEI + _int(m["y"]), _int(m["m"]), _int(m["d"]))


def read_handmade(path: Path, source_file: str, folder: str) -> list[Sitting] | str:
    """The sittings in one of the secretariat's own files (usually one)."""
    fm = _FOLDER.match(folder)
    if not fm:
        return f"session folder not understood: {folder!r}"
    session = f"平成{int(fm['y'])}年{int(fm['m'])}月{fm['kind']}"
    lines = _decode(path)
    if _wrapped(lines):
        lines = _unwrap(lines)
    elif (width := _wrap_width(lines)) is not None:
        lines = _rejoin(lines, width)
    lines = [line.lstrip(" ") for line in lines]

    starts = [i for i, line in enumerate(lines) if _PRINTED_DATE.match(line)]
    file_number = _FILE_NUMBER.search(path.stem)
    if not starts:
        date = _file_date(path.stem)
        if date is None:
            return "no printed date and none in the file name"
        n = _int(file_number["n"]) if file_number else None
        return [Sitting(source_file, session, date, n, lines)]

    sittings = []
    for k, start in enumerate(starts):
        end = starts[k + 1] if k + 1 < len(starts) else len(lines)
        d = _PRINTED_DATE.match(lines[start])
        assert d is not None
        date = dt.date(HEISEI + _int(d["y"]), _int(d["m"]), _int(d["d"]))
        # 号 is printed in the header just above the date, sometimes split
        # over three lines (「平成１６年」「９月定例」「鳥取県議会会議録」「第　１　号」).
        head = "".join(lines[max(0, start - 6) : start + 3])
        printed = _NUMBER.search(head)
        number = _int(printed["n"]) if printed else None
        if number is None and len(starts) == 1 and file_number:
            number = _int(file_number["n"])
        body = lines[start:end]
        # In a file of several sittings the next one's header precedes its date;
        # the sitting ends at its own 散会 / 閉会.
        closes = [i for i, line in enumerate(body) if _CLOSE.match(line)]
        if len(starts) > 1 and closes:
            body = body[: closes[-1] + 1]
        tag = f"#{date.isoformat()}" if len(starts) > 1 else ""
        sittings.append(Sitting(source_file + tag, session, date, number, body))
    return sittings


@dataclass
class TottoriOutcome:
    meetings: list[Meeting] = field(default_factory=list)
    skipped: dict[str, list[str]] = field(default_factory=lambda: defaultdict(list))
    unattributed: list[str] = field(default_factory=list)
    duplicates: list[str] = field(default_factory=list)
    empty: list[str] = field(default_factory=list)
    numbering: list[str] = field(default_factory=list)
    date_out_of_session: list[str] = field(default_factory=list)
    cut_sections: int = 0
    cut_chars: int = 0
    silent: int = 0
    resumed: int = 0

    @property
    def speeches(self) -> int:
        return sum(len(m.speeches) for m in self.meetings)

    def summary(self) -> list[str]:
        lines = [f"imported : {len(self.meetings)} sittings, {self.speeches} speeches"]
        for reason, files in sorted(self.skipped.items()):
            lines.append(f"skipped  : {len(files)} x {reason}")
            if not reason.startswith("not a transcript"):
                lines.extend(f"           {f}" for f in files[:10])
        lines.append(
            f"cut      : {self.cut_sections} sections after a separator rule "
            f"({self.cut_chars} characters of 〔参照〕, 朗読 and name rolls)"
        )
        if self.resumed:
            lines.append(f"resumed  : {self.resumed} speech(es) continued after an inserted table")
        if self.silent:
            lines.append(f"silent   : {self.silent} marker(s) with no words after them")
        for label, items in (
            ("duplicate", self.duplicates),
            ("no speech", self.empty),
            ("numbering", self.numbering),
            ("date/session", self.date_out_of_session),
            ("no speaker", self.unattributed),
        ):
            if items:
                lines.append(f"WARNING  : {len(items)} {label}")
                lines.extend(f"           {i}" for i in items[:10])
        return lines


def _meeting(s: Sitting, split: Split, retrieved_at: dt.datetime) -> Meeting:
    return Meeting(
        prefecture=PREFECTURE,
        source_file=s.source_file,
        date=s.date,
        session=s.session,
        committee=None,
        title=s.title,
        speeches=split.speeches,
        retrieved_at=retrieved_at,
    )


def import_tree(root: Path, *, skip: set[str] | None = None) -> TottoriOutcome:
    """Everything under ``manual/鳥取県``: ``export/`` and ``H15-H18/``."""
    skip = skip or set()
    out = TottoriOutcome()
    sittings: list[Sitting] = []
    for path in sorted((root / "export").glob("*.txt")):
        rel = path.relative_to(root).as_posix()
        got = read_export(path, rel)
        if isinstance(got, str):
            out.skipped[got].append(rel)
        else:
            sittings.append(got)
    for path in sorted(p for p in (root / "H15-H18").rglob("*") if p.is_file()):
        rel = path.relative_to(root).as_posix()
        if NOT_TRANSCRIPT.search(path.name):
            out.skipped["not a transcript (目次・付録 by name)"].append(rel)
            continue
        folder = next((p for p in path.relative_to(root).parts if _FOLDER.match(p)), "")
        found = read_handmade(path, rel, folder)
        if isinstance(found, str):
            out.skipped[found].append(rel)
        else:
            sittings.extend(found)

    # One sitting per date. Only H18.11's 第1号 arrives twice (on its own and
    # inside 「第1～4号」); the file of its own is kept, and whether the two
    # texts agree is reported either way.
    by_date: dict[dt.date | None, list[Sitting]] = defaultdict(list)
    for s in sittings:
        by_date[s.date].append(s)
    retrieved_at = dt.datetime.now(dt.UTC)
    numbers: dict[str, list[int | None]] = defaultdict(list)
    for date in sorted(by_date, key=lambda d: d or dt.date.min):
        group = sorted(by_date[date], key=lambda s: ("#" in s.source_file, s.source_file))
        splits = [split_speeches(s.lines) for s in group]
        if len(group) > 1:
            same = all(
                [x.text for x in sp.speeches] == [x.text for x in splits[0].speeches]
                for sp in splits[1:]
            )
            out.duplicates.append(
                f"{date}: kept {group[0].source_file}; also in "
                + ", ".join(s.source_file for s in group[1:])
                + (" (same speeches)" if same else " (TEXT DIFFERS)")
            )
        s, split = group[0], splits[0]
        numbers[s.session].append(s.number)
        if s.date and not _in_session(s.session, s.date):
            out.date_out_of_session.append(f"{s.source_file}: {s.date} in {s.session}")
        if f"file:{s.source_file}" in skip:
            continue
        out.cut_sections += split.cut_sections
        out.cut_chars += split.cut_chars
        out.silent += split.silent
        out.resumed += split.resumed
        out.unattributed.extend(f"{s.source_file}: {u}" for u in split.unattributed)
        if not split.speeches:
            out.empty.append(s.source_file)
            continue
        out.meetings.append(_meeting(s, split, retrieved_at))

    for session, ns in numbers.items():
        known = sorted(n for n in ns if n is not None)
        if len(known) != len(ns):
            out.numbering.append(f"{session}: {len(ns) - len(known)} sitting(s) with no 号")
        if known and known != list(range(1, len(known) + 1)):
            missing = sorted(set(range(1, max(known) + 1)) - set(known))
            out.numbering.append(f"{session}: 号 {known} (missing {missing})")
    return out


_SESSION_MONTH = re.compile(r"(?:平成|令和)(?:元|\d{1,2})年(?P<m>\d{1,2})月")


def _in_session(session: str, date: dt.date) -> bool:
    """A sitting falls in its session's month or the two after it."""
    m = _SESSION_MONTH.match(session)
    if not m:
        return True
    months = (date.month - int(m["m"])) % 12
    return months <= 2
