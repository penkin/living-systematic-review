"""D7. Equity test, agreement table, regret figure and the hand sheet checks over the signals rows. Pure."""

import csv
import io
import re
from collections import defaultdict

from signal_tool.pipeline import CONFIRMABLE
from signal_tool.scoring import score_record

DELIMITERS = ",;\t|"
ID_COLUMNS = ("record_id", "record")
LEVEL_COLUMNS = ("hand_level", "signal")
SHAPE_ERROR = "Use a file with record_id and hand_level columns, or the reviewers' sheet with one row per question."


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


def _table(text):
    """Rows of a comma, semicolon, tab or pipe file. The delimiter that splits the first line widest wins."""
    lines = [line for line in text.splitlines() if line.strip()]
    if not lines:
        raise ValueError(SHAPE_ERROR)
    delimiter = max(DELIMITERS, key=lambda d: len(next(csv.reader([lines[0]], delimiter=d))))
    return [row for row in csv.reader(io.StringIO(text), delimiter=delimiter) if any(c.strip() for c in row)]


def parse_handsort(text):
    """{record_id: {"hand_level": LEVEL, column: value}} from a file with one row per record
    (record_id or Record, hand_level or SIGNAL, any other columns), or
    {record_id: {question: answer}} from the reviewers' sheet with the ids across the top."""
    rows = _table(text)
    header = [c.strip() for c in rows[0]]
    names = [c.casefold() for c in header]
    id_col = next((i for i, n in enumerate(names) if n in ID_COLUMNS), None)
    if id_col is not None:
        level_col = next((i for i, n in enumerate(names) if n in LEVEL_COLUMNS), None)
        if level_col is None:
            raise ValueError("Missing required column(s): hand_level.")
        hand = {}
        for r in rows[1:]:
            cells = dict(enumerate(c.strip() for c in r))
            if not cells.get(id_col):
                continue
            answers = {header[i]: v for i, v in cells.items() if v and i not in (id_col, level_col) and i < len(header)}
            hand[cells[id_col]] = {"hand_level": cells.get(level_col, "").upper(), **answers}
        return hand
    ids = header[1:]
    if not any(ids):
        raise ValueError(SHAPE_ERROR)
    hand = {record_id: {} for record_id in ids if record_id}
    for row in rows[1:]:
        label = row[0].strip()
        for record_id, answer in zip(ids, row[1:]):
            if label and record_id and answer.strip():
                hand[record_id][label] = answer.strip()
    return hand


def hand_tags(hand, rules):
    """Per record and tool field: the question, the answer as written, the tool values it
    agrees with, and the rubric's label for the answer when it has one. Also the sheet
    labels the rubric does not map."""
    sheet = {label.casefold(): (label, spec) for label, spec in rules["hand_sheet"].items()}
    tags, unmapped = {}, set()
    for record_id, answers in hand.items():
        tags[record_id] = {}
        for label, answer in answers.items():
            if label == "hand_level":
                continue
            if label.casefold() not in sheet:
                unmapped.add(label)
                continue
            question, spec = sheet[label.casefold()]
            key = answer.strip().upper()
            values = spec.get("values", {}).get(key)
            if values is None and spec.get("outcomes"):
                values = [f"O{int(d)}" for d in re.findall(r"\d+", answer)]
            if values is None and spec.get("numeric") and re.fullmatch(r"-?\d+", key):
                values = [int(key)]
            if values:
                tags[record_id][spec["field"]] = {"question": question, "answer": answer, "values": list(values),
                                                  "label": spec.get("labels", {}).get(key)}
    return tags, sorted(unmapped)


def tag_agreement(rows, tags, rules):
    """Per sheet question the file used: records compared and records where the tool's tag
    agrees. An answer with no mapping is not compared."""
    used = {tag["question"] for answers in tags.values() for tag in answers.values()}
    fields = [(label, spec["field"]) for label, spec in rules["hand_sheet"].items() if label in used]
    records = []
    for row in rows:
        answers = tags.get(row["record_id"])
        if answers is None:
            continue
        cells = []
        for label, field in fields:
            hand = answers.get(field)
            tool = row.get(field)
            # override_triggered joins several names with ";"; one match is agreement.
            parts = tool.split(";") if isinstance(tool, str) else [tool]
            cells.append({"field": field, "tool": tool, "hand": hand,
                          "agree": None if hand is None else any(p in hand["values"] for p in parts)})
        records.append({"record_id": row["record_id"], "cells": cells})
    counts = [
        {"label": label, "field": field,
         "n": sum(1 for r in records if r["cells"][i]["agree"] is not None),
         "agree": sum(1 for r in records if r["cells"][i]["agree"])}
        for i, (label, field) in enumerate(fields)
    ]
    return {"fields": counts, "records": records}


def hand_levels(rows, hand, tags, review, rules):
    """{record_id: LEVEL}. A given hand_level by its first word ("HIGH (override)" is HIGH,
    "ROUTE OUT" is "", set aside); otherwise the reviewers' answers laid over the tool's tags
    and scored with the same rubric. A hand "not finished" is "" (set aside)."""
    levels = {}
    for row in rows:
        record_id = row["record_id"]
        given = hand.get(record_id, {}).get("hand_level")
        answers = tags.get(record_id)
        if given:
            first = given.split()[0]
            levels[record_id] = first if first in rules["levels"] else ""
        elif answers:
            overlay = {f: row.get(f) if row.get(f) in a["values"] else a["values"][0] for f, a in answers.items()}
            if overlay.pop("lane", row.get("lane")) == "separate":
                levels[record_id] = ""
            else:
                levels[record_id] = score_record({**row, **overlay}, review, rules)["signal_level"]
    return levels


def agreement(rows, handsort, rules):
    """Crosstab of tool level by hand level, plus the per-record list with the confirm fields."""
    levels = list(reversed(rules["levels"])) + [""]
    table = {tool: {hand: 0 for hand in levels} for tool in levels}
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
