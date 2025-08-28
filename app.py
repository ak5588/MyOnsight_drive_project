import os
import re
import json
from flask import Flask, request, jsonify, send_from_directory
import yaml

# CORS for browser-based frontend
try:
    from flask_cors import CORS
    USE_CORS = True
except Exception:
    USE_CORS = False

SEVERITY_WEIGHTS = {"low": 1, "med": 3, "high": 5}
DEFAULT_JURISDICTION = "delaware"

ROOT_DIR = os.path.dirname(os.path.abspath(__file__))
RULES_PATH = os.path.join(ROOT_DIR, "rules", "rules.yml")
SUGGESTED_FIXES_PATH = os.path.join(ROOT_DIR, "data", "suggested_fixes.json")
WEB_DIR = os.path.join(ROOT_DIR, "web")

app = Flask(__name__, static_folder=None)
if USE_CORS:
    CORS(app)

def load_rules():
    if not os.path.exists(RULES_PATH):
        raise FileNotFoundError(f"Missing rules file at {RULES_PATH}")
    with open(RULES_PATH, "r", encoding="utf-8") as f:
        rules = yaml.safe_load(f)
    if not isinstance(rules, list):
        raise ValueError("rules.yml must be a list of rule objects")
    return rules

def load_fixes():
    if not os.path.exists(SUGGESTED_FIXES_PATH):
        return {}
    with open(SUGGESTED_FIXES_PATH, "r", encoding="utf-8") as f:
        return json.load(f)

RULES = load_rules()
SUGGESTED_FIXES = load_fixes()

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
        rid = rule.get("id", "unknown")
        severity = rule.get("severity", "low")
        rationale = rule.get("rationale", "")
        mock_ref = rule.get("mock_reference", "Ref: Placeholder-001")
        rtype = rule.get("type", "")
        triggered = False
        message = ""

        if rtype == "missing_keywords":
            keywords = rule.get("keywords", [])
            if not find_any(text_lc, keywords):
                triggered = True
                message = rule.get("description", f"Missing: {rid}")

        elif rtype == "missing_regex":
            pattern = rule.get("pattern")
            if pattern and not regex_found(text, pattern):
                triggered = True
                message = rule.get("description", f"Missing pattern: {rid}")

        elif rtype == "risky_regex":
            pattern = rule.get("pattern")
            if pattern and regex_found(text, pattern):
                triggered = True
                message = rule.get("description", f"Risky pattern: {rid}")

        elif rtype == "venue_mismatch":
            expected = jurisdiction.lower()
            others = [p.lower() for p in rule.get("other_places", [])]
            if any(p in text_lc for p in others) and expected not in text_lc:
                triggered = True
                message = rule.get("description", "Venue/jurisdiction mismatch")

        if triggered:
            severity = severity if severity in SEVERITY_WEIGHTS else "low"
            counts[severity] += 1
            score += SEVERITY_WEIGHTS[severity]
            issues.append({
                "id": rid,
                "severity": severity,
                "message": message,
                "rationale": rationale,
                "mock_reference": mock_ref,
                "suggested_fix": SUGGESTED_FIXES.get(rid, "")
            })

    return score, counts, issues

# API
@app.route("/review", methods=["POST"])
def review():
    data = request.get_json(silent=True) or {}
    text = data.get("text", "")
    jurisdiction = (data.get("jurisdiction") or DEFAULT_JURISDICTION).lower()

    if not isinstance(text, str) or not text.strip():
        return jsonify({"error": "text is required"}), 400
    if len(text) > 1_000_000:
        return jsonify({"error": "text too long"}), 400

    score, counts, issues = evaluate_rules(text, jurisdiction)
    return jsonify({
        "risk_score": score,
        "summary": {"high": counts["high"], "med": counts["med"], "low": counts["low"]},
        "issues": issues
    }), 200

# Frontend: serve index.html or health
@app.route("/", methods=["GET"])
def root_or_health():
    index = os.path.join(WEB_DIR, "index.html")
    if os.path.exists(index):
        return send_from_directory(WEB_DIR, "index.html")
    return jsonify({"status": "ok", "rules_loaded": len(RULES)}), 200

# Serve /styles.css and /app.js from web/
@app.route("/<path:filename>", methods=["GET"])
def serve_web_file(filename):
    path = os.path.join(WEB_DIR, filename)
    if os.path.exists(path):
        return send_from_directory(WEB_DIR, filename)
    return jsonify({"error": "not found"}), 404

# Serve /assets/*
@app.route("/assets/<path:filename>", methods=["GET"])
def serve_assets(filename):
    return send_from_directory(os.path.join(WEB_DIR, "assets"), filename)

# Serve /samples/*
@app.route("/samples/<path:filename>", methods=["GET"])
def serve_samples(filename):
    return send_from_directory(os.path.join(ROOT_DIR, "samples"), filename)

# Helpful GET for testers
@app.route("/review", methods=["GET"])
def review_get():
    return jsonify({"message": "Use POST /review with JSON {\"text\": \"...\", \"jurisdiction\": \"delaware\"}"}), 405

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    print(f"Starting Flask on http://127.0.0.1:{port}")
    app.run(host="127.0.0.1", port=port, debug=True)
