# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Quick Start
```powershell
python -m venv venv
venv\Scripts\activate        # Windows
pip install -r requirements.txt
cp .env.example .env         # fill in API keys
python server.py             # http://localhost:5000
```

## Architecture

Single-file Flask backend (`server.py`) + single-file vanilla JS frontend (`static/index.html`). No build step, no framework.

**Request flow:**
1. Frontend calls `/api/extract-tasks` → backend sends transcript to Claude → returns JSON task array
2. User edits/deselects tasks in the UI
3. Frontend calls `/api/tasks` (POST) for each selected task, one at a time with a 5.5s delay between requests to stay under Motion's 12 req/min rate limit

**Motion API proxy:** All Motion calls go through `motion_request()` in `server.py`, which injects the API key header. Frontend never touches Motion directly.

**Assignee matching:** Claude returns assignee names as plain strings. The frontend fuzzy-matches them against the Motion users list (fetched from `/api/users`) by comparing lowercased names. Matched users get their Motion `assigneeId` set; unmatched ones are left as `None`.

**Task state shape** (frontend JS `tasks` array):
- Fields from Claude: `name`, `description`, `priority`, `dueDate`, `assignee`
- Added by frontend: `_id` (local dedup), `_include` (checkbox), `_status` (`null`/`"ok"`/`"fail"`), `_statusMsg`, `assigneeId` (resolved Motion user ID)

**Claude prompt:** `SYSTEM_PROMPT` in `server.py`. Uses prompt caching (`cache_control: ephemeral`) on the system prompt. The `{today}` placeholder is replaced at request time so Claude can resolve relative dates.

**Rate limiting:** Motion's free tier allows 12 req/min. The frontend enforces a 5.5s inter-task delay and retries 429s up to 3 times with a 10s backoff.

**Workspace/project persistence:** Selected workspace and project IDs are saved to `localStorage` and restored on page load.

## Environment Variables

| Variable | Required | Default |
|---|---|---|
| `ANTHROPIC_API_KEY` | Yes | — |
| `MOTION_API_KEY` | Yes | — |
| `CLAUDE_MODEL` | No | `claude-sonnet-5` |
| `SSL_VERIFY` | No | `1` (set to `0` to skip TLS cert verification on outbound API calls, e.g. behind a proxy that breaks it) |

The server exits immediately at startup if either required key is missing.

## Key APIs
- Motion API: `https://api.usemotion.com/v1` — authenticated via `X-API-Key` header
- Claude API: used via `anthropic` Python SDK with prompt caching enabled
