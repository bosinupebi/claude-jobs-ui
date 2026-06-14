# claude-jobs-ui

`claude-jobs-ui` is a self-contained Flask app plus autonomous job-search pipeline. It gives you a browser UI for editing `config.json`, running searches manually, reviewing generated job folders, and installing a daily macOS `launchd` scheduler without hand-editing JSON.

Despite the repository name, the workflow is agent-agnostic. The UI, terminal, `launchd`, cron, Codex, Claude, or any other automation agent can run `job_search_daily.py`; the configured generation providers only control how documents are drafted.

## What It Includes

- `app.py` serves the web UI, persists config changes, starts pipeline runs, and generates a checkout-specific launchd plist.
- `job_search_daily.py` fetches jobs, scores them, validates links, generates application materials, and writes dated output folders.
- `run_daily.sh` is the launchd/cron wrapper. It loads `.env`, fixes `PATH`, writes runner logs, and invokes the pipeline from any scheduler or agent.
- `config.json` contains editable candidate, source, search, scoring, cleanup, and generation settings.

The UI tabs cover:

- `Run`: dry runs, full runs, force reprocessing, date override, max-results override, and live log polling.
- `Results`: generated job folders, README details, apply links, and PDF status badges.
- `Profile`: contact info, experience, education, source document paths, provider order, models, fast mode, fallback documents, and timeouts.
- `Sources`: toggles and editable settings for all built-in sources.
- `Search`: location, job age, result count, and exclude-keyword controls.
- `Scoring`: Tier 1/Tier 2 keywords, bonus keywords, thresholds, and remote bonus.
- `Cleanup`: dated-folder retention settings with applied-job protection.
- `Setup`: copy-paste commands for launchd install, manual runs, dry runs, logs, and uninstall.

## Pipeline Features

- Source toggles via `disabled_sources`.
- Built-in sources: Job Bank Canada, Remotive, RemoteOK, Himalayas, Real Work From Anywhere, Jobicy, Indeed RSS, career sites, The Muse, and Google Jobs via SerpAPI.
- Career-site ingestion for Ashby, Greenhouse, Lever, and Recruitee public job boards.
- Relative posted-date parsing such as `today`, `yesterday`, and `3 days ago`.
- Two-phase filtering: title relevance first, then full-description fetching and scoring.
- URL validation before generating application materials.
- Provider chaining across `claude_cli`, `anthropic_api`, and `codex_cli`.
- Fast generation mode to avoid embedding source PDFs during local CLI fallback runs.
- Optional deterministic markdown fallback documents when all model providers fail.
- Company-specific output filenames, for example `your-name-company-cover-letter.pdf`.
- Cleanup preservation for dated folders containing jobs marked `- [x] Applied`.

## Requirements

- [Python 3.8+](https://www.python.org/downloads/)
- Python dependencies from [`requirements.txt`](requirements.txt): `pip3 install -r requirements.txt`
- [md-to-pdf](https://www.npmjs.com/package/md-to-pdf) installed globally if you want PDF generation: `npm install -g md-to-pdf`

Optional integrations:

- At least one generation path is recommended: [Claude CLI](https://docs.anthropic.com/en/docs/claude-code), [Anthropic API](https://docs.anthropic.com/en/api/overview), [Codex CLI](https://developers.openai.com/codex/cli), or [`tools.deterministic_fallback_documents`](#key-config-fields).
- [`claude` CLI](https://docs.anthropic.com/en/docs/claude-code) if you want Claude available as one document-generation provider.
- [`codex` CLI](https://developers.openai.com/codex/cli) if you want Codex available as one document-generation provider.
- [`ANTHROPIC_API_KEY`](https://docs.anthropic.com/en/api/admin-api/apikeys/get-api-key) for Anthropic API fallback.
- [`SERPAPI_KEY`](https://serpapi.com/manage-api-key) for Google Jobs via [SerpAPI](https://serpapi.com/google-jobs-api).

## Getting Started

```bash
cp .env.example .env
pip3 install -r requirements.txt
bash start.sh
```

The app starts on `http://localhost:5050` by default, or `5051` if `5050` is already in use.

## Running The Pipeline

From the UI, use the `Run` tab.

From the terminal:

```bash
python3 job_search_daily.py
python3 job_search_daily.py --dry-run
python3 job_search_daily.py --force
python3 job_search_daily.py --date 2026-03-22
python3 job_search_daily.py --force --date 2026-03-22 --max-results 3
```

## Output

```text
claude-jobs-ui/
├── 2026-03-22/
│   └── 01-company-role/
│       ├── README.md
│       ├── your-name-company-cover-letter.md
│       ├── your-name-company-cover-letter.pdf
│       ├── your-name-company-resume.md
│       └── your-name-company-resume.pdf
├── logs/
│   ├── 2026-03-22.log
│   └── runner.log
└── seen_jobs.json
```

Runtime output, generated plist files, logs, `.env`, and `seen_jobs.json` are ignored by git.

## Key Config Fields

- `candidate`: profile, skills, experience, education, and contact details used in generated documents.
- `disabled_sources`: source keys skipped during runs.
- `search.max_results_per_tier`: default number of ranked jobs to process per run.
- `search.max_job_age_days`: posted-date freshness filter.
- `sources.career_sites.feeds`: company career-page URLs.
- `sources.serpapi`: Google Jobs queries and SerpAPI locations.
- `scoring.tier1_keywords`, `scoring.tier2_keywords`, and `scoring.remote_bonus`: ranking behavior.
- `tools.generation_provider_order`: generation preference order.
- `tools.fast_generation_mode`: skip source documents by default for faster prompts.
- `tools.include_source_documents_in_fast_mode`: embed source documents even in fast mode.
- `tools.deterministic_fallback_documents`: write template-based documents if model generation fails.
- `tools.text_generation_timeout_seconds`, `tools.resume_generation_timeout_seconds`, and `tools.resume_retry_timeout_seconds`: generation timeouts.

Saves are atomic and create `config.json.bak`.

## Daily Scheduling

Open the `Setup` tab after starting the app. The app generates a launchd plist for the current checkout path and shows commands to:

- check whether the service is installed
- copy the plist into `~/Library/LaunchAgents`
- load the service
- run the pipeline manually
- view logs
- uninstall the service

The generated plist runs `run_daily.sh` every day at 08:00 local time.

## Tests

```bash
pip3 install pytest
PYTHONDONTWRITEBYTECODE=1 pytest -p no:cacheprovider tests/test_app.py -q
```

## Repo Layout

```text
claude-jobs-ui/
├── .env.example
├── app.py
├── config.json
├── job_search_daily.py
├── requirements.txt
├── run_daily.sh
├── start.sh
├── tests/
│   └── test_app.py
└── templates/
    └── index.html
```
