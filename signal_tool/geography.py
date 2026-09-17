"""Countries, regions and income groups from reference/. Nothing is hardcoded here."""

import csv
import json
import re
from pathlib import Path

# "Western Africa" and "Southern Africa" live in the intermediate column, so a region
# match must look at all three.
REGION_COLUMNS = ("region", "sub-region", "intermediate-region")


def load_reference(reference_dir):
    """Return the ISO 3166 rows, a name index, the income map and the download date."""
    reference_dir = Path(reference_dir)
    with (reference_dir / "iso3166_regions.csv").open(encoding="utf-8", newline="") as handle:
        rows = [r for r in csv.DictReader(handle) if r["alpha-3"]]
    income_path = reference_dir / "worldbank_income.json"
    meta_path = reference_dir / "METADATA.json"
    income = json.loads(income_path.read_text(encoding="utf-8")) if income_path.is_file() else {}
    meta = json.loads(meta_path.read_text(encoding="utf-8")) if meta_path.is_file() else {}
    return {
        "countries": {r["alpha-3"]: r for r in rows},
        "names": {r["name"].casefold(): r["alpha-3"] for r in rows},
        "income": income,
        "date": meta.get("worldbank_income", {}).get("downloaded", ""),
    }


def countries_in_text(text, ref):
    """ISO3 codes for every ISO 3166 name that appears whole in the text. Exact match only."""
    haystack = (text or "").casefold()
    found = set()
    for name, iso3 in ref["names"].items():
        if name in haystack and re.search(rf"(?<!\w){re.escape(name)}(?!\w)", haystack):
            found.add(iso3)
    return sorted(found)


def resolve(iso3_codes, ref, rules):
    """Regions, income levels and the LMIC verdict for a set of ISO3 codes."""
    codes = sorted({c for c in iso3_codes if c in ref["countries"]})
    regions = set()
    for code in codes:
        row = ref["countries"][code]
        regions.update(row[col] for col in REGION_COLUMNS if row.get(col))
    income = sorted({ref["income"][c] for c in codes if c in ref["income"]})
    verdicts = {level in rules["lmic_income_levels"] for level in income}
    if not income:
        lmic_setting = "Unclear"
    elif verdicts == {True}:
        lmic_setting = "Yes"
    elif verdicts == {False}:
        lmic_setting = "No"
    else:
        lmic_setting = "Mixed"
    return {
        "countries": codes,
        "country_names": [ref["countries"][c]["name"] for c in codes],
        "regions": sorted(regions),
        "income_levels": income,
        "lmic_setting": lmic_setting,
    }
