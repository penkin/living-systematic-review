"""Stage 3. Scoring the criteria.

Pure. No model call, no network. A reviewer who overrides a tag re-runs this, so it
must stay cheap and callable without an HTTP request.
"""


def score(criterion, value, rules):
    """Score one criterion from the value of its source field."""
    rule = rules["criteria"][criterion]
    return rule["scores"].get(value, rule["default"])
