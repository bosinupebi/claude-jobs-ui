# claude-jobs-ui

`claude-jobs-ui` is a self-contained Flask app plus job-search pipeline. It gives you a browser UI for editing `config.json`, running the pipeline manually, reviewing generated job folders, and copying launchd commands without hand-editing JSON or wiring the app to an external scripts directory.

## What This Repo Does

The repo bundles both the UI and the pipeline in one place:

- `app.py` serves the web UI and persists config changes
- `job_search_daily.py` fetches jobs, scores them, generates application materials, and writes dated output folders
- `config.json` holds the editable candidate, source, search, scoring, cleanup, and tool settings

The UI includes these tabs:

- `Run` for manual runs and live log polling
- `Results` for browsing generated jobs and README details
- `Profile` for contact info, experience, education, source documents, and text-generation settings
- `Sources` for toggling/editing built-in job sources
- `Search` for location, age, and filtering controls
- `Scoring` for keyword tiers and remote bonus
- `Cleanup` for dated-folder retention rules
- `Setup` for copy-paste launchd commands

## Pipeline Highlights

The pipeline now supports:

- Source toggles via `disabled_sources`
- New built-in sources: `career_sites`, `themuse`, and `serpapi`
- Generation provider chaining with `claude_cli`, `anthropic_api`, and `codex_cli`
- Optional source-document ingestion for cover-letter and resume generation
- Auto-generated README strong-fit bullets
- ATS-aware versus direct-human prompt behavior depending on source
- Relative posted-date parsing like `today`, `yesterday`, and `3 days ago`
- Cleanup protection for dated folders containing jobs already marked applied

## Requirements

- Python 3.8+
- `pip3 install -r requirements.txt`
- `md-to-pdf` installed globally if you want PDF generation

Optional integrations:

- `ANTHROPIC_API_KEY` for Anthropic API fallback
- `SERPAPI_KEY` for Google Jobs via SerpAPI
- local `claude` CLI and/or `codex` CLI if you want CLI-first generation

## Getting Started

```bash
pip3 install -r requirements.txt
bash start.sh
```

The app starts on `http://localhost:5050` by default.

## Key Config Fields

Important newer config fields include:

- `tools.generation_provider_order`
- `tools.anthropic_model_fallback`
- `tools.codex_model_fallback`
- `tools.cover_letter_source`
- `tools.resume_source`
- `search.locations`
- `sources.career_sites.feeds`
- `sources.themuse`
- `sources.serpapi`
- `disabled_sources`

Saves are atomic and also create `config.json.bak`.

## Built-In Sources

This repo ships with editable support for:

- `jobbank`
- `remotive`
- `remoteok`
- `himalayas`
- `realworkfromanywhere`
- `jobicy`
- `indeed`
- `career_sites`
- `themuse`
- `serpapi`

`serpapi` only runs when `SERPAPI_KEY` is present.

## Generation Behavior

The default text-generation chain is:

1. `claude_cli`
2. `anthropic_api`
3. `codex_cli`

You can reorder that chain in the UI. The pipeline tries providers in order and stops on the first successful result.

## Running Tests

```bash
pip3 install pytest
PYTHONDONTWRITEBYTECODE=1 pytest -p no:cacheprovider tests/test_app.py -q
```

## Repo Layout

```text
claude-jobs-ui/
├── app.py
├── config.json
├── job_search_daily.py
├── requirements.txt
├── start.sh
├── tests/
│   └── test_app.py
└── templates/
    └── index.html
```
