# claude-jobs-ui

A local web UI for configuring a job search pipeline without editing JSON by hand. Built with Python (Flask) and Bootstrap 5 — no build step, no cloud accounts, no installation beyond one `pip install`.

---

## What it does

The daily job search pipeline is entirely headless — it runs via a macOS launchd scheduler and generates tailored cover letters and resumes using Claude. This UI lets you tweak every configuration option through a browser form instead of editing `config.json` directly.

| Tab | What you can configure |
|-----|------------------------|
| **Profile** | Your name, contact info, summary, skills, work experience (with bullet reordering), and education |
| **Sources** | Enable or disable any job board source; edit search queries, feed URLs, and fetch limits; add your own custom sources |
| **Search** | How many jobs to process per run, how many days back to look, and keywords to exclude |
| **Scoring** | Tier 1 / Tier 2 keyword lists and thresholds, remote job score bonus |
| **Cleanup** | How many dated output folders to keep and when to start trimming them |
| **Setup** | Copy-paste shell commands to install, start, check, and remove the launchd scheduler |

Changes are saved immediately to the pipeline's `config.json` with a `.json.bak` backup created automatically on every save.

---

## Requirements

| Dependency | Version | Notes |
|------------|---------|-------|
| Python 3 | 3.8+ | Ships with macOS |
| Flask | latest | Installed automatically by `start.sh` |
| Internet (CDN) | — | Bootstrap 5 is loaded from CDN |

The pipeline itself (`job_search_daily.py`) requires additional dependencies — see its own `README.md`.

---

## Getting started

```bash
# 1. Clone or download this repo
git clone https://github.com/bosinupebi/claude-jobs-ui.git
cd claude-jobs-ui

# 2. Start the server
bash start.sh
```

`start.sh` will:
1. Check that Python 3 is available
2. Install Flask if it isn't already (`pip3 install flask`)
3. Start the Flask server on `http://localhost:5050` (falls back to `:5051`)
4. Open your browser automatically after 1.5 seconds

**First run:** A setup screen will appear asking for the path to your pipeline's `config.json`. Enter the absolute path (e.g. `~/path/to/claude-jobs/config.json`) and click **Save & Continue**. This path is saved locally in `settings.json` (gitignored) and never committed.

Press **Ctrl+C** in the Terminal to stop the server.

---

## Reconfiguring the config path

Click the **⚙** gear icon in the top navigation bar at any time to reopen the setup screen and change the config path or launchd service name.

---

## Usage guide

### Saving changes

Every change you make marks the page as "unsaved" — a yellow banner appears at the top. Click **Save All Changes** (top-right) to write the changes to `config.json`. A green toast confirms success.

> A backup is written to `config.json.bak` on every save. To roll back, copy the backup over the original:
> ```bash
> cp /path/to/config.json.bak /path/to/config.json
> ```

### Profile tab

- **Skills** — Type a skill and press **Enter** or **comma** to add it as a tag. Click **×** to remove one. **Backspace** on an empty input removes the last tag.
- **Experience bullets** — Drag the ⠿ handle to reorder bullets. Click **×** to remove one, **+ Add Bullet** to append a new one.
- **Adding a role** — Click **+ Add Role** in the Experience card header.
- **Removing a role** — Expand the role and click **Remove Role** (confirmation required).

### Sources tab

Each of the built-in job board sources has a toggle switch in its card header. Disabling a source skips it during the next run — your queries and URLs are never deleted.

| Source | Type | Notes |
|--------|------|-------|
| Job Bank Canada | RSS | Canadian gov't board |
| Remotive | JSON API | Global remote — max ~4 req/day |
| We Work Remotely | RSS | Curated remote — full-stack + back-end |
| RemoteOK | RSS | Broad global remote |
| Himalayas | JSON API | Global remote — multi-query search |
| Real Work From Anywhere | RSS | Category remote feeds |
| Jobicy | RSS | Dev jobs incl. hybrid and onsite |

