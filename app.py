"""
Job Search UI — self-contained Flask app bundling the pipeline.

The pipeline (job_search_daily.py) and config (config.json) live alongside
this file. Output folders (YYYY-MM-DD/), logs/, and seen_jobs.json are written
to the same directory.
"""

import argparse
import json
import re
import shutil
import subprocess
import sys
import threading
from datetime import date
from pathlib import Path
from xml.sax.saxutils import escape as xml_escape

from flask import Flask, jsonify, render_template, request

BASE_DIR = Path(__file__).parent.resolve()
CONFIG_FILE = BASE_DIR / "config.json"
SETTINGS_FILE = BASE_DIR / "settings.json"
LOGS_DIR = BASE_DIR / "logs"
PIPELINE_SCRIPT = BASE_DIR / "job_search_daily.py"
RUN_DAILY_SCRIPT = BASE_DIR / "run_daily.sh"

PLIST_NAME_DEFAULT = "com.example.jobsearch.plist"
REQUIRED_KEYS = {"candidate", "search", "sources", "scoring", "cleanup", "tools"}

app = Flask(__name__)
app.config["TEMPLATES_AUTO_RELOAD"] = True

# ── Run state ─────────────────────────────────────────────────────────────────
_run_state = {"running": False, "pid": None, "exit_code": None}
_run_lock = threading.Lock()


def _read_recent_log(max_lines: int) -> tuple[str, bool]:
    """Return the last `max_lines` lines from today's log file."""
    today = date.today().isoformat()
    log_file = LOGS_DIR / f"{today}.log"
    if not log_file.exists():
        return "", False

    lines = log_file.read_text(encoding="utf-8").splitlines()
    return "\n".join(lines[-max_lines:]), True


# ── Settings helpers ──────────────────────────────────────────────────────────

def get_settings():
    if SETTINGS_FILE.exists():
        try:
            return json.loads(SETTINGS_FILE.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, IOError):
            pass
    return {}


def _normalise_plist_name(value) -> str:
    """Return a safe launchd plist filename."""
    name = (value or PLIST_NAME_DEFAULT).strip()
    if not re.match(r"^[A-Za-z0-9_.-]+$", name):
        name = PLIST_NAME_DEFAULT
    if not name.endswith(".plist"):
        name += ".plist"
    return name


def _ensure_plist(plist_name: str) -> Path:
    """Write a launchd plist for this checkout and return its path."""
    plist_name = _normalise_plist_name(plist_name)
    service_id = plist_name[:-6]
    plist_path = BASE_DIR / plist_name
    log_dir = Path.home() / "Library" / "Logs"
    home = Path.home()
    content = f"""<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN"
  "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>Label</key>
  <string>{xml_escape(service_id)}</string>

  <key>ProgramArguments</key>
  <array>
    <string>/bin/bash</string>
    <string>{xml_escape(str(RUN_DAILY_SCRIPT))}</string>
  </array>

  <key>StartCalendarInterval</key>
  <dict>
    <key>Hour</key>
    <integer>8</integer>
    <key>Minute</key>
    <integer>0</integer>
  </dict>

  <key>WorkingDirectory</key>
  <string>{xml_escape(str(BASE_DIR))}</string>

  <key>StandardOutPath</key>
  <string>{xml_escape(str(log_dir / f"{service_id}.log"))}</string>
  <key>StandardErrorPath</key>
  <string>{xml_escape(str(log_dir / f"{service_id}.error.log"))}</string>

  <key>EnvironmentVariables</key>
  <dict>
    <key>PATH</key>
    <string>{xml_escape(str(home / ".nvm/versions/node/v23.1.0/bin"))}:/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin</string>
    <key>HOME</key>
    <string>{xml_escape(str(home))}</string>
  </dict>
</dict>
</plist>
"""
    plist_path.write_text(content, encoding="utf-8")
    return plist_path


# ── Routes ────────────────────────────────────────────────────────────────────

@app.route("/")
def index():
    return render_template("index.html")


@app.route("/api/settings")
def get_settings_endpoint():
    s = get_settings()
    return jsonify({
        "plist_name": _normalise_plist_name(s.get("plist_name")),
    })


@app.route("/api/settings", methods=["POST"])
def save_settings():
    data = request.get_json(force=True) or {}
    settings = get_settings()
    if data.get("plist_name"):
        settings["plist_name"] = _normalise_plist_name(data["plist_name"])
        _ensure_plist(settings["plist_name"])
    SETTINGS_FILE.write_text(json.dumps(settings, indent=2, ensure_ascii=False), encoding="utf-8")
    return jsonify({"ok": True})


@app.route("/api/config")
def get_config():
    if not CONFIG_FILE.exists():
        return jsonify({"error": "config.json not found. Reinstall the app."}), 503

    cfg = json.loads(CONFIG_FILE.read_text(encoding="utf-8"))
    settings = get_settings()
    plist_name = _normalise_plist_name(settings.get("plist_name"))
    plist_path = _ensure_plist(plist_name)

    return jsonify({
        "config": cfg,
        "meta": {
            "pipeline_dir": str(BASE_DIR),
            "plist_name": plist_name,
            "plist_path": str(plist_path),
            "run_daily_path": str(RUN_DAILY_SCRIPT),
            "launch_agents_dir": str(Path.home() / "Library" / "LaunchAgents"),
        },
    })


