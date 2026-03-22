"""
Tests for Job Search UI Flask app (app.py).

Run with:
    cd ~/Desktop/claude-jobs-ui
    pip install pytest
    pytest tests/ -v
"""

import json
import shutil
import tempfile
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

MINIMAL_CONFIG = {
    "candidate": {
        "name": "Test User",
        "title": "Developer",
        "email": "test@example.com",
        "phone": "000-000-0000",
        "location": "Toronto, ON",
        "linkedin": "https://linkedin.com/in/test",
        "github": "https://github.com/test",
        "summary": "A developer.",
        "skills": ["Python", "JavaScript"],
        "experience": [
            {
                "title": "Developer",
                "company": "Acme",
                "dates": "2020 – Present",
                "location": "Toronto, ON",
                "bullets": ["Did stuff."],
            }
        ],
        "education": [
            {"degree": "B.Sc. Computer Science", "school": "U of T", "dates": "2016–2020"}
        ],
    },
    "search": {
        "canada_location": "Toronto, ON",
        "days_back": 1,
        "max_results_per_tier": 5,
        "exclude_keywords": ["devops"],
    },
    "sources": {
        "jobbank": {"queries": ["software developer"]},
        "remotive": {"limit": 100},
        "weworkremotely": {"feeds": ["https://example.com/rss"]},
        "remoteok": {"url": "https://remoteok.com/rss"},
        "himalayas": {"queries": ["full stack"], "limit": 20},
        "realworkfromanywhere": {"feeds": ["https://example.com/rss2"]},
        "jobicy": {"url": "https://jobicy.com/feed"},
    },
    "scoring": {
        "tier1_keywords": ["azure", "react"],
        "tier1_threshold": 2,
        "tier1_bonus_keywords": ["sql"],
        "tier2_keywords": ["react", "node.js"],
        "tier2_threshold": 2,
        "remote_bonus": 0.5,
    },
    "cleanup": {"trigger_after_days": 7, "keep_days": 2},
    "tools": {
        "md_to_pdf": "md-to-pdf",
        "claude_cli": "claude",
        "claude_model_fallback": "claude-haiku-4-5-20251001",
    },
}

MINIMAL_SETTINGS = {
    "config_path": "",  # overridden in fixtures
    "plist_name": "com.jobsearch.plist",
}


@pytest.fixture
def config_file(tmp_path):
    """Write a minimal config.json to a temp file and return its path."""
    cfg = tmp_path / "config.json"
    cfg.write_text(json.dumps(MINIMAL_CONFIG, indent=2))
    return cfg


@pytest.fixture
def settings_file(tmp_path, config_file):
    """Write a settings.json pointing at the temp config file."""
    sf = tmp_path / "settings.json"
    settings = {**MINIMAL_SETTINGS, "config_path": str(config_file)}
    sf.write_text(json.dumps(settings, indent=2))
    return sf


@pytest.fixture
def flask_client(config_file, settings_file):
    """Create a Flask test client with patched SETTINGS_FILE."""
    import app as flask_app

    with patch.object(flask_app, "SETTINGS_FILE", settings_file):
        flask_app.app.config["TESTING"] = True
        with flask_app.app.test_client() as client:
            yield client, config_file, settings_file


# ---------------------------------------------------------------------------
# GET /api/settings
# ---------------------------------------------------------------------------

class TestGetSettings:
    def test_returns_settings(self, flask_client):
        client, cfg, sf = flask_client
        res = client.get("/api/settings")
        assert res.status_code == 200
        data = res.get_json()
        assert "config_path" in data
        assert "plist_name" in data

    def test_returns_defaults_when_no_settings_file(self, tmp_path):
        import app as flask_app
        missing = tmp_path / "no_settings.json"
        with patch.object(flask_app, "SETTINGS_FILE", missing):
            flask_app.app.config["TESTING"] = True
            with flask_app.app.test_client() as client:
                res = client.get("/api/settings")
                data = res.get_json()
                assert data["config_path"] == ""
                assert data["plist_name"] == "com.jobsearch.plist"


