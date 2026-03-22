"""
Job Search UI — Flask config proxy for job_search_daily.py
"""

import argparse
import json
import shutil
from datetime import date
from pathlib import Path

from flask import Flask, jsonify, render_template, request

SETTINGS_FILE = Path(__file__).parent / "settings.json"
PLIST_NAME_DEFAULT = "com.jobsearch.plist"

REQUIRED_KEYS = {"candidate", "search", "sources", "scoring", "cleanup", "tools"}

app = Flask(__name__)


# ── Settings helpers ─────────────────────────────────────────────────────────

def get_settings():
    if SETTINGS_FILE.exists():
        try:
            return json.loads(SETTINGS_FILE.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, IOError):
            pass
    return None


def get_config_path():
    settings = get_settings()
    if settings and settings.get("config_path"):
        return Path(settings["config_path"]).expanduser()
    return None


# ── Routes ───────────────────────────────────────────────────────────────────

@app.route("/")
def index():
    return render_template("index.html")


@app.route("/api/settings")
def get_settings_endpoint():
    settings = get_settings()
    if settings:
        return jsonify({
            "config_path": settings.get("config_path", ""),
            "plist_name": settings.get("plist_name", PLIST_NAME_DEFAULT),
        })
    return jsonify({"config_path": "", "plist_name": PLIST_NAME_DEFAULT})


@app.route("/api/settings", methods=["POST"])
def save_settings():
    data = request.get_json(force=True)
    if not data or not data.get("config_path"):
        return jsonify({"error": "config_path is required"}), 400

    settings = {
        "config_path": data["config_path"],
        "plist_name": data.get("plist_name", PLIST_NAME_DEFAULT),
    }
    SETTINGS_FILE.write_text(
        json.dumps(settings, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    return jsonify({"ok": True})


@app.route("/api/config")
def get_config():
    config_path = get_config_path()
    if config_path is None:
        return jsonify({"setup_required": True, "ok": False})

    if not config_path.exists():
        return (
            jsonify({"error": "config.json not found — check the path in Settings."}),
            503,
        )

    cfg = json.loads(config_path.read_text(encoding="utf-8"))
    settings = get_settings()
    plist_name = settings.get("plist_name", PLIST_NAME_DEFAULT) if settings else PLIST_NAME_DEFAULT
    pipeline_dir = config_path.parent

    return jsonify({
        "config": cfg,
        "meta": {
            "pipeline_dir": str(pipeline_dir),
            "plist_name": plist_name,
            "plist_path": str(pipeline_dir / plist_name),
            "launch_agents_dir": str(Path.home() / "Library" / "LaunchAgents"),
        },
    })


@app.route("/api/config", methods=["POST"])
def save_config():
    config_path = get_config_path()
    if config_path is None:
        return jsonify({"error": "App not configured — complete setup first."}), 503

    data = request.get_json(force=True)
    if data is None:
        return jsonify({"error": "Invalid JSON body"}), 400

    missing = REQUIRED_KEYS - set(data.keys())
    if missing:
        return jsonify({"error": f"Missing required keys: {sorted(missing)}"}), 400

    # Backup existing config
    backup = config_path.with_suffix(".json.bak")
    if config_path.exists():
        shutil.copy2(config_path, backup)

    # Atomic write: write to .tmp then rename
    tmp = config_path.with_suffix(".json.tmp")
    tmp.write_text(
        json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    tmp.rename(config_path)

    return jsonify({"ok": True})


@app.route("/api/status")
def get_status():
    config_path = get_config_path()
    if config_path is None:
        return jsonify({"log": "", "exists": False})

    pipeline_dir = config_path.parent
    log_file = pipeline_dir / "logs" / f"{date.today()}.log"
    if log_file.exists():
        lines = log_file.read_text(encoding="utf-8").splitlines()[-25:]
        return jsonify({"log": "\n".join(lines), "exists": True})
    return jsonify({"log": "", "exists": False})


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--port", type=int, default=5050)
    args = parser.parse_args()
    print(f"  Job Search UI → http://localhost:{args.port}")
    app.run(host="127.0.0.1", port=args.port, debug=False)
