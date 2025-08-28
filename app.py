import os
import re
import json
from flask import Flask, request, jsonify
import yaml

# Config
SEVERITY_WEIGHTS = {"low": 1, "med": 3, "high": 5}
DEFAULT_JURISDICTION = "delaware"

app = Flask(__name__)

# Load rules at startup
RULES_PATH = os.path.join(os.path.dirname(__file__), "rules", "rules.yml")
SUGGESTED_FIXES_PATH = os.path.join(os.path.dirname(__file__), "data", "suggested_fixes.json")

with open(RULES_PATH, "r", encoding="utf-8") as f:
    RULES = yaml.safe_load(f)

if os.path.exists(SUGGESTED_FIXES_PATH):
    with open(SUGGESTED_FIXES_PATH, "r", encoding="utf-8") as f:
        SUGGESTED_FIXES = json.load(f)
else:
    SUGGESTED_FIXES = {}

def find_any(text_lc, keywords):
    return any(k.lower() in text_lc for k in keywords)

def regex_found(text, pattern):
    return re.search(pattern, text, flags=re.IGNORECASE | re.MULTILINE) is not None

def evaluate_rules(text: str, jurisdiction: str):
    text_lc = text.lower()
    issues = []
    counts = {"high": 0, "med": 0, "low": 0}
    score = 0

    for rule in RULES:
        rid = rule["id"]
        severity = rule["severity"]
        rationale = rule.get("rationale", "")
        mock_ref = rule.get("mock_reference", "Ref: Placeholder-001")

        triggered = False
        message = ""

        # Keyword presence rule
        if rule.get("type") == "missing_keywords":
            keywords = rule.get("keywords", [])
            if not find_any(text_lc, keywords):
                triggered = True
                message = rule.get("description", f"Missing: {rid}")

        # Regex presence rule
        elif rule.get("type") == "missing_regex":
            pattern = rule.get("pattern")
            if pattern and not regex_found(text, pattern):
                triggered = True
                message = rule.get("description", f"Missing pattern: {rid}")

        # Risky pattern present
        elif rule.get("type") == "risky_regex":
            pattern = rule.get("pattern")
            if pattern and regex_found(text, pattern):
                triggered = True
                message = rule.get("description", f"Risky pattern: {rid}")

        # Jurisdiction/venue mismatch (simple)
        elif rule.get("type") == "venue_mismatch":
            expected = jurisdiction.lower()
            # If the text contains a different common state/country word, flag
            others = rule.get("other_places", [])
            if any(p.lower() in text_lc for p in others) and expected not in text_lc:
                triggered = True
                message = rule.get("description", "Venue/jurisdiction mismatch")

        if triggered:
            counts[severity] += 1
            score += SEVERITY_WEIGHTS[severity]
            issue = {
                "id": rid,
                "severity": severity,
                "message": message,
                "rationale": rationale,
                "mock_reference": mock_ref,
                "suggested_fix": SUGGESTED_FIXES.get(rid, "")
            }
            issues.append(issue)

    return score, counts, issues

@app.route("/review", methods=["POST"])
def review():
    data = request.get_json(silent=True) or {}
    text = data.get("text", "")
    jurisdiction = (data.get("jurisdiction") or DEFAULT_JURISDICTION).lower()

    if not isinstance(text, str) or len(text.strip()) == 0:
        return jsonify({"error": "text is required"}), 400
    if len(text) > 500_000:
        return jsonify({"error": "text too long"}), 400

    score, counts, issues = evaluate_rules(text, jurisdiction)

    resp = {
        "risk_score": score,
        "summary": {"high": counts["high"], "med": counts["med"], "low": counts["low"]},
        "issues": issues
    }
    return jsonify(resp), 200

if __name__ == "__main__":
    # Dev server
    from waitress import serve
    port = int(os.environ.get("PORT", 5000))
    serve(app, host="0.0.0.0", port=port)
