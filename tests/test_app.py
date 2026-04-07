"""
Tests for the self-contained Job Search UI Flask app (app.py).
"""

import json
import sys
from pathlib import Path
from unittest.mock import patch

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


MINIMAL_CONFIG = {
    "candidate": {
        "name": "Test User",
        "title": "Software Developer",
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
            {
                "degree": "B.Sc. Computer Science",
                "school": "Example University",
                "dates": "2016–2020",
            }
        ],
    },
    "search": {
        "canada_location": "Toronto, ON",
        "days_back": 1,
        "locations": [],
        "max_results_per_tier": 5,
        "max_job_age_days": 3,
        "exclude_keywords": ["devops"],
    },
    "sources": {
        "jobbank": {"queries": ["software developer"]},
        "remotive": {"limit": 100},
        "remoteok": {"url": "https://remoteok.com/rss"},
        "himalayas": {"queries": ["full stack"], "limit": 20},
        "realworkfromanywhere": {"feeds": ["https://example.com/rss"]},
        "jobicy": {"url": "https://jobicy.com/feed"},
        "indeed": {"queries": ["software developer"]},
        "career_sites": {"feeds": []},
        "themuse": {"queries": ["Software Engineer"], "limit": 2},
        "serpapi": {"queries": ["Software Engineer"], "serpapi_locations": ["Canada"]},
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
        "anthropic_model_fallback": "claude-haiku-4-5-20251001",
        "codex_model_fallback": "gpt-5.4-mini",
        "generation_provider_order": [
            "claude_cli",
            "anthropic_api",
            "codex_cli",
        ],
        "cover_letter_source": "",
        "resume_source": "",
    },
    "disabled_sources": [],
}

MINIMAL_SETTINGS = {
    "plist_name": "com.jobsearch.plist",
}


@pytest.fixture
def config_file(tmp_path):
    cfg = tmp_path / "config.json"
    cfg.write_text(json.dumps(MINIMAL_CONFIG, indent=2))
    return cfg


@pytest.fixture
def settings_file(tmp_path):
    sf = tmp_path / "settings.json"
    sf.write_text(json.dumps(MINIMAL_SETTINGS, indent=2))
    return sf


@pytest.fixture
def logs_dir(tmp_path):
    path = tmp_path / "logs"
    path.mkdir()
    return path


@pytest.fixture
def flask_client(config_file, settings_file, logs_dir):
    import app as flask_app

    with patch.object(flask_app, "CONFIG_FILE", config_file), patch.object(
        flask_app, "SETTINGS_FILE", settings_file
    ), patch.object(flask_app, "LOGS_DIR", logs_dir):
        flask_app.app.config["TESTING"] = True
        with flask_app.app.test_client() as client:
            yield client, config_file, settings_file, logs_dir


class TestGetSettings:
    def test_returns_settings(self, flask_client):
        client, _, _, _ = flask_client
        res = client.get("/api/settings")
        assert res.status_code == 200
        data = res.get_json()
        assert data["plist_name"] == "com.jobsearch.plist"

    def test_returns_defaults_when_no_settings_file(self, tmp_path, config_file, logs_dir):
        import app as flask_app

        missing = tmp_path / "no_settings.json"
        with patch.object(flask_app, "CONFIG_FILE", config_file), patch.object(
            flask_app, "SETTINGS_FILE", missing
        ), patch.object(flask_app, "LOGS_DIR", logs_dir):
            flask_app.app.config["TESTING"] = True
            with flask_app.app.test_client() as client:
                res = client.get("/api/settings")
                data = res.get_json()
                assert data["plist_name"] == "com.example.jobsearch.plist"


class TestSaveSettings:
    def test_saves_valid_settings(self, flask_client):
        client, _, settings_file, _ = flask_client
        res = client.post("/api/settings", json={"plist_name": "com.test.plist"})
        assert res.status_code == 200
        assert res.get_json()["ok"] is True
        saved = json.loads(settings_file.read_text())
        assert saved["plist_name"] == "com.test.plist"


class TestGetConfig:
    def test_returns_config_and_meta(self, flask_client):
        client, _, _, _ = flask_client
        res = client.get("/api/config")
        assert res.status_code == 200
        data = res.get_json()
        assert "config" in data
        assert "meta" in data

    def test_config_contains_required_keys(self, flask_client):
        client, _, _, _ = flask_client
        data = client.get("/api/config").get_json()
        for key in ("candidate", "search", "sources", "scoring", "cleanup", "tools"):
            assert key in data["config"], f"Missing key: {key}"

    def test_meta_contains_paths_and_plist_name(self, flask_client):
        client, _, _, _ = flask_client
        meta = client.get("/api/config").get_json()["meta"]
        assert "pipeline_dir" in meta
        assert "plist_path" in meta
        assert "plist_name" in meta
        assert "launch_agents_dir" in meta

    def test_503_when_config_missing(self, tmp_path, settings_file, logs_dir):
        import app as flask_app

        missing = tmp_path / "gone.json"
        with patch.object(flask_app, "CONFIG_FILE", missing), patch.object(
            flask_app, "SETTINGS_FILE", settings_file
        ), patch.object(flask_app, "LOGS_DIR", logs_dir):
            flask_app.app.config["TESTING"] = True
            with flask_app.app.test_client() as client:
                res = client.get("/api/config")
                assert res.status_code == 503
                assert "error" in res.get_json()