**Adding a custom source** — Click **+ Add Source** at the bottom of the sources list. Choose a type (RSS Feed, JSON API, or Search-based RSS), enter the details, and click **Add Source**. Custom sources appear with a **Custom** badge and a trash icon to delete them.

### Scoring tab

Jobs are tiered by how well they match your keywords:

- **Tier 1** — Must have ≥ N of your Tier 1 keywords. Bonus keywords add to the score without counting toward the threshold.
- **Tier 2** — Must have ≥ N of your Tier 2 keywords (fallback tier).
- **Tier 3** — Everything else.

The **Remote Bonus** slider adds a fixed score increment to any job flagged as remote.

### Cleanup tab

The pipeline stores output in dated folders. The cleanup policy:

- Cleanup only runs once **Trigger After** folders exist (prevents early deletion during the first week)
- When triggered, it keeps the **Keep** most recent folders and permanently deletes the rest
- Logs, `seen_jobs.json`, scripts, and config files are never touched

### Setup tab

The Setup tab shows ready-to-run Terminal commands for managing the launchd scheduler. Each command has a **Copy** button. The UI never modifies launchd — you run the commands yourself.

---

## File structure

```
claude-jobs-ui/
├── app.py              Flask server — reads and writes config.json
├── requirements.txt    Python dependencies (flask only)
├── start.sh            Launch script — installs Flask, starts server, opens browser
├── README.md           This file
├── .gitignore          Excludes secrets, settings, macOS junk, and build artefacts
├── tests/
│   └── test_app.py     Pytest test suite for the Flask backend
└── templates/
    └── index.html      Single-page Bootstrap 5 app (all tabs + JS inline)
```

`settings.json` is created on first run and is gitignored — it stores your local config path.

---

## Running tests

```bash
cd ~/Desktop/claude-jobs-ui
pip3 install pytest flask
pytest tests/ -v
```

The test suite covers:
- `GET /api/settings` — returns settings, defaults when no settings file exists
- `POST /api/settings` — saves settings, validates required fields
- `GET /api/config` — returns `setup_required` when unconfigured, returns config + meta otherwise, handles missing config file (503)
- `POST /api/config` — saves config, creates backup, validates required keys, atomic write, preserves `_comment` keys, writes `disabled_sources`, returns 503 when unconfigured
- `GET /api/status` — returns log tail, handles missing log file, handles unconfigured state
- `GET /` — serves the HTML page

---

## Architecture notes

### Config proxy pattern

`app.py` is a thin proxy — it reads `config.json` on every `GET /api/config` request and writes it on every `POST /api/config`. It holds no in-memory state between requests. This means:

- Multiple browser tabs won't conflict (last save wins)
- Restarting the server loses nothing
- You can still edit `config.json` by hand while the server is running (refresh the page to pick up changes)

### Atomic writes

`POST /api/config` writes to `config.json.tmp` first, then renames it over `config.json`. On POSIX filesystems (macOS included), rename is atomic — if the process is killed mid-write, the original config is untouched.

### `settings.json`

Stores the path to `config.json` and the launchd service name. Created by the setup screen on first run. Gitignored — never committed to the repo.

### `disabled_sources` key

The pipeline's `fetch_all_jobs()` function reads `config["disabled_sources"]` (a list of source key strings) and skips those fetchers. The Sources tab toggle writes this list. If the key is absent the pipeline behaves as before (all sources enabled).

### `_comment` key preservation

The config file may contain `_comment` and similar keys for human readability. The UI deep-clones the originally-loaded config before collecting form values, so any keys it doesn't know about survive every save.

---

## Troubleshooting

| Problem | Fix |
|---------|-----|
| Setup screen appears every time | `settings.json` was deleted or is unreadable — re-enter the config path |
| Browser doesn't open | Navigate manually to `http://localhost:5050` |
| Port already in use | `start.sh` falls back to `:5051` automatically |
| "config.json not found" error | The path in Settings is wrong or the file doesn't exist — click ⚙ to reconfigure |
| Flask not found | Run `pip3 install flask` manually, then re-run `start.sh` |
| Save fails with "Missing required keys" | The config is missing a top-level section — restore from `config.json.bak` |
