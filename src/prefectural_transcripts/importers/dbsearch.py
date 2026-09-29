"""Import the text files DB-Search's ダウンロード button produces.

山梨県議会事務局 asked on 2026-09-17 that the search system not be fetched
automatically — it is built for one-at-a-time searching — and pointed at the
「ダウンロード」 button instead. So 山梨 is collected by hand and parsed here.
Nothing in this module makes a request; `manual/<prefecture>/*.txt` in, JSONL out.

The format is the vendor's, not the prefecture's — DB-Search (大和速記情報センター)
serves 150-odd assemblies, 青森・島根・福岡 among them — so this parser is written
against the product and takes the prefecture as an argument.

One downloaded file is one 号, which is one sitting::

    令和８年２月臨時会（第１号）　本文 : 2026-02-03
    ----------------------------------------------------------------
    1:
    ◯議長（渡辺淳也君）ただいまから、令和八年二月山梨県議会臨時会を開会いたします。
    これより、本日の会議を開きます。
    ───────────────────────────────────
    2:
    ◯議長（渡辺淳也君）次に、日程第二、諸般の報告をいたします。

Three things about that shape are worth stating, because they decide the design:

**The split is given, not inferred.** `1:` … `39:` are the vendor's 発言番号, and
they are what separates one speech from the next. Every other site in this project
finds its boundaries by matching a marker, which is why a marker that stops
matching silently hands one member's words to whoever spoke before them. Here the
marker is only asked *who is speaking*, never *where the speech begins*. A marker
this parser fails to read therefore costs a speaker name and nothing else — and
`ImportOutcome.unattributed` counts it, so the loss is a number rather than a
surprise.

**The circle is U+25EF.** Not 和歌山's ○ (U+25CB), not 静岡's 〇 (U+3007). The same
file uses U+3007 seven times as the numeral zero. A marker rule lifted from either
of those prefectures matches nothing at all here.

**The rule line ends the speech.** A 発言番号 block holds the speech and then,
after a run of ─ (U+2500), whatever document the clerk appended to that item —
説明員 lists, 付託表, 委員会日程表, a 報告書, a box-drawn 議事予定表. None of it is
the preceding speaker talking, so the block is cut at the first rule line and
`ImportOutcome.trimmed_blocks` counts how often that happened. Verified against
all 39 blocks of 2026-02-03: no block carries speech prose after a rule.
"""

from __future__ import annotations

import datetime as dt
import logging
import re
from collections.abc import Iterator
from dataclasses import dataclass, field
from pathlib import Path

from prefectural_transcripts.models import Meeting, Speech
from prefectural_transcripts.scrapers.generic import _clean_speaker

log = logging.getLogger(__name__)

# The downloads are cp932 — Shift_JIS proper cannot hold the NEC/IBM characters
# ordinary names use (髙, 﨑), and mapping to cp932 is what `sniff_encoding` does
# for the same reason. utf-8 is tried first anyway: the tenants are not uniform,
# and a mojibake corpus is the kind of failure that looks like data.
_ENCODINGS = ("utf-8", "cp932", "euc_jp")

# 令和８年２月臨時会（第１号）　本文 : 2026-02-03
# The date is ISO, which is a mercy — `dates.py` exists because assembly pages
# almost never are — so it is read directly and any other shape is a hard error
# rather than a guess.
_HEADER = re.compile(
    r"^(?P<left>.*?)[\s\u3000]*[:：][\s\u3000]*(?P<date>\d{4}-\d{2}-\d{2})[\s\u3000]*$"
)
_NUMBER = re.compile(r"[（(](?P<number>第[0-9０-９一二三四五六七八九十]+号)[）)][\s\u3000]*$")

_BLOCK_START = re.compile(r"^(?P<n>\d+):$")

# ─ is U+2500; the ASCII rule under the header is a different character and a
# different job, so it is not matched here.
_RULE = re.compile(r"^[\s\u3000]*─{5,}[\s\u3000]*$")

