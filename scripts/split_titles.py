"""Split the speaker titles a scraper had to keep whole, using the corpus itself.

Some sources print 「知事（村井嘉浩君）」 and some print 「赤嶺昇議長」. The first is
exact; the second is a name and an office run together with nothing marking where
one ends, and `scrapers/ssp.py` deliberately refuses to guess — it keeps the title
whole and counts it, because the alternative is a speaker made of an office (大分's
「渡邊直二公安委員長」 cut into 「渡邊直二公安」, which is the failure 兵庫 took 124
speeches of).

A finished corpus knows what a single document cannot:

* **the offices**, pooled from every corpus here — a role only ever comes from a
  title that was already unambiguous, and 「委員」 never appears in 神奈川's 本会議
  while appearing constantly in its committees;
* **the names**, per prefecture, from that prefecture's own bracketed titles.

So a title splits only when an office from the first list ends it *and* what
remains is a name from the second — or the unique start of one, which is how
長崎's 「冨岡委員長」 and 奈良's 「疋田委員」 are read. Anything else keeps its title
and is reported under why.

    uv run python scripts/split_titles.py data/沖縄県.jsonl          # measure
    uv run python scripts/split_titles.py data/*.jsonl --apply       # rewrite
"""

from __future__ import annotations

import json
import shutil
import sys
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from pathlib import Path

MIN_NAME = 2
MIN_OFFICE = 2


def load(path: Path) -> list[dict]:
    return [
        json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()
    ]


def pooled_offices(paths: list[Path]) -> set[str]:
    """Every office any corpus has ever stated separately from a name.

    Pooled across *all* of `data/`, not just the files being rewritten: 「委員」
    never appears beside a name in 神奈川's 本会議 and appears 60,000 times in its
    committees, and 静岡 and 兵庫 have been contributing offices to this project
    for a month. A role in any corpus got there from a title that was already
    unambiguous, so the pool is evidence rather than a list someone typed.
    """
    offices: set[str] = set()
    for path in paths:
        for record in load(path):
            for speech in record["speeches"]:
                role = speech.get("role")
                if role and len(role) >= MIN_OFFICE:
                    offices.add(role)
    return offices


@dataclass
class Outcome:
    """What the pass did, and — more usefully — what it refused to do."""

    split: Counter[tuple[str, str]] = field(default_factory=Counter)
    bare_name: Counter[str] = field(default_factory=Counter)
    office_only: Counter[str] = field(default_factory=Counter)
    unknown: Counter[str] = field(default_factory=Counter)
    ambiguous: Counter[str] = field(default_factory=Counter)
    uncorroborated: Counter[tuple[str, str]] = field(default_factory=Counter)
    """Split on a known office alone, with no name in this corpus to confirm it.

    A committee member who never spoke in 本会議 has no bracketed title anywhere,
    so nothing states their name apart from their office — 沖縄 has 110,000
    speeches like that. The office is still evidence: it is the longest match in
    a vocabulary of 2,478 roles that other titles stated separately, and the
    residual is rejected if it ends in an office itself. Counted apart from the
    corroborated splits because it is the weaker claim of the two.
    """

    @property
    def touched(self) -> int:
        return sum(self.split.values()) + sum(self.uncorroborated.values())


def build(records: list[dict]) -> tuple[set[str], dict[str, set[str]], set[tuple[str, str]]]:
    """This prefecture's names, their prefixes, and which offices each has held."""
    names: set[str] = set()
    held: set[tuple[str, str]] = set()
    for record in records:
        for speech in record["speeches"]:
            if speech.get("role"):
                names.add(speech["speaker"])
                held.add((speech["speaker"], speech["role"]))
    starts: dict[str, set[str]] = defaultdict(set)
    for name in names:
        for cut in range(MIN_NAME, len(name) + 1):
            starts[name[:cut]].add(name)
    return names, starts, held


