import requests
from jinja2 import Template
import os
import subprocess
from datetime import datetime
import time

# --- CONFIG ---
JIRA_BASE_URL = "https://extrapreneur.atlassian.net"
JIRA_PROJECT = "EASCP"
JIRA_USER = "rickard.dysenius@extrapreneur.se"
JIRA_TOKEN = os.getenv("JIRA_TOKEN")  # export JIRA_TOKEN="..."
HTML_FILE = "index.html"
LOG_FILE = "update.log"
REFRESH_INTERVAL = 600  # seconds = 10 minutes
RETRY_INTERVAL = 60     # retry in 1 minute if Jira fetch fails

# --- HTML TEMPLATE ---
html_template = """
<!DOCTYPE html>
<html>
<head>
  <meta http-equiv="refresh" content="{{ refresh_interval }}">
  <title>Jira Report</title>
  <style>
    body { font-family: Arial, sans-serif; margin: 40px; }
    table { border-collapse: collapse; width: 100%; }
    th, td { border: 1px solid #ddd; padding: 8px; text-align: left; }
    th { background-color: #f2f2f2; }
    tr:nth-child(even) { background-color: #fafafa; }
    a { color: #007bff; text-decoration: none; }
  </style>
</head>
<body>
  <h1>Jira Report - {{ project }}</h1>
  <p>Last updated: {{ updated }}</p>
  <table>
    <tr><th>Key</th><th>Summary</th><th>Status</th><th>Description</th><th>Assignee</th></tr>
    {% for issue in issues %}
    <tr>
      <td><a href="{{ issue.url }}" target="_blank">{{ issue.key }}</a></td>
      <td>{{ issue.summary }}</td>
      <td>{{ issue.status }}</td>
      <td>{{ issue.description }}</td>
      <td>{{ issue.assignee }}</td>
    </tr>
    {% endfor %}
  </table>
</body>
</html>
"""

# --- LOGGING ---
def log(msg):
    """Print and save timestamped log messages."""
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    entry = f"[{timestamp}] {msg}"
    print(entry)
    with open(LOG_FILE, "a", encoding="utf-8") as f:
        f.write(entry + "\n")

# --- FUNCTIONS ---
def extract_description(desc_field):
    """Extract plain text from Jira Cloud's ADF description field."""
    if not desc_field:
        return "N/A"
    try:
        text_parts = []
        def walk_content(content):
            for node in content:
                if "text" in node:
                    text_parts.append(node["text"])
                if "content" in node:
                    walk_content(node["content"])
        walk_content(desc_field.get("content", []))
        return " ".join(text_parts).strip() if text_parts else "N/A"
    except Exception as e:
        return f"[Parse error: {e}]"

def get_jira_issues():
    """Fetch issues from Jira Cloud API."""
    url = f"{JIRA_BASE_URL}/rest/api/3/search/jql"
    headers = {"Accept": "application/json", "Content-Type": "application/json"}
    payload = {
        "jql": f"project = {JIRA_PROJECT} ORDER BY updated DESC",
        "maxResults": 20,
        "fields": ["summary", "status", "description", "assignee"],
    }

    try:
        response = requests.post(url, headers=headers, json=payload, auth=(JIRA_USER, JIRA_TOKEN))
        if response.status_code != 200:
            log(f"❌ Jira API Error {response.status_code}: {response.text}")
            return []
        data = response.json()
        issues = []
        for issue in data.get("issues", []):
            fields = issue.get("fields", {})
            issues.append({
                "key": issue.get("key", "N/A"),
                "summary": fields.get("summary", "N/A"),
                "status": fields.get("status", {}).get("name", "N/A"),
                "description": extract_description(fields.get("description")),
                "assignee": fields.get("assignee", {}).get("displayName", "Unassigned") if fields.get("assignee") else "Unassigned",
                "url": f"{JIRA_BASE_URL}/browse/{issue.get('key', '')}"
            })
        return issues
    except Exception as e:
        log(f"⚠️ Exception fetching Jira issues: {e}")
        return []

def render_html(issues):
    """Render Jira issues into HTML file."""
    t = Template(html_template)
    html = t.render(
        project=JIRA_PROJECT,
        issues=issues,
        updated=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        refresh_interval=REFRESH_INTERVAL
    )
    with open(HTML_FILE, "w", encoding="utf-8") as f:
        f.write(html)
    log(f"✅ Report generated with {len(issues)} issues.")

def git_commit_and_push():
    """Commit and push changes (HTML + script)."""
    try:
        subprocess.run(["git", "add", HTML_FILE, "jira_report.py"], check=True)
        diff_result = subprocess.run(["git", "diff", "--cached", "--quiet"])
        if diff_result.returncode == 0:
            log("ℹ️ No changes to commit.")
            return
        msg = f"Auto-update report {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
        subprocess.run(["git", "commit", "-m", msg], check=True)
        subprocess.run(["git", "push", "origin", "main"], check=True)
        log("🚀 Report and script pushed to GitHub successfully.")
    except subprocess.CalledProcessError as e:
        log(f"⚠️ Git push failed: {e}")

# --- MAIN LOOP ---
def main():
    log("🚀 Jira report automation started.")
    while True:
        log("🔄 Fetching Jira issues...")
        issues = get_jira_issues()

        if issues:
            render_html(issues)
            git_commit_and_push()
            log(f"💤 Sleeping for {REFRESH_INTERVAL / 60:.1f} minutes before next fetch...")
            time.sleep(REFRESH_INTERVAL)
        else:
            log(f"⚠️ No issues found or fetch failed. Retrying in {RETRY_INTERVAL / 60:.1f} minute...")
            time.sleep(RETRY_INTERVAL)

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        log("🛑 Script manually stopped.")
    except Exception as e:
        log(f"❌ Fatal error: {e}")