# Both shapes appear in a single 43KB sitting: 33 speeches name an office and put
# the name in the marker's own brackets, 6 are a bare name. 和歌山 does the same,
# and a rule that knows only one of them drops the other in silence.
#
# The role class excludes only （） — the marker's own brackets. 兵庫 taught this
# one from the other side: a class that also excluded half-width ( ) cut an office
# at 「参事」 and built a speaker out of the rest. Whichever bracket the marker
# itself uses is the one to exclude, and here that is the full-width pair.
#
# 茨城 (the same product, fetched rather than downloaded) adds a third: its
# committees write 「◯坂本委員長　」 — no brackets, no honorific, the name or office
# ended by a full-width space. The honorific branch then read on into the speech
# until it found a 「さん」 somewhere — 「森田委員二,三人じゃきかないですよ。パッと
# 数えてもたく」 was a speaker, and 2,483 of 2,869 speeches were unattributed —
# which is 和歌山's greedy-speaker failure again. So no branch crosses
# punctuation; the honorific branch allows exactly one full-width space — 山梨
# aligns 「◯飯島　修君　」 in a column — and the bare form ends at the first one,
# or at the end of the line (「◯小野瀬書記」 alone, the speech on the next).
#
# Two more from 茨城's 本会議: 「◯24番江尻加那議員　」 puts the seat number in front
# with no brackets, so it is read as the role — the digit guard below would
# otherwise throw the name away. And one document writes a marker with no space
# after it at all, 「◯江尻委員今の知事の説明を多くの県民の皆さん」: the honorific
# branch must be followed by a space or the line end, or it reads to the first
# 「さん」 in the speech. Unmatched, it costs a name, which is counted; matched,
# it is a speaker made of words, which is not.
_MARKER = re.compile(
    r"^[◯○〇]"  # ◯ ○ 〇
    r"(?:"
    r"(?P<role>[^（）　]{1,40}?)（(?P<name>[^（）]{1,40})）"
    r"|"
    r"(?P<name2>[^（）　、。，,「」]{1,15}(?:　[^（）　、。，,「」]{1,15})?(?:君|さん|氏))"
    r"(?=[　\s]|$)"
    r"|"
    r"(?:(?P<seat>[0-9０-９]{1,3}番))?(?P<name3>[^（）　、。，,「」]{1,40}?)(?:　|$)"
    r")"
)

# A speaker may not be only digits and may not begin with one. 兵庫 numbers its
# offices — 「○（陰山　地域整備第１局長）」 — so excluding digits outright costs real
# speeches; this is the narrower guard that survives both.
_NOT_A_NAME = re.compile(r"^[0-9０-９]|^[0-9０-９\s\u3000、。・]+$")

#: Document kinds the download button produces. Only 本文 carries a transcript;
#: 目次 is the table of contents for the same sitting. Anything else is reported
#: by name rather than skipped quietly — an unknown kind is a thing to look at.
TRANSCRIPT_KIND = "本文"
INDEX_KIND = "目次"


@dataclass(frozen=True)
class _Header:
    session: str
    number: str | None
    kind: str
    date: dt.date
    title: str


@dataclass(frozen=True)
class DocumentResult:
    """What one file parsed to.

    `meeting` is None for a document that carries no transcript — a 目次 is a real
    download and a real part of the sitting, it simply holds no speeches.
    """

    meeting: Meeting | None
    header: _Header
    unattributed: list[str] = field(default_factory=list)
    trimmed: int = 0
    gaps: list[str] = field(default_factory=list)


@dataclass
class ImportOutcome:
    """What one directory of downloads turned into, and what it cost.

    Every field here exists because the corresponding failure is otherwise
    invisible. `unattributed` and `empty` are the two that matter most: the first
    means a marker shape this parser has not seen, the second means a file whose
    blocks produced no text at all.
    """

    meetings: list[Meeting] = field(default_factory=list)
    skipped: dict[str, int] = field(default_factory=dict)
    unattributed: list[str] = field(default_factory=list)
    trimmed_blocks: int = 0
    empty: list[str] = field(default_factory=list)
    gaps: list[str] = field(default_factory=list)

    @property
    def speeches(self) -> int:
        return sum(len(m.speeches) for m in self.meetings)

    def summary(self) -> list[str]:
        """Lines for the CLI to print. Losses first; a clean run says so."""
        lines = [
            f"imported : {len(self.meetings)} documents, {self.speeches} speeches",
        ]
        for kind, count in sorted(self.skipped.items()):
            lines.append(f"skipped  : {count} x {kind}")
        if self.trimmed_blocks:
            lines.append(f"trimmed  : {self.trimmed_blocks} blocks cut at a 罫線")
        if self.gaps:
            lines.append(f"WARNING  : {len(self.gaps)} files have gaps in 発言番号")
            lines.extend(f"           {g}" for g in self.gaps[:5])
        if self.unattributed:
            lines.append(f"WARNING  : {len(self.unattributed)} speeches have no speaker")
            lines.extend(f"           {u}" for u in self.unattributed[:5])
        if self.empty:
            lines.append(f"WARNING  : {len(self.empty)} files produced no speeches")
            lines.extend(f"           {e}" for e in self.empty[:5])
        return lines


