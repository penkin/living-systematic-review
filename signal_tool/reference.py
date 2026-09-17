"""One-off download of World Bank income groups. Run: python -m signal_tool.reference

The demo never touches the network, so this writes dated files into reference/
and the pipeline reads those.
"""

import json
import sys
import urllib.request
from datetime import date
from pathlib import Path

WORLD_BANK_URL = "https://api.worldbank.org/v2/country?format=json&per_page=400"


def fetch_income_levels(url=WORLD_BANK_URL):
    """Return {ISO3: income level id} for every country the API lists."""
    with urllib.request.urlopen(url, timeout=30) as response:
        _meta, countries = json.load(response)
    # Aggregates such as "World" carry the placeholder level NA; they are not countries.
    return {c["id"]: c["incomeLevel"]["id"] for c in countries if c["incomeLevel"]["id"] != "NA"}


def write_reference(reference_dir, url=WORLD_BANK_URL, today=None):
    reference_dir = Path(reference_dir)
    income = fetch_income_levels(url)
    (reference_dir / "worldbank_income.json").write_text(
        json.dumps(income, indent=0, sort_keys=True) + "\n", encoding="utf-8"
    )
    metadata = {
        "worldbank_income": {
            "source": url,
            "downloaded": str(today or date.today()),
            "countries": len(income),
        },
        "iso3166_regions": {
            "source": "https://github.com/lukes/ISO-3166-Countries-with-Regional-Codes"
        },
    }
    (reference_dir / "METADATA.json").write_text(json.dumps(metadata, indent=2) + "\n", encoding="utf-8")
    return metadata


if __name__ == "__main__":
    target = sys.argv[1] if len(sys.argv) > 1 else Path(__file__).resolve().parents[1] / "reference"
    print(json.dumps(write_reference(target), indent=2))
