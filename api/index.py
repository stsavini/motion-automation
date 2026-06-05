import json
import os
import re
import sys
from datetime import date

import anthropic
import requests as http_requests
from dotenv import load_dotenv
from flask import Flask, jsonify, request, send_from_directory

load_dotenv()

ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY")
MOTION_API_KEY = os.getenv("MOTION_API_KEY")
CLAUDE_MODEL = os.getenv("CLAUDE_MODEL", "claude-sonnet-4-20250514")

STATIC_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "static")

app = Flask(__name__, static_folder=STATIC_DIR)


@app.before_request
def check_env():
    if not ANTHROPIC_API_KEY or not MOTION_API_KEY:
        return jsonify({"error": "Server misconfigured: missing API keys"}), 500


SYSTEM_PROMPT = """You are a meeting transcript analyzer. Your job is to extract actionable tasks from meeting transcripts.

Analyze the transcript provided by the user and extract every actionable task assigned to Steven. For each task, determine:

1. "name": A concise task title (under 80 characters). Start with a verb (e.g., "Draft proposal for...", "Schedule meeting with...", "Review and approve...").

2. "description": A 1-3 sentence description providing context from the meeting. Include any specific details, requirements, or constraints mentioned. Use plain text, not markdown.

3. "priority": One of "ASAP", "HIGH", "MEDIUM", or "LOW". Infer from urgency cues:
   - ASAP: words like "immediately", "urgent", "blocker", "today", "right now"
   - HIGH: words like "important", "soon", "this week", "critical", "top priority"
   - MEDIUM: standard tasks with no particular urgency signals
   - LOW: words like "when you get a chance", "nice to have", "eventually", "backlog"

4. "dueDate": An ISO 8601 date string (YYYY-MM-DD) if a deadline is mentioned or inferable. Use null if no date is mentioned. Today's date is {today}. Interpret relative dates like "next Friday", "end of the week", "by Monday" relative to today.

5. "assignee": The name of the person assigned to this task, exactly as mentioned in the transcript. Use null if no specific person is assigned.

6. "duration": An integer number of minutes estimated to complete this task. Base your estimate on the complexity and scope described in the transcript. Use these as rough guides:
   - 15: Quick action (send an email, make a call, brief lookup)
   - 30: Short task (draft a brief doc, quick review)
   - 60: Medium task (write a report, detailed review, multi-step process)
   - 120: Large task (complex analysis, lengthy document)
   - 240+: Very large task (major deliverable)
   Always provide an integer value; never use null.

Respond with ONLY a JSON array of task objects. No markdown fencing, no explanation, no preamble. Example format:

[
  {{
    "name": "Draft Q3 budget proposal",
    "description": "Create initial draft of Q3 budget proposal incorporating the new headcount projections discussed in the meeting.",
    "priority": "HIGH",
    "dueDate": "2026-04-17",
    "assignee": "Steven",
    "duration": 120
  }}
]

Rules:
- Extract ONLY tasks assigned to Steven Savini (by first name, last name, or any recognizable variant such as "Steven" or "Steve"). Ignore tasks assigned to other people.
- If a task has no explicit assignee but is clearly directed at the group or unspecified, include it — Steven may be responsible.
- Extract ONLY actionable tasks. Do not include discussion points, decisions, or informational items unless they have a clear action attached.
- If the transcript contains no actionable tasks for Steven, return an empty array: []
- Each task must be a distinct action. Do not combine multiple unrelated actions into one task.
- Prefer specific, concrete task names over vague ones."""


# --- Motion API proxy ---

def motion_request(method, path, params=None, json_body=None):
    headers = {"X-API-Key": MOTION_API_KEY}
    url = f"https://api.usemotion.com/v1{path}"
    resp = http_requests.request(
        method, url, headers=headers, params=params, json=json_body
    )
    return resp.json(), resp.status_code


@app.route("/")
def index():
    return send_from_directory(STATIC_DIR, "index.html")


@app.route("/api/workspaces")
def get_workspaces():
    data, status = motion_request("GET", "/workspaces")
    return jsonify(data), status


@app.route("/api/projects")
def get_projects():
    workspace_id = request.args.get("workspaceId")
    params = {"workspaceId": workspace_id} if workspace_id else None
    data, status = motion_request("GET", "/projects", params=params)
    return jsonify(data), status


@app.route("/api/users")
def get_users():
    workspace_id = request.args.get("workspaceId")
    params = {"workspaceId": workspace_id} if workspace_id else None
    data, status = motion_request("GET", "/users", params=params)
    return jsonify(data), status


@app.route("/api/tasks", methods=["POST"])
def create_task():
    payload = request.json
    data, status = motion_request("POST", "/tasks", json_body=payload)
    return jsonify(data), status


# --- Claude task extraction ---

@app.route("/api/extract-tasks", methods=["POST"])
def extract_tasks():
    transcript = request.json.get("transcript", "")
    if not transcript.strip():
        return jsonify({"error": "Empty transcript"}), 400

    today = date.today().isoformat()
    prompt_text = SYSTEM_PROMPT.replace("{today}", today)

    client = anthropic.Anthropic()
    response = client.messages.create(
        model=CLAUDE_MODEL,
        max_tokens=4096,
        system=[
            {
                "type": "text",
                "text": prompt_text,
                "cache_control": {"type": "ephemeral"},
            }
        ],
        messages=[{"role": "user", "content": transcript}],
    )

    text = response.content[0].text

    # Try to parse JSON directly
    try:
        tasks = json.loads(text)
    except json.JSONDecodeError:
        # Fallback: extract JSON array from response (in case of markdown fencing)
        match = re.search(r"\[.*\]", text, re.DOTALL)
        if match:
            try:
                tasks = json.loads(match.group())
            except json.JSONDecodeError:
                return jsonify({"error": "Could not parse tasks from AI response. Please try again."}), 500
        else:
            return jsonify({"error": "Could not parse tasks from AI response. Please try again."}), 500

    if not isinstance(tasks, list):
        return jsonify({"error": "Unexpected response format from AI."}), 500

    return jsonify({"tasks": tasks})


if __name__ == "__main__":
    app.run(debug=True, host="127.0.0.1", port=5000)