def decode(raw: bytes) -> str:
    """Decode a download, and normalise its CRLF line endings."""
    for encoding in _ENCODINGS:
        try:
            return raw.decode(encoding).replace("\r\n", "\n")
        except UnicodeDecodeError:
            continue
    raise ValueError(f"could not decode as any of {', '.join(_ENCODINGS)}")


def _parse_header(line: str) -> _Header:
    """Read the one header line: 会議名, 号, 文書種別 and the date.

    Parsed from the right — date after the colon, kind as the last whitespace
    -separated token before it — because the session name is the part most likely
    to contain a space on a document type we have not seen yet.
    """
    match = _HEADER.match(line)
    if not match:
        raise ValueError(f"not a DB-Search header line: {line!r}")
    date = dt.date.fromisoformat(match["date"])
    left = match["left"].strip()
    parts = left.rsplit(maxsplit=1) if " " in left or "　" in left else [left]
    if len(parts) != 2:
        raise ValueError(f"no document kind in header: {line!r}")
    session, kind = parts[0].strip(), parts[1].strip()
    number_match = _NUMBER.search(session)
    number = None
    if number_match:
        number = number_match["number"]
        session = session[: number_match.start()].strip()
    return _Header(session=session, number=number, kind=kind, date=date, title=left)


def _blocks(lines: list[str]) -> Iterator[tuple[int, list[str]]]:
    """Yield (発言番号, lines) for each numbered block, in file order."""
    starts = [i for i, line in enumerate(lines) if _BLOCK_START.match(line)]
    for start, end in zip(starts, starts[1:] + [len(lines)], strict=True):
        number = int(_BLOCK_START.match(lines[start])["n"])  # type: ignore[index]
        yield number, lines[start + 1 : end]


def _speaker_of(line: str) -> tuple[str, str | None, str]:
    """Split a block's first line into (speaker, role, remaining text).

    Returns an empty speaker when no marker matches. That is deliberate: because
    the 発言番号 already bounded the speech, an unreadable marker costs a name and
    not the words, and the caller counts it.
    """
    match = _MARKER.match(line)
    if not match:
        return "", None, line
    raw_name = match["name"] or match["name2"] or match["name3"] or ""
    speaker = _clean_speaker(raw_name)
    if not speaker or _NOT_A_NAME.match(speaker):
        return "", None, line
    role = (match["role"] or match["seat"] or "").strip() or None
    return speaker, role, line[match.end() :]


def _from_first_marker(block: list[str]) -> list[str]:
    """Drop header lines that come before the block's first speech marker.

    茨城's block 1 is 「　　午前10時29分開議」 and then 「◯坂本委員長　ただいまから、
    …開会いたします。」 — the chair's first words, inside the same 発言番号. Read
    from the first line only, the whole block went to nobody: 30 opening speeches
    in 30 sittings. The lines above the marker are the clerk's heading, which
    every other site drops the same way (see `split_speeches`). A block with no
    marker anywhere is left alone, and is counted as unattributed as before.
    Only lines before the first 罫線 are looked at, since what follows one is an
    appended document, not speech.
    """
    for i, line in enumerate(block):
        if _RULE.match(line):
            break
        if _MARKER.match(line):
            return block[i:]
    return block


def _body(block: list[str], first_line_rest: str) -> tuple[str, bool]:
    """The speech text of one block, and whether a 罫線 cut it short."""
    trimmed = False
    kept: list[str] = []
    for line in block[1:]:
        if _RULE.match(line):
            trimmed = True
            break
        kept.append(line)
    stripped = [line.strip().strip("　").strip() for line in [first_line_rest, *kept]]
    return "\n".join(line for line in stripped if line).strip(), trimmed


_PLENARY = re.compile(r"(?:定例会|臨時会)$")
_YEAR = re.compile(r"^(?:令和|平成|昭和)[元0-9０-９]{1,2}年")


def _committee(session: str) -> str | None:
    """The committee a session names, or None for 本会議.

    Anything that is not a 定例会 or 臨時会 is a committee — 茨城 lists
    「令和８年大学連携推進会議」 beside its committees, and a rule that looked for
    委員会 would have filed it as a plenary. The year is dropped: 茨城 names each
    committee-year 「令和８年土木企業立地推進常任委員会」, and one committee under
    forty names is the digit-width lesson again, one field over.
    """
    if _PLENARY.search(session):
        return None
    return _YEAR.sub("", session).strip() or None


