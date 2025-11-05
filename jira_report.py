



import requests
import time
from jinja2 import Template
from html import escape
import os


# --- CONFIG ---
JIRA_BASE_URL = "https://allgon.atlassian.net"           # change this
#JIRA_BASE_URL = "https://extrapreneur.atlassian.net"
JIRA_PROJECT = "D365"                                  # e.g. "ENG" or "DEV"
#JIRA_PROJECT = "EASCP"
JIRA_USER = "rickard.dysenius@extrapreneur.se"         # your Atlassian email
JIRA_TOKEN = os.getenv("JIRA_TOKEN")
# from your API token page
REFRESH_INTERVAL = 600                                 # seconds (10 minutes)
HTML_FILE = "report.html"

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
  </style>
</head>
<body>
  <h1>Jira Report - {{ project }}</h1>
  <p>Last updated: {{ updated }}</p>
  <table>
    <tr><th>Key</th><th>Summary</th><th>Status</th><th>Description</th><th>Assignee</th></tr>
    {% for issue in issues %}
    <tr>
      <td><a href="{{ issue.url }}">{{ issue.key }}</a></td>
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

def extract_description(desc_field):
    """Extracts plain text from Jira Cloud's ADF description field."""
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
    url = f"{JIRA_BASE_URL}/rest/api/3/search/jql"
    headers = {
        "Accept": "application/json",
        "Content-Type": "application/json"
    }
    payload = {
        "jql": 'project = D365 AND status IN ("In Progress", "To Do") AND labels IN (CRM_Known_Issues, CRM_CR)',
        #"jql": f"project= EASCP ORDER BY updated DESC",
        "maxResults": 100,  # adjust if needed
        "fields": ["summary", "status", "description", "assignee"]
    }

    try:
        response = requests.post(url, headers=headers, json=payload, auth=(JIRA_USER, JIRA_TOKEN))
        if response.status_code != 200:
            print("Error:", response.status_code, response.text)
            response.raise_for_status()

        data = response.json()
        issues = []
        for issue in data.get("issues", []):
            fields = issue.get("fields", {})  # use .get to avoid NoneType
            issues.append({
                "key": issue.get("key", "N/A"),
                "summary": fields.get("summary", "N/A"),
                "status": fields.get("status", {}).get("name", "N/A") if fields.get("status") else "N/A",
                #"description": fields.get("description", "N/A"),
                "description": extract_description(fields.get("description")),
                "assignee": fields.get("assignee", {}).get("displayName", "Unassigned") if fields.get("assignee") else "Unassigned",
                "url": f"{JIRA_BASE_URL}/browse/{issue.get('key', '')}"
            })
        return issues

    except Exception as e:
        print("Exception fetching Jira issues:", e)
        return []

def render_html(issues):
    t = Template(html_template)
    html = t.render(
        project=JIRA_PROJECT,
        issues=issues,
        updated=time.strftime("%Y-%m-%d %H:%M:%S"),
        refresh_interval=REFRESH_INTERVAL
    )
    with open(HTML_FILE, "w", encoding="utf-8") as f:
        f.write(html)

def main():
    while True:
        print("Fetching Jira issues...")
        issues = get_jira_issues()

        if issues:
            render_html(issues)
            print(f"Report updated with {len(issues)} issues.")
        else:
            print("No issues to display.")
        time.sleep(REFRESH_INTERVAL)

if __name__ == "__main__":
    main()