class TestSaveConfig:
    def test_saves_valid_config(self, flask_client):
        client, cfg_path, _, _ = flask_client
        updated = json.loads(json.dumps(MINIMAL_CONFIG))
        updated["candidate"]["name"] = "Updated Name"
        res = client.post("/api/config", json=updated)
        assert res.status_code == 200
        assert res.get_json()["ok"] is True
        saved = json.loads(cfg_path.read_text())
        assert saved["candidate"]["name"] == "Updated Name"

    def test_creates_backup_on_save(self, flask_client):
        client, cfg_path, _, _ = flask_client
        client.post("/api/config", json=MINIMAL_CONFIG)
        backup = cfg_path.with_suffix(".json.bak")
        assert backup.exists()

    def test_rejects_missing_required_keys(self, flask_client):
        client, _, _, _ = flask_client
        incomplete = {"candidate": {}, "search": {}}
        res = client.post("/api/config", json=incomplete)
        assert res.status_code == 400
        assert "error" in res.get_json()

    def test_rejects_invalid_json_body(self, flask_client):
        client, _, _, _ = flask_client
        res = client.post(
            "/api/config",
            data="not-json",
            content_type="application/json",
        )
        assert res.status_code == 400

    def test_atomic_write_does_not_leave_tmp_file(self, flask_client):
        client, cfg_path, _, _ = flask_client
        client.post("/api/config", json=MINIMAL_CONFIG)
        tmp = cfg_path.with_suffix(".json.tmp")
        assert not tmp.exists()

    def test_preserves_comment_keys(self, flask_client):
        client, cfg_path, _, _ = flask_client
        with_comment = json.loads(json.dumps(MINIMAL_CONFIG))
        with_comment["_comment"] = "test comment"
        cfg_path.write_text(json.dumps(with_comment, indent=2))
        client.post("/api/config", json=with_comment)
        saved = json.loads(cfg_path.read_text())
        assert saved.get("_comment") == "test comment"

    def test_disabled_sources_written(self, flask_client):
        client, cfg_path, _, _ = flask_client
        payload = json.loads(json.dumps(MINIMAL_CONFIG))
        payload["disabled_sources"] = ["remoteok", "jobicy"]
        res = client.post("/api/config", json=payload)
        assert res.status_code == 200
        saved = json.loads(cfg_path.read_text())
        assert saved["disabled_sources"] == ["remoteok", "jobicy"]

    def test_generation_settings_written(self, flask_client):
        client, cfg_path, _, _ = flask_client
        payload = json.loads(json.dumps(MINIMAL_CONFIG))
        payload["tools"]["generation_provider_order"] = [
            "codex_cli",
            "claude_cli",
            "anthropic_api",
        ]
        payload["tools"]["anthropic_model_fallback"] = "claude-sonnet-4-20250514"
        payload["tools"]["codex_model_fallback"] = "gpt-5.4"
        res = client.post("/api/config", json=payload)
        assert res.status_code == 200
        saved = json.loads(cfg_path.read_text())
        assert saved["tools"]["generation_provider_order"] == [
            "codex_cli",
            "claude_cli",
            "anthropic_api",
        ]
        assert saved["tools"]["anthropic_model_fallback"] == "claude-sonnet-4-20250514"
        assert saved["tools"]["codex_model_fallback"] == "gpt-5.4"


class TestStatus:
    def test_returns_no_log_when_missing(self, flask_client):
        client, _, _, _ = flask_client
        res = client.get("/api/status")
        assert res.status_code == 200
        data = res.get_json()
        assert data["exists"] is False
        assert data["log"] == ""

    def test_returns_last_25_lines(self, flask_client, logs_dir):
        client, _, _, _ = flask_client
        from datetime import date

        log_file = logs_dir / f"{date.today()}.log"
        log_file.write_text("\n".join(f"Line {i}" for i in range(1, 51)))

        res = client.get("/api/status")
        data = res.get_json()
        assert data["exists"] is True
        lines = data["log"].splitlines()
        assert len(lines) == 25
        assert lines[0] == "Line 26"
        assert lines[-1] == "Line 50"


class TestIndex:
    def test_serves_html(self, flask_client):
        client, _, _, _ = flask_client
        res = client.get("/")
        assert res.status_code == 200
        assert b"<!DOCTYPE html>" in res.data or b"html" in res.data.lower()