def parse_document(
    raw: bytes | str,
    *,
    prefecture: str,
    source_file: str,
    retrieved_at: dt.datetime | None = None,
) -> DocumentResult:
    """Parse one downloaded file."""
    text = decode(raw) if isinstance(raw, bytes) else raw.replace("\r\n", "\n")
    lines = text.split("\n")
    if not lines:
        raise ValueError(f"{source_file} is empty")
    header = _parse_header(lines[0])
    if header.kind != TRANSCRIPT_KIND:
        return DocumentResult(meeting=None, header=header)

    speeches: list[Speech] = []
    unattributed: list[str] = []
    trimmed = 0
    numbers: list[int] = []
    for number, block in _blocks(lines):
        numbers.append(number)
        if not block:
            continue
        block = _from_first_marker(block)
        speaker, role, rest = _speaker_of(block[0])
        body, was_trimmed = _body(block, rest)
        trimmed += was_trimmed
        if not body:
            continue
        if not speaker:
            unattributed.append(f"{source_file} #{number}: {block[0][:40]}")
        speeches.append(Speech(order=len(speeches), speaker=speaker, role=role, text=body))

    gaps = []
    if numbers and numbers != list(range(1, len(numbers) + 1)):
        gaps.append(
            f"{source_file}: 発言番号 {numbers[0]}..{numbers[-1]} for {len(numbers)} blocks"
        )

    committee = _committee(header.session)
    meeting = Meeting(
        prefecture=prefecture,
        url=None,
        source_file=source_file,
        date=header.date,
        session=header.session,
        committee=committee,
        title=header.title,
        speeches=speeches,
        retrieved_at=retrieved_at or dt.datetime.now(dt.UTC),
    )
    return DocumentResult(
        meeting=meeting, header=header, unattributed=unattributed, trimmed=trimmed, gaps=gaps
    )


class DbSearchImporter:
    """Turn a directory of hand-downloaded DB-Search files into `Meeting`s."""

    def __init__(self, prefecture: str) -> None:
        self.prefecture = prefecture

    def import_paths(self, paths: list[Path], *, skip: set[str] | None = None) -> ImportOutcome:
        skip = skip or set()
        outcome = ImportOutcome()
        for path in paths:
            if f"file:{path.name}" in skip:
                log.debug("already have %s", path.name)
                continue
            try:
                result = parse_document(
                    path.read_bytes(), prefecture=self.prefecture, source_file=path.name
                )
            except (ValueError, OSError) as exc:
                log.error("could not parse %s: %s", path.name, exc)
                outcome.skipped["unparseable"] = outcome.skipped.get("unparseable", 0) + 1
                continue
            if result.meeting is None:
                kind = result.header.kind
                outcome.skipped[kind] = outcome.skipped.get(kind, 0) + 1
                continue
            if not result.meeting.speeches:
                outcome.empty.append(f"{path.name} ({path.stat().st_size} bytes)")
            outcome.meetings.append(result.meeting)
            outcome.unattributed.extend(result.unattributed)
            outcome.trimmed_blocks += result.trimmed
            outcome.gaps.extend(result.gaps)
        return outcome


def find_downloads(source: Path) -> list[Path]:
    """Every .txt under `source`, sorted; or `source` itself if it is a file."""
    if source.is_file():
        return [source]
    return sorted(p for p in source.rglob("*.txt") if p.is_file())


_PAGE_DATE = re.compile(r"\s*(\d{4}-\d{2}-\d{2})\s*$")


def page_to_download(html: str) -> str:
    """A fetched `?Template=document&Id=N` page, in the download's text shape.

    茨城 permits fetching what 山梨 asked us not to, and the page carries the same
    document the ダウンロード button saves: the `h1` is the header line (without
    the colon before the date), and every speech is an `li.voice-block` whose
    `data-voice_code` is the 発言番号. Rebuilding the text lets `parse_document`
    do the one job it already does, rather than a second parser drifting from it.
    """
    from bs4 import BeautifulSoup

    soup = BeautifulSoup(html, "lxml")
    heads = [h.get_text(" ", strip=True) for h in soup.find_all("h1")]
    header = next((h for h in heads if _PAGE_DATE.search(h)), None)
    if header is None:
        raise ValueError("no document header (an h1 ending in a date) on this page")
    lines = [_PAGE_DATE.sub(r" : \1", header), "-" * 64]
    for block in soup.select("li.voice-block"):
        body = block.select_one("p.voice__text")
        lines.append(f"{block.get('data-voice_code', '')}:")
        lines.append(body.get_text().strip("\n") if body else "")
    return "\n".join(lines)