class TestSaveSettings:
    def test_saves_valid_settings(self, flask_client):
        client, cfg, sf = flask_client
        res = client.post("/api/settings", json={
            "config_path": "/some/path/config.json",
            "plist_name": "com.test.plist",
        })
        assert res.status_code == 200
        assert res.get_json()["ok"] is True
        saved = json.loads(sf.read_text())
        assert saved["config_path"] == "/some/path/config.json"
        assert saved["plist_name"] == "com.test.plist"

    def test_rejects_missing_config_path(self, flask_client):
        client, _, _ = flask_client
        res = client.post("/api/settings", json={"plist_name": "com.test.plist"})
        assert res.status_code == 400
        assert "error" in res.get_json()

    def test_defaults_plist_name_if_omitted(self, flask_client):
        client, cfg, sf = flask_client
        res = client.post("/api/settings", json={"config_path": "/some/path/config.json"})
        assert res.status_code == 200
        saved = json.loads(sf.read_text())
        assert saved["plist_name"] == "com.jobsearch.plist"


# ---------------------------------------------------------------------------
# GET /api/config
# ---------------------------------------------------------------------------

class TestGetConfig:
    def test_returns_setup_required_when_not_configured(self, tmp_path):
        import app as flask_app
        missing = tmp_path / "no_settings.json"
        with patch.object(flask_app, "SETTINGS_FILE", missing):
            flask_app.app.config["TESTING"] = True
            with flask_app.app.test_client() as client:
                res = client.get("/api/config")
                assert res.status_code == 200
                data = res.get_json()
                assert data.get("setup_required") is True

    def test_returns_config_and_meta(self, flask_client):
        client, _, _ = flask_client
        res = client.get("/api/config")
        assert res.status_code == 200
        data = res.get_json()
        assert "config" in data
        assert "meta" in data

    def test_config_contains_required_keys(self, flask_client):
        client, _, _ = flask_client
        data = client.get("/api/config").get_json()
        for key in ("candidate", "search", "sources", "scoring", "cleanup", "tools"):
            assert key in data["config"], f"Missing key: {key}"

    def test_meta_contains_paths_and_plist_name(self, flask_client):
        client, _, _ = flask_client
        meta = client.get("/api/config").get_json()["meta"]
        assert "pipeline_dir" in meta
        assert "plist_path" in meta
        assert "plist_name" in meta
        assert "launch_agents_dir" in meta

    def test_503_when_config_missing(self, tmp_path, settings_file):
        import app as flask_app
        # Settings points to a non-existent file
        sf = tmp_path / "settings2.json"
        sf.write_text(json.dumps({"config_path": str(tmp_path / "gone.json"), "plist_name": "com.jobsearch.plist"}))
        with patch.object(flask_app, "SETTINGS_FILE", sf):
            flask_app.app.config["TESTING"] = True
            with flask_app.app.test_client() as client:
                res = client.get("/api/config")
                assert res.status_code == 503
                assert "error" in res.get_json()


# ---------------------------------------------------------------------------
# POST /api/config
# ---------------------------------------------------------------------------