def decide(
    title: str,
    names: set[str],
    starts: dict[str, set[str]],
    held: set[tuple[str, str]],
    offices: list[str],
    outcome: Outcome,
) -> tuple[str, str | None] | None:
    """(speaker, role) when the corpus justifies a split, else None with a reason."""
    if title in names:
        # The title is a name this prefecture states separately elsewhere. There
        # is no office in it to find — 熊本 prints 「岩中伸司」 and nothing more.
        outcome.bare_name[title] += 1
        return None
    for office in offices:
        if not title.endswith(office):
            continue
        residual = title[: -len(office)].strip()
        if not residual:
            # 埼玉 writes 「知事」 with no name at all. Splitting would invent a
            # speaker; the record keeps the office as printed.
            outcome.office_only[title] += 1
            return None
        if len(residual) < MIN_NAME:
            continue
        if residual in names:
            outcome.split[(residual, office)] += 1
            return residual, office
        candidates = starts.get(residual, set())
        if len(candidates) == 1:
            outcome.split[(residual, office)] += 1
            return residual, office
        if candidates:
            # 「黒岩知事」 — several names start 黒岩, so the surname alone does
            # not say who. The office does: exactly one of them has ever been
            # recorded holding it, and that is a fact of this corpus rather than
            # a guess. Where two have, the title stands.
            holders = {name for name in candidates if (name, office) in held}
            if len(holders) == 1:
                winner = holders.pop()
                outcome.split[(winner, office)] += 1
                return winner, office
            outcome.ambiguous[title] += 1
            return None

    # Nothing in this corpus states the name. Take the longest known office that
    # ends the title, provided what is left does not read as an office too —
    # which is what keeps 「渡邊直二公安委員長」 from becoming 「渡邊直二公安」,
    # because 公安委員長 is itself in the vocabulary and matches first.
    for office in offices:
        if not title.endswith(office):
            continue
        residual = title[: -len(office)].strip()
        if len(residual) < MIN_NAME or any(residual.endswith(o) for o in offices):
            continue
        outcome.uncorroborated[(residual, office)] += 1
        return residual, office

    outcome.unknown[title] += 1
    return None


def run(path: Path, offices: set[str], apply: bool) -> Outcome:
    records = load(path)
    names, starts, held = build(records)
    ordered = sorted(offices, key=len, reverse=True)
    outcome = Outcome()
    before = {s["speaker"] for r in records for s in r["speeches"]}

    for record in records:
        for speech in record["speeches"]:
            if speech.get("role") is not None:
                continue
            decided = decide(speech["speaker"], names, starts, held, ordered, outcome)
            if decided:
                speech["speaker"], speech["role"] = decided

    after = {s["speaker"] for r in records for s in r["speeches"]}
    print(f"\n=== {path.name}")
    total = sum(len(r["speeches"]) for r in records)
    print(f"  speeches                 : {total:,}")
    print(f"  split, name corroborated : {sum(outcome.split.values()):,}")
    print(f"  split, office only       : {sum(outcome.uncorroborated.values()):,}")
    print(f"  kept: a name, no office  : {sum(outcome.bare_name.values()):,}")
    print(f"  kept: an office, no name : {sum(outcome.office_only.values()):,}")
    print(f"  kept: office not in any corpus : {sum(outcome.unknown.values()):,}")
    print(f"  kept: the name is ambiguous    : {sum(outcome.ambiguous.values()):,}")
    print(f"  distinct speakers        : {len(before):,} -> {len(after):,}")
    if outcome.split:
        print("  e.g.", [f"{n}+{o}" for (n, o), _ in outcome.split.most_common(3)])
    if outcome.uncorroborated:
        print(
            "  office-only e.g.",
            [f"{n}+{o}" for (n, o), _ in outcome.uncorroborated.most_common(3)],
        )
    for label, counter in (("unknown office", outcome.unknown), ("ambiguous", outcome.ambiguous)):
        if counter:
            print(f"  {label} e.g.: {[t for t, _ in counter.most_common(3)]}")

    # A *new* speaker ending in an office is the failure this pass exists to
    # avoid — 「渡邊直二公安」. It must be zero. (Titles that were already whole
    # and stayed whole are counted above, not here.)
    invented = sorted({n for n in after - before if any(n.endswith(o) for o in ordered)})
    print(f"  speakers invented ending in an office: {len(invented)} {invented[:3]}")
    print(f"  speakers merged away: {len(before - after):,}")

    if apply:
        tmp = path.with_suffix(".jsonl.new")
        with tmp.open("w", encoding="utf-8") as fh:
            for record in records:
                fh.write(json.dumps(record, ensure_ascii=False) + "\n")
        shutil.move(str(tmp), str(path))
        print(f"  rewritten: {path}")
    return outcome


def main() -> int:
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    apply = "--apply" in sys.argv
    paths = [Path(a) for a in args]
    if not paths:
        print(__doc__)
        return 1

    corpora = sorted(Path("data").glob("*.jsonl"))
    offices = pooled_offices(corpora)
    print(f"office vocabulary: {len(offices):,} roles, pooled from {len(corpora)} corpora in data/")
    print(f"rewriting: {len(paths)} of them")
    if not apply:
        print("(dry run — nothing is written; pass --apply to rewrite)")

    grand = 0
    for path in paths:
        grand += run(path, offices, apply).touched
    print(f"\ntotal speeches given a role: {grand:,}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
