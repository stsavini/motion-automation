# Motion Automation

Meeting transcript → Motion tasks pipeline. Local Flask server + single-page HTML frontend.

## Quick Start
```bash
python3 -m venv venv && source venv/bin/activate
pip install -r requirements.txt
cp .env.example .env  # add your API keys
python server.py      # http://localhost:5000
```

## Architecture
- `server.py` — Flask backend. Proxies Motion API calls and handles Claude task extraction.
- `static/index.html` — Complete frontend in one file (HTML + CSS + JS). No build step.
- `.env` — Holds ANTHROPIC_API_KEY, MOTION_API_KEY, and optional CLAUDE_MODEL.

## Key APIs
- Motion API: https://api.usemotion.com/v1 — Auth via X-API-Key header. 12 req/min rate limit (individual).
- Claude API: Used via `anthropic` Python SDK for task extraction from transcripts.

## Conventions
- Backend: All routes in server.py. Motion requests go through `motion_request()` helper.
- Frontend: Vanilla JS, no frameworks. State is a plain JS array re-rendered by `renderTasks()`.
- Keep it minimal — this is a personal tool, not production SaaS.

## Testing
- Start server, open localhost:5000
- Paste a transcript, click Extract Tasks, verify task list
- Send tasks to Motion, verify they appear in the Motion app