class TestSaveConfig:
    def test_saves_valid_config(self, flask_client):
        client, cfg_path, _ = flask_client
        updated = json.loads(json.dumps(MINIMAL_CONFIG))
        updated["candidate"]["name"] = "Updated Name"
        res = client.post("/api/config", json=updated)
        assert res.status_code == 200
        assert res.get_json()["ok"] is True
        saved = json.loads(cfg_path.read_text())
        assert saved["candidate"]["name"] == "Updated Name"

    def test_creates_backup_on_save(self, flask_client):
        client, cfg_path, _ = flask_client
        client.post("/api/config", json=MINIMAL_CONFIG)
        backup = cfg_path.with_suffix(".json.bak")
        assert backup.exists(), "Backup file should be created"

    def test_rejects_missing_required_keys(self, flask_client):
        client, _, _ = flask_client
        incomplete = {"candidate": {}, "search": {}}  # missing keys
        res = client.post("/api/config", json=incomplete)
        assert res.status_code == 400
        assert "error" in res.get_json()

    def test_rejects_invalid_json_body(self, flask_client):
        client, _, _ = flask_client
        res = client.post(
            "/api/config",
            data="not-json",
            content_type="application/json",
        )
        assert res.status_code == 400

    def test_atomic_write_does_not_leave_tmp_file(self, flask_client):
        client, cfg_path, _ = flask_client
        client.post("/api/config", json=MINIMAL_CONFIG)
        tmp = cfg_path.with_suffix(".json.tmp")
        assert not tmp.exists(), ".json.tmp should be cleaned up after save"

    def test_preserves_comment_keys(self, flask_client):
        client, cfg_path, _ = flask_client
        with_comment = json.loads(json.dumps(MINIMAL_CONFIG))
        with_comment["_comment"] = "test comment"
        cfg_path.write_text(json.dumps(with_comment, indent=2))
        client.post("/api/config", json=with_comment)
        saved = json.loads(cfg_path.read_text())
        assert saved.get("_comment") == "test comment"

    def test_disabled_sources_written(self, flask_client):
        client, cfg_path, _ = flask_client
        payload = json.loads(json.dumps(MINIMAL_CONFIG))
        payload["disabled_sources"] = ["remoteok", "jobicy"]
        res = client.post("/api/config", json=payload)
        assert res.status_code == 200
        saved = json.loads(cfg_path.read_text())
        assert saved["disabled_sources"] == ["remoteok", "jobicy"]

    def test_503_when_not_configured(self, tmp_path):
        import app as flask_app
        missing = tmp_path / "no_settings.json"
        with patch.object(flask_app, "SETTINGS_FILE", missing):
            flask_app.app.config["TESTING"] = True
            with flask_app.app.test_client() as client:
                res = client.post("/api/config", json=MINIMAL_CONFIG)
                assert res.status_code == 503


# ---------------------------------------------------------------------------
# GET /api/status
# ---------------------------------------------------------------------------

class TestStatus:
    def test_returns_no_log_when_missing(self, flask_client):
        client, _, _ = flask_client
        res = client.get("/api/status")
        assert res.status_code == 200
        data = res.get_json()
        assert data["exists"] is False
        assert data["log"] == ""

    def test_returns_last_25_lines(self, flask_client, tmp_path):
        client, cfg_path, sf = flask_client
        import app as flask_app
        from datetime import date

        # Write settings pointing to a new dir that has a logs/ folder
        logs_dir = tmp_path / "logs"
        logs_dir.mkdir()
        log_file = logs_dir / f"{date.today()}.log"
        log_file.write_text("\n".join(f"Line {i}" for i in range(1, 51)))

        fake_cfg = tmp_path / "config.json"
        fake_cfg.write_text(json.dumps(MINIMAL_CONFIG))
        new_sf = tmp_path / "settings3.json"
        new_sf.write_text(json.dumps({"config_path": str(fake_cfg), "plist_name": "com.jobsearch.plist"}))

        with patch.object(flask_app, "SETTINGS_FILE", new_sf):
            flask_app.app.config["TESTING"] = True
            with flask_app.app.test_client() as c:
                res = c.get("/api/status")
                data = res.get_json()
                assert data["exists"] is True
                lines = data["log"].splitlines()
                assert len(lines) == 25
                assert lines[0] == "Line 26"
                assert lines[-1] == "Line 50"

    def test_returns_empty_when_not_configured(self, tmp_path):
        import app as flask_app
        missing = tmp_path / "no_settings.json"
        with patch.object(flask_app, "SETTINGS_FILE", missing):
            flask_app.app.config["TESTING"] = True
            with flask_app.app.test_client() as client:
                res = client.get("/api/status")
                data = res.get_json()
                assert data["exists"] is False


# ---------------------------------------------------------------------------
# Index route
# ---------------------------------------------------------------------------

class TestIndex:
    def test_serves_html(self, flask_client):
        client, _, _ = flask_client
        res = client.get("/")
        assert res.status_code == 200
        assert b"<!DOCTYPE html>" in res.data or b"html" in res.data.lower()