@app.route("/api/config", methods=["POST"])
def save_config():
    data = request.get_json(force=True)
    if data is None:
        return jsonify({"error": "Invalid JSON body"}), 400

    missing = REQUIRED_KEYS - set(data.keys())
    if missing:
        return jsonify({"error": f"Missing required keys: {sorted(missing)}"}), 400

    backup = CONFIG_FILE.with_suffix(".json.bak")
    if CONFIG_FILE.exists():
        shutil.copy2(CONFIG_FILE, backup)

    tmp = CONFIG_FILE.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
    tmp.rename(CONFIG_FILE)

    return jsonify({"ok": True})


# ── Run pipeline ──────────────────────────────────────────────────────────────

@app.route("/api/run", methods=["POST"])
def run_pipeline():
    global _run_state
    with _run_lock:
        if _run_state["running"]:
            return jsonify({"error": "A run is already in progress."}), 409

        data = request.get_json(force=True) or {}
        args = [sys.executable, str(PIPELINE_SCRIPT)]
        if data.get("dry_run"):
            args.append("--dry-run")
        if data.get("force"):
            args.append("--force")
        run_date = data.get("date") or data.get("run_date")
        if run_date:
            if not re.match(r"^\d{4}-\d{2}-\d{2}$", str(run_date)):
                return jsonify({"error": "Invalid run date. Use YYYY-MM-DD."}), 400
            args.extend(["--date", str(run_date)])
        max_results = data.get("max_results")
        if max_results not in (None, ""):
            try:
                max_results_int = int(max_results)
            except (TypeError, ValueError):
                return jsonify({"error": "max_results must be a positive integer."}), 400
            if max_results_int < 1:
                return jsonify({"error": "max_results must be a positive integer."}), 400
            args.extend(["--max-results", str(max_results_int)])

        try:
            proc = subprocess.Popen(
                args,
                cwd=str(BASE_DIR),
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
        except Exception as exc:
            return jsonify({"error": str(exc)}), 500

        _run_state = {"running": True, "pid": proc.pid, "exit_code": None}

    def _monitor():
        exit_code = proc.wait()
        with _run_lock:
            _run_state["running"] = False
            _run_state["exit_code"] = exit_code
            _run_state["pid"] = None

    threading.Thread(target=_monitor, daemon=True).start()
    return jsonify({"ok": True, "pid": proc.pid})


@app.route("/api/run/status")
def run_status():
    with _run_lock:
        state = dict(_run_state)

    log_text, _ = _read_recent_log(60)

    return jsonify({
        "running": state["running"],
        "exit_code": state["exit_code"],
        "log": log_text,
    })


@app.route("/api/status")
def status():
    log_text, exists = _read_recent_log(25)
    return jsonify({
        "exists": exists,
        "log": log_text,
    })


# ── Jobs listing ──────────────────────────────────────────────────────────────

@app.route("/api/jobs")
def list_jobs():
    date_pattern = re.compile(r"^\d{4}-\d{2}-\d{2}$")
    result = []

    for date_dir in sorted(BASE_DIR.iterdir(), reverse=True):
        if not date_dir.is_dir() or not date_pattern.match(date_dir.name):
            continue

        jobs = []
        for job_dir in sorted(date_dir.iterdir()):
            if not job_dir.is_dir():
                continue
            readme = job_dir / "README.md"
            meta = _parse_readme_meta(readme) if readme.exists() else {}
            jobs.append({
                "slug": job_dir.name,
                "title": meta.get("title", job_dir.name),
                "company": meta.get("company", ""),
                "tier": meta.get("tier", ""),
                "score": meta.get("score", ""),
                "url": meta.get("url", ""),
                "has_cover": any(job_dir.glob("*cover-letter.pdf")),
                "has_resume": any(job_dir.glob("*resume.pdf")),
            })

        if jobs:
            result.append({"date": date_dir.name, "jobs": jobs})

    return jsonify(result)


@app.route("/api/jobs/<date_str>/<slug>/readme")
def get_readme(date_str, slug):
    if not re.match(r"^\d{4}-\d{2}-\d{2}$", date_str):
        return jsonify({"error": "Invalid date"}), 400
    if not re.match(r"^[\w\-]+$", slug):
        return jsonify({"error": "Invalid slug"}), 400

    readme = BASE_DIR / date_str / slug / "README.md"
    if not readme.exists():
        return jsonify({"error": "Not found"}), 404

    return jsonify({"content": readme.read_text(encoding="utf-8")})


def _parse_readme_meta(readme_path: Path) -> dict:
    """Extract title, company, tier, score, url from a job README.md."""
    try:
        text = readme_path.read_text(encoding="utf-8")
    except Exception:
        return {}

    meta = {}

    m = re.search(r"^#\s+(.+?)\s+@\s+(.+)$", text, re.MULTILINE)
    if m:
        meta["title"] = m.group(1).strip()
        meta["company"] = m.group(2).strip()

    m = re.search(r"\*\*Tier:\*\*\s*(\d+)", text)
    if m:
        meta["tier"] = int(m.group(1))

    m = re.search(r"\*\*Score:\*\*\s*([\d.]+)", text)
    if m:
        meta["score"] = float(m.group(1))

    m = re.search(r"\[Apply here\]\(([^)]+)\)", text)
    if m:
        meta["url"] = m.group(1)

    return meta


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--port", type=int, default=5050)
    args = parser.parse_args()
    print(f"  Job Search UI → http://localhost:{args.port}")
    app.run(host="127.0.0.1", port=args.port, debug=False)
