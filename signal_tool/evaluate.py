"""D7. Equity test, agreement table and regret figure over the signals rows. Pure."""

import csv
import io
from collections import defaultdict

from signal_tool.pipeline import CONFIRMABLE

HANDSORT_COLUMNS = ("record_id", "hand_level")


def _scored(rows):
    return [r for r in rows if r.get("signal_level")]


def _size_bucket(row, large):
    size = row.get("sample_size")
    if not isinstance(size, int):
        return "unknown"
    return f"n >= {large}" if size >= large else f"n < {large}"


def equity(rows, rules):
    """Mean score and share HIGH by setting, language, design and size. Scored rows only."""
    large = rules["switches"]["large_study_n"]
    groupers = {
        "lmic_setting": lambda r: r.get("lmic_setting") or "Unclear",
        "non_english": lambda r: "Yes" if r.get("non_english") else "No",
        "study_design": lambda r: r.get("study_design") or "other",
        "sample_size": lambda r: _size_bucket(r, large),
    }
    out = {}
    for name, key in groupers.items():
        groups = defaultdict(list)
        for row in _scored(rows):
            groups[key(row)].append(row)
        out[name] = [
            {
                "group": group,
                "n": len(members),
                "mean_score": round(sum(r["signal_score"] for r in members) / len(members), 1),
                "share_high": round(sum(r["signal_level"] == "HIGH" for r in members) / len(members), 2),
            }
            for group, members in sorted(groups.items(), key=lambda item: str(item[0]))
        ]
    return out


def parse_handsort(text):
    """{record_id: HAND_LEVEL} from a CSV with the columns record_id and hand_level."""
    reader = csv.DictReader(io.StringIO(text))
    missing = [c for c in HANDSORT_COLUMNS if c not in (reader.fieldnames or [])]
    if missing:
        raise ValueError(f"Missing required column(s): {', '.join(missing)}.")
    return {r["record_id"].strip(): r["hand_level"].strip().upper() for r in reader if r["record_id"].strip()}


def agreement(rows, handsort, rules):
    """Crosstab of tool level by hand level, plus the per-record list with the confirm fields."""
    levels = list(reversed(rules["levels"]))
    table = {tool: {hand: 0 for hand in levels} for tool in levels + [""]}
    records = []
    for row in rows:
        hand = handsort.get(row["record_id"])
        if hand is None:
            continue
        tool = row.get("signal_level") or ""
        table.setdefault(tool, {})
        table[tool][hand] = table[tool].get(hand, 0) + 1
        records.append(
            {
                "record_id": row["record_id"],
                "tool_level": tool,
                "hand_level": hand,
                "agree": tool == hand,
                **{f: row.get(f) for f in CONFIRMABLE},
            }
        )
    return {"levels": levels, "table": table, "records": records}


def regret(rows, handsort, top_n):
    """Hand-sorted HIGH records outside the tool's top N by score. The headline figure."""
    ranked = sorted(_scored(rows), key=lambda r: (-r["signal_score"], r["record_id"]))
    rank = {r["record_id"]: i + 1 for i, r in enumerate(ranked)}
    return [
        {"record_id": r["record_id"], "rank": rank.get(r["record_id"]), "signal_level": r.get("signal_level") or "",
         "signal_score": r.get("signal_score"), "signal_reason": r.get("signal_reason") or ""}
        for r in rows
        if handsort.get(r["record_id"]) == "HIGH" and rank.get(r["record_id"], top_n + 1) > top_n
    ]
